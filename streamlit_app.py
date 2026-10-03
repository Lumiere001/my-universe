"""
streamlit_app.py

나의 우주 — 화면

    streamlit run streamlit_app.py

로그인이 없다. 우주는 이 브라우저 세션에만 있고, "정리된 기록 파일"(JSON)로 내려받았다가 다시 올린다.
서버에는 사용자의 글을 저장하지 않는다.
"""

import copy
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

try:
    import universe_view3d
except ImportError:
    universe_view3d = None

st.set_page_config(page_title="나의 우주", page_icon="🌌", layout="wide")


##################################################
# 세션 상태
##################################################

@st.cache_data
def demo_state():
    return json.loads(config.DEMO_UNIVERSE.read_text(encoding="utf-8")) if config.DEMO_UNIVERSE.exists() else None


def ensure_state():
    if "state" not in st.session_state:
        demo = demo_state()
        st.session_state.state = copy.deepcopy(demo) if demo else universe.new_state()
        st.session_state.source = "demo" if demo else "new"
        st.session_state.selected = st.session_state.state["order"][-1] if st.session_state.state["order"] else None
    if "budget" not in st.session_state:
        st.session_state.budget = service.Budget()


ensure_state()
S = st.session_state.state


def use_state(state, source):
    st.session_state.state = state
    st.session_state.source = source
    st.session_state.selected = state["order"][-1] if state["order"] else None


##################################################
# 사이드바
##################################################

with st.sidebar:
    st.title("🌌 나의 우주")
    st.caption("내가 쓴 글에서 지켜 온 생각, 바뀐 생각, 아직 풀지 못한 긴장을 근거와 함께 보여 줍니다.")
    st.divider()
    st.subheader("우주 고르기")
    label = {"demo": "데모: 하늘의 우주 (가상 인물)", "new": "새 우주", "file": "불러온 정리된 기록 파일"}[st.session_state.source]
    st.write(f"지금: **{label}** · 글 {len(S['order'])}편")
    c1, c2 = st.columns(2)
    if c1.button("데모 우주", width="stretch", disabled=demo_state() is None):
        use_state(copy.deepcopy(demo_state()), "demo")
        st.rerun()
    if c2.button("새 우주", width="stretch"):
        use_state(universe.new_state(), "new")
        st.rerun()
    up = st.file_uploader("정리된 기록 파일 불러오기 (.json)", type=["json"], key="state_up")
    if up is not None and st.session_state.get("loaded_name") != up.name:
        try:
            loaded = json.loads(up.getvalue().decode("utf-8"))
            assert {"records", "thoughts", "hubs", "relations"} <= set(loaded)
            use_state(loaded, "file")
            st.session_state.loaded_name = up.name
            st.rerun()
        except Exception:
            st.error("나의 우주에서 내려받은 정리된 기록 파일이 아닙니다.")
    st.download_button("정리된 기록 파일 내려받기", json.dumps(S, ensure_ascii=False), file_name="my-universe.json",
                       mime="application/json", width="stretch", disabled=not S["order"])
    st.caption("서버는 글을 저장하지 않습니다. 다음에 이어 쓰려면 이 파일을 내려받아 두세요.")
    st.divider()
    st.caption(f"이번 세션 Studio 실행 남은 횟수: {st.session_state.budget.left}/{config.MAX_JOBS_PER_SESSION}")
    st.caption("Powered by Upstage Studio · 전남대 생성형 AI 트랙 5조")


##################################################
# 관측 보고서 그리기
##################################################

def show_report(rid):
    v = service.view_report(S, rid)
    st.markdown(f"#### {v['day']} · {v['title']}")
    st.caption(f"글 유형: {v['type']} · 날짜 {v['day_basis']}")
    st.markdown(f"**관측 상태: {v['observation_state']}**")
    if v["summary"]:
        st.write(v["summary"])
    kinds = " · ".join(f"{k} {n}" for k, n in v["counts"]["by_kind"].items())
    m = st.columns(4)
    m[0].metric("생각", v["counts"]["thoughts"])
    m[1].metric("별자리", sum(len(v[k]) for k in ("continued", "changed", "tension", "resolved", "missed_vows", "goal_conflicts")))
    m[2].metric("처리 시간", f"{round(v['run']['seconds'])}초")
    m[3].metric("추정 비용", f"${v['run']['est_cost_usd']}")
    if kinds:
        st.caption(f"생각의 종류: {kinds}")

    def items(title, rows, icon):
        if not rows:
            return
        st.markdown(f"**{icon} {title} {len(rows)}**")
        for r in rows:
            st.markdown(f"- `{r['line']}` {r['topic']} · {r['past']['day']} → {r['today']['day']}  \n"
                        f"  그때: “{r['past']['quote']}”  \n  지금: “{r['today']['quote']}”  \n"
                        f"  <span style='color:#8a90b8'>{r['explanation']}{' · 축: ' + r['axis'] if r['axis'] else ''}</span>",
                        unsafe_allow_html=True)

    items("바뀐 생각", v["changed"], "🔀")
    items("이어진 생각", v["continued"], "🔗")
    items("긴장 (쌍성)", v["tension"], "🌗")
    items("해소", v["resolved"], "🌕")
    items("어긋난 다짐", v["missed_vows"], "⭕")
    items("목표 충돌", v["goal_conflicts"], "⚡")
    if v["question"]:
        st.info(f"다음에 써 볼 질문 · {v['question']}")
    with st.expander("한계와 관문 결과"):
        for l in v["limits"]:
            st.write("- " + l)
        g = v["gates"]
        st.write(f"- G1 원문에 없는 인용 걸러냄: {g['G1_dropped_quotes']} · G2 날짜 확인: {'통과' if g['G2_date_ok'] else '확인 필요'} · "
                 f"G3 단정 표현 바꿈: {g.get('G3_rewritten', 0)} · G4 가린 이름: {g['G4_names_masked']}")
    st.download_button("관측 보고서 JSON 내려받기", json.dumps(v, ensure_ascii=False, indent=2),
                       file_name=f"observation-{v['day']}.json", mime="application/json", key=f"dl-{rid}")
    with st.expander("JSON 보기"):
        st.json(v)


