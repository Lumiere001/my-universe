"""
streamlit_app.py

나의 우주 — 말을 거는 일기장 (사용자 화면)

    streamlit run streamlit_app.py          # 사용자 화면: ✍️ 일기 넣기 · 🌌 나의 우주
    주소 끝에 ?ops=1                         # 운영(Ops) 탭이 더 보인다

로그인이 없다. 우주는 이 브라우저 세션에만 있고, "정리된 기록 파일"(JSON)로 내려받았다가 다시 올린다.
서버는 사용자의 글을 저장하지 않는다.
"""

import copy
import html
import json
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

import config
import importer
import runlog
import service
import universe
import universe_view
import voice

try:
    import universe_view3d
except ImportError:
    universe_view3d = None

st.set_page_config(page_title="나의 우주", page_icon="🌌", layout="wide")
OPS = st.query_params.get("ops") == "1"
SAMPLE = config.DATA_DIR / "samples" / "하늘-2026-10-03.txt"

st.markdown("""<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
.stApp :is(p,li,label,input,textarea,h1,h2,h3,h4,h5,h6,button,div,summary,small,b,strong){
  font-family:Pretendard,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}
.vb{display:flex;gap:10px;align-items:flex-start;margin:4px 0 14px}
.vb-av{flex:none;width:40px;height:40px;border-radius:50%;background:#2a2154;border:1px solid #4c3f86;
  display:flex;align-items:center;justify-content:center;font-size:21px}
.vb-name{font-size:12.5px;font-weight:700;color:#c4b5fd;margin:0 0 3px 4px}
.vb-text{background:rgba(167,139,250,.14);border:1px solid rgba(167,139,250,.42);color:#f1edff;
  border-radius:4px 16px 16px 16px;padding:10px 14px;line-height:1.65;max-width:680px}
.uq{border-left:3px solid #5b6b9a;padding:4px 10px;color:#d6dcf5;background:rgba(255,255,255,.03);
  border-radius:0 8px 8px 0;line-height:1.6}
.rc{border:1px solid rgba(160,170,220,.22);border-left:4px solid #a78bfa;border-radius:12px;
  padding:12px 14px;margin:0 0 10px;background:rgba(15,21,48,.6)}
.rc.coral{border-left-color:#fb8a6b}.rc.gold{border-left-color:#fcd679}
.rc-head{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline;margin-bottom:8px}
.rc-head b{font-size:15.5px}
.rc-line{font-size:12px;color:#a9b6dc}.rc-line i{display:inline-block;width:20px;border-top:2px solid #e3e9ff;
  vertical-align:middle;margin-right:5px}.rc-line i.dash{border-top-style:dashed}
.rc-body{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.rc-side{flex:1 1 200px;min-width:0}.rc-arrow{color:#a78bfa;font-size:18px}
.rc-when{font-size:12px;color:#a9b6dc;margin-bottom:3px}
.rc-why{font-size:12.5px;color:#a9b6dc;margin-top:8px}
</style>""", unsafe_allow_html=True)


##################################################
# 세션 상태
##################################################

@st.cache_data
def demo_state():
    return json.loads(config.DEMO_UNIVERSE.read_text(encoding="utf-8")) if config.DEMO_UNIVERSE.exists() else None


def use_state(state, source):
    st.session_state.state = state
    st.session_state.source = source
    st.session_state.selected = state["order"][-1] if state["order"] else None
    st.session_state.pop("result", None)


if "state" not in st.session_state:
    use_state(copy.deepcopy(demo_state()) if demo_state() else universe.new_state(), "demo" if demo_state() else "new")
    st.session_state.pick = st.session_state.source
st.session_state.setdefault("budget", service.Budget())
st.session_state.setdefault("v_name", "별지기")
st.session_state.setdefault("v_tone", "다정하게")
S = st.session_state.state


def say(text, opener=False):
    """일기장이 하는 말은 모두 말풍선으로."""
    st.markdown(voice.bubble(text, st.session_state.v_tone, st.session_state.v_name, opener), unsafe_allow_html=True)