def run_one(rec, status):
    return service.process_record(S, rec, budget=st.session_state.budget, progress=lambda s: status.write(s))


##################################################
# 탭
##################################################

tab_u, tab_w, tab_i, tab_o = st.tabs(["🌌 우주 · 관측 보고서", "✍️ 글쓰기", "📥 가져오기", "🛠 운영(Ops)"], key="page")   # key: 다시 그려도 보던 탭 유지

with tab_u:
    if not S["order"]:
        st.info("아직 별이 없습니다. ✍️ 글쓰기에서 첫 글을 쓰거나, 📥 가져오기로 지난 글을 올려 보세요.")
    else:
        left, right = st.columns([7, 4])
        with left:
            mode = st.radio("보기", ["3D", "평면"], horizontal=True, key="view_mode", label_visibility="collapsed",
                            disabled=universe_view3d is None)
            if mode == "3D" and universe_view3d:
                components.html(universe_view3d.render(S, st.session_state.selected), height=680)
            else:
                components.html(universe_view.render(S, st.session_state.selected), height=680)
        with right:
            reported = [r for r in S["order"] if r in S["reports"]]
            names = {r: f"{S['records'][r]['day']} · {S['records'][r]['title'][:24]}" for r in reported}
            idx = reported.index(st.session_state.selected) if st.session_state.selected in reported else len(reported) - 1
            pick = st.selectbox("관측 보고서", reported[::-1], index=len(reported) - 1 - idx, format_func=lambda r: names[r])
            if pick != st.session_state.selected:
                st.session_state.selected = pick
                st.rerun()
            show_report(pick)

with tab_w:
    st.subheader("오늘의 글")
    st.caption("저장하면 기록 Agent가 생각을 나누고, 관측 Agent가 지난 생각과 비교합니다. 약 1분 걸립니다.")
    with st.form("write"):
        title = st.text_input("제목", placeholder="예: 10/3 금요일 일기")
        day = st.date_input("글이 다루는 날", value=date.today())
        body = st.text_area("본문", height=260, placeholder="있었던 일, 든 생각, 고민, 다짐을 자유롭게 써 보세요.")
        go = st.form_submit_button("저장하고 관측하기", type="primary")
    if go:
        if len(body.strip()) < 20:
            st.warning("본문을 조금 더 써 주세요 (20자 이상).")
        else:
            rec = importer.from_direct(title, body, day.isoformat())
            with st.status("관측하는 중…", expanded=True) as status:
                try:
                    run_one(rec, status)
                    status.update(label="완료! 우주에 새 별이 떴습니다.", state="complete")
                    st.session_state.selected = rec["id"]
                except Exception as e:
                    status.update(label="실행하지 못했습니다", state="error")
                    st.error(f"{e} — 잠시 후 다시 시도해 주세요. 글은 지워지지 않았습니다.")
            if rec["id"] in S["reports"]:
                show_report(rec["id"])

with tab_i:
    st.subheader("지난 글 가져오기")
    st.caption("인스타그램 '내 정보 다운로드' ZIP(JSON 형식), MD, TXT 파일을 올릴 수 있습니다. 사진은 쓰지 않고 글만 읽습니다.")
    files = st.file_uploader("파일 올리기", type=["zip", "md", "txt"], accept_multiple_files=True)
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
            st.write(f"새 글 **{len(recs)}편**을 찾았습니다 ({recs[0]['day']} ~ {recs[-1]['day']}). "
                     f"이어진 게시물은 하나로 묶고, 제목 속 날짜와 소제목을 찾았습니다.")
            n = st.number_input("최근 글 몇 편을 관측할까요?", 1, min(len(recs), config.MAX_IMPORT_POSTS), min(len(recs), 5))
            st.caption(f"예상: 약 {int(n)}분 · 추정 비용 약 ${n * 0.1:.2f} (공개 버전은 한 번에 {config.MAX_IMPORT_POSTS}편까지)")
            if st.button("가져와서 관측하기", type="primary"):
                chosen = recs[-int(n):]
                bar = st.progress(0.0)
                with st.status("가져오는 중…", expanded=True) as status:
                    for i, rec in enumerate(chosen, 1):
                        status.write(f"[{i}/{len(chosen)}] {rec['day']} {rec['title'][:20]}")
                        try:
                            run_one(rec, status)
                        except Exception as e:
                            st.error(f"{rec['day']} 글에서 멈췄습니다: {e}. 다시 누르면 이어서 진행합니다(정리된 글은 다시 보내지 않습니다).")
                            break
                        bar.progress(i / len(chosen))
                    status.update(label="가져오기 끝", state="complete")
                st.session_state.selected = S["order"][-1]
        else:
            st.info("새로 관측할 글이 없습니다 (이미 우주에 있는 글은 건너뜁니다).")

with tab_o:
    st.subheader("운영(Ops) — 실행 기록")
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