##################################################
# 사이드바: 우주 고르기 · 내려받기 · 말투
##################################################

PICK = {"demo": "데모 우주 (가상 인물 하늘)", "new": "새 우주", "file": "정리된 기록 파일 불러오기"}


def switch_universe():
    st.session_state.pop("loaded_name", None)
    if st.session_state.pick == "demo":
        use_state(copy.deepcopy(demo_state()), "demo")
    elif st.session_state.pick == "new":
        use_state(universe.new_state(), "new")
    # file: 파일을 올려야 바뀐다


with st.sidebar:
    st.title("🌌 나의 우주")
    st.caption("말을 거는 일기장")
    st.subheader("우주 고르기")
    st.radio("우주 고르기", list(PICK), format_func=PICK.get, key="pick", on_change=switch_universe,
             label_visibility="collapsed")
    if st.session_state.pick == "file":
        up = st.file_uploader("정리된 기록 파일 (.json)", type=["json"], key="state_up")
        if up is not None and st.session_state.get("loaded_name") != up.name:
            try:
                loaded = json.loads(up.getvalue().decode("utf-8"))
                assert {"records", "thoughts", "hubs", "relations"} <= set(loaded)
                use_state(loaded, "file")
                st.session_state.loaded_name = up.name
                st.rerun()
            except Exception:
                st.error("나의 우주에서 내려받은 정리된 기록 파일이 아니에요. '정리된 기록 파일 내려받기'로 받은 .json 파일을 올려 주세요.")
    now = {"demo": "하늘의 우주", "new": "새 우주", "file": st.session_state.get("loaded_name", "불러온 파일")}[st.session_state.source]
    st.write(f"지금: **{now}** · 일기 {len(S['order'])}편")
    st.download_button("정리된 기록 파일 내려받기", json.dumps(S, ensure_ascii=False), file_name="my-universe.json",
                       mime="application/json", width="stretch", disabled=not S["order"], on_click="ignore")
    st.caption("서버는 일기를 저장하지 않아요. 우주를 바꾸기 전이나 다음에 이어 쓰려면 먼저 내려받아 두세요.")
    st.divider()
    st.subheader("말투")
    st.text_input("일기장 이름", key="v_name", max_chars=12)
    st.radio("말투", voice.TONES, key="v_tone")
    say("오늘 하루는 어땠어요?")
    st.divider()
    st.caption("Powered by Upstage Studio · 전남대 생성형 AI 트랙 5조")


##################################################
# 관측 결과: 이어진 지난 일기 카드 → 우주 → 일기장의 말
##################################################

REL_WORDS = {"바뀜": ("🔀", "생각이 바뀌었어요"), "이어짐": ("🔗", "같은 생각이 이어져요"), "해소": ("🌕", "고민이 정리됐어요"),
             "어긋남": ("⭕", "다짐과 다르게 흘러갔어요"), "긴장": ("🌗", "두 마음이 함께 있어요"), "목표 충돌": ("⚡", "목표끼리 부딪혀요")}
LINE_WORDS = {"실선": '<i></i>실선 · 글에 직접 쓴 변화', "점선": '<i class="dash"></i>점선 · AI가 추정한 연결'}
ORDER = ("resolved", "changed", "continued", "missed_vows", "tension", "goal_conflicts")


def kday(d):
    return f"{int(d[5:7])}월 {int(d[8:10])}일"


def rel_card(i):
    e = html.escape
    kept = i["type"] == "이어짐" and i["past"]["kind"] == "다짐"
    icon, words = ("🌟", "다짐이 지켜졌어요") if kept else REL_WORDS.get(i["type"], ("·", i["type"]))
    color = "gold" if kept else "coral" if i["type"] in ("긴장", "어긋남", "목표 충돌") else ""
    return (f'<div class="rc {color}"><div class="rc-head"><b>{icon} {words}</b><span class="rc-line">{LINE_WORDS.get(i["line"], e(i["line"]))}</span></div>'
            f'<div class="rc-body"><div class="rc-side"><div class="rc-when">그때 · {kday(i["past"]["day"])}</div><div class="uq">“{e(i["past"]["quote"])}”</div></div>'
            f'<div class="rc-arrow">→</div><div class="rc-side"><div class="rc-when">지금 · {kday(i["today"]["day"])}</div><div class="uq">“{e(i["today"]["quote"])}”</div></div></div>'
            f'<div class="rc-why">{e(i["explanation"])}</div></div>')


def universe_html(selected, height):
    if universe_view3d and st.session_state.get("view_mode", "3D") == "3D":
        return universe_view3d.render(S, selected, height=height)
    return universe_view.render(S, selected)


def show_result(rid, fresh, with_universe, where):
    v = service.view_report(S, rid)
    items = [i for k in ORDER for i in v[k] if i["past"]["record_id"] != rid]
    n = len({i["past"]["record_id"] for i in items})
    if n:
        st.markdown(f"### {'새 별이' if fresh else '이 별은'} 지난 일기 {n}편과 이어졌어요")
    else:
        st.markdown(f"### {'새 별이 우주에 떴어요' if fresh else '아직 홀로 빛나는 별이에요'}")
    st.caption(f"{kday(v['day'])} · {v['title']}")
    if items:
        st.markdown("".join(rel_card(i) for i in items), unsafe_allow_html=True)
    else:
        say("아직 이어진 지난 일기는 없어요. 몇 편 더 쓰면 생각이 어떻게 흘러가는지 보이기 시작해요.")
    if with_universe:
        components.html(universe_html(rid, 560), height=560)
    if v["summary"]:
        say(v["summary"], opener=fresh)
    if v["question"]:
        say(voice.ask(v["question"]))
    with st.expander("자세히 보기"):
        st.caption(f"글 유형: {v['type']} · 날짜: {v['day']} ({v['day_basis']}) · 관측 상태: {v['observation_state']} · 찾은 생각 {v['counts']['thoughts']}개")
        for l in v["limits"]:
            st.write("- " + l)
        g = v["gates"]
        st.write(f"- 원문에 없는 인용 걸러냄 {g['G1_dropped_quotes']} · 날짜 확인 {'통과' if g['G2_date_ok'] else '확인 필요'} · "
                 f"단정 표현 바꿈 {g.get('G3_rewritten', 0)} · 가린 이름 {g['G4_names_masked']}")
        st.download_button("관측 결과 JSON 내려받기", json.dumps(v, ensure_ascii=False, indent=2), file_name=f"observation-{v['day']}.json",
                           mime="application/json", key=f"dl-{where}-{rid}", on_click="ignore")
        st.json(v, expanded=False)


def run_one(rec, status):
    return service.process_record(S, rec, budget=st.session_state.budget, progress=lambda s: status.write(s))


def finished(rid, imported=0):
    st.session_state.selected = st.session_state.result = rid
    st.session_state.imported = imported
    st.rerun()   # 사이드바·우주 탭은 실행 전에 그려졌으므로 새 별이 보이도록 다시 그린다


##################################################
# 탭: 일기 넣기 · 나의 우주 (· 운영은 ?ops=1 일 때만)
##################################################

tabs = st.tabs(["✍️ 일기 넣기", "🌌 나의 우주"] + (["🛠 운영(Ops)"] if OPS else []), key="page")   # key: 다시 그려도 보던 탭 유지

with tabs[0]:
    done = st.session_state.get("result")
    if done in S["reports"]:
        if st.session_state.get("imported", 0) > 1:
            say(f"일기 {st.session_state.imported}편을 우주에 더했어요. 마지막 일기부터 보여 드릴게요.")
        show_result(done, fresh=True, with_universe=True, where="w")
        st.divider()
        st.markdown("#### 다른 일기도 넣어 볼까요?")
    else:
        say("오늘 있었던 일, 든 생각, 고민, 다짐을 들려주세요. 지난 일기와 이어지는 생각을 찾아 드릴게요.")

    how = st.radio("어떻게 넣을까요?", ["직접 쓰기", "파일 올리기"], horizontal=True, key="how",
                   captions=["지금 바로 써요", "txt · md · 인스타그램 ZIP"])
    if how == "직접 쓰기":
        with st.form("write"):
            title = st.text_input("제목", placeholder="예: 10/3 토요일 일기")
            day = st.date_input("일기 속 날짜", value=date.today())
            body = st.text_area("본문", height=240, placeholder="있었던 일, 든 생각, 고민, 다짐을 자유롭게 써 보세요.")
            go = st.form_submit_button("저장하고 우주에 띄우기", type="primary")
        st.caption("저장하면 일기 속 생각을 찾아 지난 일기와 비교해요. 1분쯤 걸려요.")
        if go:
            if len(body.strip()) < 20:
                st.warning("본문을 20자 이상 써 주세요.")
            else:
                rec = importer.from_direct(title, body, day.isoformat())
                with st.status("일기를 읽는 중…", expanded=True) as status:
                    try:
                        run_one(rec, status)
                        finished(rec["id"])
                    except Exception as e:
                        status.update(label="실행하지 못했어요", state="error")
                        st.error(f"{e} — 잠시 후 다시 눌러 주세요. 쓴 글은 그대로 있어요.")
    else:
        if SAMPLE.exists():
            st.download_button("예시 일기 받기", SAMPLE.read_bytes(), file_name="하늘-2026-10-03-일기.txt", mime="text/plain",
                               type="tertiary", icon=":material/download:", on_click="ignore",
                               help="가상 인물 하늘의 10월 3일 일기예요. 받은 파일을 아래에 올려 보세요.")
        files = st.file_uploader("일기 파일 올리기", type=["zip", "md", "txt"], accept_multiple_files=True,
                                 help="인스타그램은 '내 정보 다운로드'(JSON 형식) ZIP을 올려 주세요. 사진은 쓰지 않고 글만 읽어요.")
        if files:
            recs = []
            for f in files:
                try:
                    recs += importer.from_instagram_zip(f.getvalue()) if f.name.lower().endswith(".zip") else importer.from_text_file(f.name, f.getvalue())
                except Exception as e:
                    st.error(f"{f.name}: {e}")
            recs = [r for r in recs if r["id"] not in S["records"]]
            recs.sort(key=lambda r: (r["day"], r["written_at"]))
            if recs:
                span = kday(recs[0]["day"]) + ("" if recs[0]["day"] == recs[-1]["day"] else f" ~ {kday(recs[-1]['day'])}")
                st.write(f"새 일기 **{len(recs)}편**을 찾았어요 ({span}).")
                n = 1
                if len(recs) > 1:
                    n = int(st.number_input("최근 일기 몇 편을 넣을까요?", 1, min(len(recs), config.MAX_IMPORT_POSTS), min(len(recs), 5)))
                    st.caption(f"한 편에 1분쯤, 한 번에 {config.MAX_IMPORT_POSTS}편까지 넣을 수 있어요.")
                if st.button("가져와서 우주에 띄우기", type="primary"):
                    chosen = recs[-n:]
                    bar = st.progress(0.0)
                    with st.status("일기를 읽는 중…", expanded=True) as status:
                        for i, rec in enumerate(chosen, 1):
                            status.write(f"[{i}/{len(chosen)}] {rec['day']} {rec['title'][:20]}")
                            try:
                                run_one(rec, status)
                            except Exception as e:
                                st.error(f"{rec['day']} 일기에서 멈췄어요: {e}. 다시 누르면 이어서 진행해요(정리된 일기는 다시 보내지 않아요).")
                                break
                            bar.progress(i / len(chosen))
                        else:
                            finished(chosen[-1]["id"], len(chosen))
                        status.update(label="가져오기 멈춤", state="error")
                    st.session_state.selected = S["order"][-1]
            else:
                st.info("새로 넣을 일기가 없어요. 이미 우주에 있는 일기는 건너뛰어요.")

with tabs[1]:
    reported = [r for r in S["order"] if r in S["reports"]]
    if not reported:
        say("아직 별이 없어요. ✍️ 일기 넣기에서 첫 일기를 들려주세요.")
    else:
        left, right = st.columns([7, 4])
        with left:
            st.radio("보기", ["3D", "평면"], horizontal=True, key="view_mode", label_visibility="collapsed",
                     disabled=universe_view3d is None)
            components.html(universe_html(st.session_state.selected, 680), height=680)
        with right:
            names = {r: f"{kday(S['records'][r]['day'])} · {S['records'][r]['title'][:24]}" for r in reported}
            idx = reported.index(st.session_state.selected) if st.session_state.selected in reported else len(reported) - 1
            pick = st.selectbox("어느 일기를 볼까요?", reported[::-1], index=len(reported) - 1 - idx, format_func=lambda r: names[r])
            if pick != st.session_state.selected:
                st.session_state.selected = pick
                st.rerun()
            show_result(pick, fresh=False, with_universe=False, where="u")

if OPS:
    with tabs[2]:
        st.subheader("운영(Ops) — 실행 기록")
        st.caption(f"이번 세션 Studio 실행 남은 횟수: {st.session_state.budget.left}/{config.MAX_JOBS_PER_SESSION}")
        st.caption("글 원문과 인용문은 기록하지 않습니다. 실행 ID, 설정 버전, 시간, 추정 비용, 관문 결과, 개수만 남깁니다.")
        logs = [l for l in runlog.read() if l["step"] in ("record", "observe")]
        shipped = config.DATA_DIR / "ops" / "run_log_virtual.jsonl"
        if not logs and shipped.exists():
            logs = [json.loads(l) for l in shipped.read_text(encoding="utf-8").splitlines() if l.strip()]
            logs = [l for l in logs if l["step"] in ("record", "observe")]
            st.caption("이 서버에서는 아직 실행이 없어, 개발 때 가상 글 29편을 처리한 기록을 보여 줍니다.")
        if logs:
            fresh = [l for l in logs if not l.get("cached")]
            c = st.columns(5)
            c[0].metric("Studio 실행", len(logs))
            c[1].metric("캐시로 건너뜀", len(logs) - len(fresh))
            c[2].metric("평균 처리 시간", f"{sum(l['seconds'] for l in fresh) / max(len(fresh), 1):.1f}s")
            c[3].metric("추정 비용 합계", f"${sum(l['est_cost'] for l in fresh):.2f}")
            c[4].metric("G1 걸러낸 인용", sum(l.get("G1_dropped_quotes", 0) for l in logs))
            st.dataframe([{k: l.get(k) for k in ("at", "run_id", "step", "agent", "config_id", "seconds", "pages", "est_cost", "cached",
                                                  "type", "state", "thoughts", "past", "relations", "rule_changes", "G1_dropped_quotes", "G4_names_masked")}
                          for l in logs[::-1]], width="stretch", hide_index=True)
        else:
            st.info("아직 이 서버에서 실행한 기록이 없습니다.")
        st.markdown("**설정 버전**")
        st.write(f"기록 Agent config #{config.RECORD_CONFIG_ID} · 관측 Agent config #{config.OBSERVE_CONFIG_ID} · 임베딩 {config.EMBEDDING_MODEL}")
        for name, title in (("eval_virtual.json", "가상 데이터 평가 (설계한 관계를 얼마나 찾았나)"), ("stability.json", "흔들림 측정 (같은 글을 여러 번)")):
            p = config.DATA_DIR / "ops" / name
            if p.exists():
                st.markdown(f"**{title}**")
                st.json(json.loads(p.read_text(encoding="utf-8")), expanded=False)
