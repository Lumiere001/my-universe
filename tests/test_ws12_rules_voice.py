"""WS12 규칙 · 말 걸기 결함: 빈 인용(G1) · G3 와 내부 번호 · 글로 지킨/그만둔 다짐 · 말 걸기 재료(heavy · person_history ·
지난 생각 · 바뀜) · 넘어가기와 그만 묻기 · 좁아짐 막기 · 목표 충돌 ended. 외부 클라이언트는 가짜(tests.test_graph_flow)."""
import re

import pytest

from app.agents import graph
from app.core.ontology import load
from app.repository import diary, views
from app.service import rules, voice
from app.service.rules import advance, clean_text, filter_relations, reask_trigger, strip_ids
from tests.test_graph_flow import NAMES, U1, env  # noqa: F401  (env 는 fixture)


# ---------- 순수 규칙 ----------

def T(i, day, kind, topic="걷기", domain="건강", rid=None, **kw):
    return {"id": i, "record_id": rid or f"R{day}", "day": day, "kind": kind, "certainty": kw.pop("certainty", "단정"),
            "topic": topic, "domain": domain, "quote": kw.pop("quote", ""), "thought": kw.pop("thought", ""),
            "self_change": "", **kw}


def run(cands, *ts, states=None):
    return filter_relations(cands, {t["id"]: t for t in ts}, states)


def test_strip_internal_ids_and_g3():
    assert strip_ids("P3에서 혼자가 편하다고 했는데 T1와 맞선다. (T2) T1는 P12를 잇는다") == \
        "지난 생각에서 혼자가 편하다고 했는데 오늘 생각과 맞선다. 오늘 생각 오늘 생각은 지난 생각을 잇는다"
    assert strip_ids("HTTP2 · T10x") == "HTTP2 · T10x"            # 낱말 속 글자는 그대로
    assert clean_text("T1과 P1이 이어진다. 글쓴이는 의지가 약한 사람이다.") == "오늘 생각과 지난 생각이 이어진다."
    assert clean_text("우울증 진단을 받은 날이다.", "오늘 우울증 진단을 받았다") == "우울증 진단을 받은 날이다."   # 글쓴이 말은 둠
    assert clean_text("우울증 경향이 보인다.", "오늘은 지쳤다") == ""
    # 글쓴이 원문에 있는 글자('T1' 팀 이름)는 내부 번호가 아니라 그대로 둔다
    assert clean_text("T1 경기를 보며 페이커를 응원했다.", "오늘 T1 경기를 봤다") == "T1 경기를 보며 페이커를 응원했다."
    # 요약의 줄바꿈은 둔다(이어진 공백만 줄임)
    assert strip_ids("아침에 걸었다.\n\nT1   저녁엔 쉬었다.") == "아침에 걸었다.\n\n오늘 생각 저녁엔 쉬었다."
    assert clean_text("아침에 걸었다.\n글쓴이는 의지가 약한 사람이다.\n저녁엔  쉬었다.\n밤엔 읽었다.") == \
        "아침에 걸었다.\n저녁엔 쉬었다.\n밤엔 읽었다."


def test_relation_explanation_cleaned():
    a, b = T("a", "2026-03-20", "해석"), T("b", "2026-04-02", "해석")
    kept, _ = run([{"a": "a", "b": "b", "type": "이어짐", "explanation": "P1과 T1이 같은 방향이다. 너는 게으른 사람이다."}], a, b)
    assert kept[0]["explanation"] == "지난 생각과 오늘 생각이 같은 방향이다."


def test_cross_domain_other_day_needs_explanation_after_cleaning():
    """영역을 넘는 다른 날 관계는 G3 · 내부 번호를 거른 설명으로 판정한다. 거른 뒤 비면 버린다."""
    a, b = T("a", "2026-03-20", "해석", domain="일"), T("b", "2026-04-02", "해석", domain="관계")
    c = {"a": "a", "b": "b", "type": "이어짐", "quoted": True}
    kept, dropped = run([{**c, "explanation": "글쓴이는 의지가 약한 사람이다."}], a, b)
    assert not kept and dropped[0]["reason"] == "영역 넘는 다른 날 관계인데 원문 설명이 없음"
    kept, _ = run([{**c, "explanation": "P1에서 일이 버겁다고 했다. 글쓴이는 의지가 약한 사람이다."}], a, b)
    assert kept[0]["explanation"] == "지난 생각에서 일이 버겁다고 했다." and kept[0]["line"] == "점선"


def test_positive_self_eval_after_open_vow_is_kept_vow():
    """관측 2판은 지킨 다짐을 '이어짐'으로 낸다 → 열린 다짐 + 다른 글의 같은 주제 자기평가(긍정)이면 지켜짐."""
    v = T("v", "2026-03-20", "다짐", thought="매일 아침 30분 걷겠다")
    k = T("k", "2026-04-02", "자기평가(긍정)", thought="2주 동안 하루도 안 빠지고 걸었다")
    kept, _ = run([{"a": "v", "b": "k", "type": "이어짐"}], v, k)
    assert (kept[0]["type"], kept[0]["vow_kept"]) == ("이어짐", True)
    st = advance(advance({}, {"v": v}, [], "R2026-03-20"), {"v": v, "k": k}, kept, "R2026-04-02")
    assert st["v"]["state"] == "지켜짐"
    # 다른 주제 · 닫힌 다짐 · 같은 글 · 다짐 다시 쓰기는 지켜짐이 아님
    other = T("o", "2026-04-02", "자기평가(긍정)", topic="발표")
    again = T("g", "2026-04-02", "다짐", thought="다음 주도 걷겠다")
    same = T("s", "2026-03-20", "자기평가(긍정)")
    kept, _ = run([{"a": "v", "b": "o", "type": "이어짐", "explanation": "x", "quoted": True},
                   {"a": "v", "b": "g", "type": "이어짐"}, {"a": "v", "b": "s", "type": "이어짐"}], v, other, again, same)
    assert not any(r["vow_kept"] for r in kept)
    kept, _ = run([{"a": "v", "b": "k", "type": "이어짐"}], v, k, states={"v": {"kind": "다짐", "state": "그만둠"}})
    assert not kept[0]["vow_kept"]


def test_quit_text_closes_vow():
    v = T("v", "2026-03-20", "다짐", thought="매일 아침 30분 걷겠다")
    q = T("q", "2026-04-10", "해석", thought="아침 걷기는 그만두기로 했다", quote="아침 걷기는 그만두기로 했다.")
    kept, _ = run([{"a": "v", "b": "q", "type": "해소"}], v, q)
    r = kept[0]
    assert (r["type"], r["vow_quit"], r["vow_kept"]) == ("이어짐", True, False)   # 해소 → 지켜짐 으로 잘못 닫지 않음
    st = advance(advance({}, {"v": v}, [], "R2026-03-20"), {"v": v, "q": q}, kept, "R2026-04-10")
    assert st["v"]["state"] == "그만둠" and st["v"]["history"][-1]["why"] == "그만둔다는 글"
    for kind, text in (("소망", "걷기를 그만두고 싶다"), ("질문", "그만둘까"), ("자기평가(부정)", "결국 포기했다, 또 졌다")):
        x = T("x", "2026-04-10", kind, thought=text, certainty="판단 보류" if kind == "질문" else "단정")
        kept, _ = run([{"a": "v", "b": "x", "type": "이어짐"}], v, x)
        assert not any(k["vow_quit"] for k in kept), kind
    # 그만두지 않는다는 다짐 글은 그만둠이 아니다(열림으로 남음)
    for text in ("힘들어도 포기하지 않기로 했다", "끝까지 포기 안 하기로 했다", "걷기는 그만두지 않기로 했다"):
        x = T("x", "2026-04-10", "다짐", thought=text, quote=text)
        kept, _ = run([{"a": "v", "b": "x", "type": "이어짐"}], v, x)
        assert not kept[0]["vow_quit"], text
        st = advance(advance({}, {"v": v}, [], "R2026-03-20"), {"v": v, "x": x}, kept, "R2026-04-10")
        assert st["v"]["state"] == "열림", text
    x = T("x", "2026-04-10", "해석", thought="걷기는 안 하기로 했다")     # 부정 꼴이 아닌 '안 하기로'는 그대로 그만둠
    assert run([{"a": "v", "b": "x", "type": "이어짐"}], v, x)[0][0]["vow_quit"]


def test_new_vow_in_quit_form_keeps_old_vow_open():
    """새 생각이 그 자체로 다짐이면(같은 주제의 새 다짐) 그만두는 꼴이어도 앞 다짐을 그만둠 · 지켜짐으로 닫지 않는다."""
    v = T("v", "2026-03-20", "다짐", topic="야근", domain="일", thought="야근을 줄이겠다")
    for text in ("주중엔 야근을 안 하기로 했다", "야근은 이제 그만하기로 했다"):
        n = T("n", "2026-04-10", "다짐", topic="야근", domain="일", thought=text, quote=text)
        for rtype in ("이어짐", "해소"):
            kept, _ = run([{"a": "v", "b": "n", "type": rtype}], v, n)
            r = kept[0]
            assert (r["type"], r["vow_quit"], r["vow_kept"]) == ("이어짐", False, False), (text, rtype)
            st = advance(advance({}, {"v": v}, [], "R2026-03-20"), {"v": v, "n": n}, kept, "R2026-04-10")
            assert st["v"]["state"] == "열림" and st["n"]["state"] == "열림", (text, rtype)


def test_reask_trigger():
    missed = {"v": {"kind": "다짐", "state": "열림", "topic": "걷기", "marks": ["실수"]}}
    assert reask_trigger([{"type": "바뀜", "from": "a", "to": "b"}], {})
    assert reask_trigger([{"type": "어긋남", "from": "v", "to": "b", "topic": "걷기"}], missed)       # 같은 어긋남 반복
    assert not reask_trigger([{"type": "어긋남", "from": "w", "to": "b", "topic": "발표"}], missed)  # 처음 어긋남
    assert not reask_trigger([{"type": "이어짐", "from": "a", "to": "b"}], missed)


def test_heavy_and_widen_pick():
    assert voice.is_heavy([{"kind": "감정", "thought": "하루 종일 슬펐다"}])
    assert voice.is_heavy([{"kind": "해석", "quote": "할머니 기일이라 성묘를 다녀왔다."}])
    assert voice.is_heavy([], ["할머니 장례"])
    assert not voice.is_heavy([{"kind": "해석", "thought": "슬픈 영화를 보고 대본 구조를 분석했다"}])   # 감정 생각이 아님
    for text in ("내일부터 유산소 30분씩 하겠다", "헤어샵에서 머리를 잘랐다", "지갑을 잃어버려서 짜증났다", "여행을 떠난 첫날이 설렌다"):
        assert not voice.is_heavy([{"kind": "감정", "thought": text, "quote": text}], [text]), text   # 상실 말 아님
    c = [{"kind": "axis", "key": "sun:관계", "name": "관계"}, {"kind": "axis", "key": "sun:여가", "name": "여가"}]
    assert voice.pick_widen(c, []) == c[0]
    assert voice.pick_widen(c, ["", "sun:관계"]) is None                 # 가끔: 바로 앞에서 썼으면 쉼
    assert voice.pick_widen(c, ["sun:관계", ""]) == c[1]                 # 같은 재료 연속 금지
    assert voice.pick_widen([], []) is None


def test_widen_question_kind_and_heavy_skips_it():
    base = {"days_written": 5, "weather": "맑음", "aspiration": {"said": "x"}, "text": "공원을 걸었다."}
    w = {"kind": "axis", "key": "sun:여가", "name": "여가"}
    assert voice.next_question_kind({**base, "widen": w}) == "widen"
    assert "여가" in voice.base_question("widen", {"widen": w})
    assert voice.next_question_kind({**base, "widen": w, "heavy": True}) == ""      # 무거운 날엔 넓히지 않음
    assert "넓혀 보기" in voice.situations({**base, "widen": {"kind": "twin", "key": "twin:p"}})


def test_heavy_day_does_not_reflect_changes():
    """위기 · 비 · 천둥 날에는 바뀜이 있어도 '생각이 바뀜' 지시와 changes 재료를 프롬프트에 싣지 않는다."""
    ch = [{"before": "혼자가 편하다", "after": "같이 걷고 싶다", "day": "2026-10-01"}]
    base = {"text": "오늘 글", "changes": ch, "tone": "다정하게"}
    for extra in ({"crisis": True}, {"weather": "비"}, {"weather": "천둥"}, {"heavy": True}):
        ctx = {**base, **extra}
        sit = voice.situations(ctx)
        assert "무거운 날" in sit and "생각이 바뀜" not in sit, extra
        blob = repr(voice.build_messages(ctx, "", sit, False))
        assert "예전엔" not in blob and "혼자가 편하다" not in blob, extra
    sit = voice.situations(base)                                   # 평소 날엔 비춰 준다
    assert "생각이 바뀜" in sit and "혼자가 편하다" in repr(voice.build_messages(base, "", sit, False))


def test_skip_vs_stop_question_kind():
    base = {"days_written": 5, "weather": "맑음", "text": "공원을 걸었다."}
    assert voice.next_question_kind(base) == "aspiration_invite"
    assert voice.next_question_kind({**base, "aspiration_off": True}) == ""


# ---------- 그래프(가짜 Studio · Solar, 메모리 저장소) ----------

@pytest.fixture
def seen(monkeypatch):
    """voice.generate 가 받은 ctx(가명 처리 뒤)를 남긴다."""
    got, orig = [], voice.generate

    def spy(ctx):
        got.append(ctx)
        return orig(ctx)
    monkeypatch.setattr(voice, "generate", spy)
    return got


def put(env, title, text, when, weather="맑음"):
    eid = diary.new_id("e")
    with env.repo.session(U1) as s:
        diary.create_entry(s, eid, diary.parse_dt(when), weather, title, text)
    graph.run(env.repo, U1, eid)
    with env.repo.session(U1) as s:
        return eid, views.entry_result(s, eid)


def observe_as(env, type_, explanation="이어진 생각"):
    """관측 가짜: 첫 지난 생각(P1) → 첫 오늘 생각(T1) 을 type_ 으로 잇는다."""
    def obs(html):
        ids = re.findall(r"<li>([TP]\d+) · ", html)
        t, p = [i for i in ids if i[0] == "T"], [i for i in ids if i[0] == "P"]
        rels = [{"type": [type_], "past_id": [p[0]], "today_id": [t[0]], "same_target": [""], "topic": ["아침 걷기"],
                 "evidence": [""], "explanation": [explanation], "axis": [""], "author_stated": ["아니오"]}] if t and p else []
        return {"state": [""], "summary": [""], "question": [""], "relations": rels, "reached": []}
    env.fake._observe = obs


def record_with(env, monkeypatch, **override):
    first = env.fake._record

    def rec(html):
        d = first(html)
        for k, v in override.items():
            v(d) if callable(v) else d.__setitem__(k, v)
        return d
    monkeypatch.setattr(env.fake, "_record", rec)


def test_empty_quote_thought_dropped_and_summary_g3(env, monkeypatch):
    def empty_second(d):
        d["thoughts"][1]["quote"] = [""]
    record_with(env, monkeypatch, thoughts=empty_second, summary=["글쓴이는 게으른 사람이다. T1에서 걷기를 시작한 날."])
    _, r = put(env, "걷기", "오늘부터 매일 아침 걷기를 하겠다. 민준이가 같이 걷자고 해서 고맙다.", "2026-10-01T22:00:00+09:00")
    assert len(r["thoughts"]) == 1 and r["thoughts"][0]["kind"] == "다짐"     # 빈 인용 생각은 저장하지 않음(G1)
    assert r["info"]["summary"] == "오늘 생각에서 걷기를 시작한 날."            # 판정 문장 빠지고 내부 번호 없음


def test_voice_materials_masked(env, monkeypatch, seen):
    """heavy · person_history · 지난 생각 · 바뀜이 ctx 로 들어가고, 외부(Solar)로는 가명만 나간다."""
    first = env.fake._record

    def rec(html):   # 요약 = 첫 문장(가명 글로 받은 것 → 원래 이름으로 되돌아와 저장됨), 편지 글이면 말 거는 대상 = 특정 인물
        d = first(html)
        body = " ".join(re.findall(r"<p>(.*?)</p>", html))
        d["summary"] = [re.findall(r"[^.]+\.", body)[0].strip()]
        if "에게" in body:
            d["addressee"] = ["특정 인물"]
        return d
    monkeypatch.setattr(env.fake, "_record", rec)
    put(env, "산책", "민준이랑 공원을 한 바퀴 걸었다.", "2026-10-01T22:00:00+09:00")
    observe_as(env, "바뀜")
    _, r = put(env, "편지", "민준이에게 쓴다. 혼자 걷는 게 더 편하다고 느꼈다.", "2026-10-03T22:00:00+09:00")
    ctx = seen[-1]
    assert len(ctx["person_history"]) == 1 and "공원을 한 바퀴 걸었다" in ctx["person_history"][0]   # 그 사람이 나온 지난 기록
    assert ctx["past_thoughts"] and ctx["changes"] and ctx["heavy"] is False
    assert r["message"]["mode"] == "normal"
    blob = repr({k: ctx[k] for k in ("person_history", "past_thoughts", "changes")})
    assert not [n for n in NAMES if n in blob]                                 # generate 에 온 재료가 이미 가명
    chat = [m for m in env.fake.sent if '"role": "system"' in m and "별지기" in m][-1]
    assert "person_history" in chat and "past_thoughts" in chat and "changes" in chat and "예전엔" in chat
    assert not [n for n in NAMES if n in "\n".join(env.fake.sent)]            # 외부 요청 전체 실명 0건
    _, r = put(env, "장례", "민준이랑 할머니 장례를 치렀다.", "2026-10-04T22:00:00+09:00")
    assert seen[-1]["heavy"] is True and seen[-1]["changes"] and r["message"]["mode"] == "comfort"   # 무거운 날 → 위로만
    chat = [m for m in env.fake.sent if '"role": "system"' in m and "별지기" in m][-1]
    assert "예전엔" not in chat                                                # 무거운 날엔 바뀜을 되비추지 않음


def _three_days(env):
    for i, text in enumerate(("아침에 공원을 걸었다.", "점심에 동네를 걸었다.", "저녁에 강가를 걸었다."), 1):
        put(env, f"걷기 {i}", text, f"2026-10-0{i}T22:00:00+09:00")


@pytest.mark.parametrize("mode", ["skip", "stop"])
def test_skip_reasks_on_trigger_stop_never(env, mode):
    _three_days(env)
    with env.repo.session(U1) as s:
        diary.save_profile(s, onboarding={"aspiration": mode})
    _, r = put(env, "걷기 4", "밤에 운동장을 걸었다.", "2026-10-04T22:00:00+09:00")   # 계기 없음(이어짐)
    assert r["next_question"]["kind"] != "aspiration"
    observe_as(env, "바뀜")                                                        # 관련 생각의 바뀜 = 계기
    _, r = put(env, "걷기 5", "혼자 걷는 게 더 좋다고 느꼈다.", "2026-10-05T22:00:00+09:00")
    assert r["relations"][0]["type"] == "바뀜"
    with env.repo.session(U1) as s:
        ob = diary.profile(s)[1]["aspiration"]
        should = views.aspiration_state(s)["ask"]["should_ask"]
    if mode == "skip":
        assert r["next_question"]["kind"] == "aspiration" and ob == "none" and should is True
    else:
        assert r["next_question"]["kind"] != "aspiration" and ob == "stop" and should is False


@pytest.mark.parametrize("weather,text", [("비", "혼자 걷는 게 더 좋다고 느꼈다."),
                                          ("맑음", "혼자 걷는 게 더 좋다고 느꼈다. 요즘 너무 지쳐서 죽고 싶다는 생각이 든다.")])
def test_reask_waits_past_heavy_or_crisis_day(env, weather, text):
    """'이번엔 넘어가기' 뒤 계기가 무거운 날(비) · 위기 글에서 생기면 그 글에선 다시 묻지 않고, 다음 글에서 묻는다."""
    _three_days(env)
    with env.repo.session(U1) as s:
        diary.save_profile(s, onboarding={"aspiration": "skip"})
    observe_as(env, "바뀜")
    _, r = put(env, "걷기 4", text, "2026-10-04T22:00:00+09:00", weather=weather)
    assert r["relations"][0]["type"] == "바뀜" and r["message"]["mode"] == "comfort"
    with env.repo.session(U1) as s:
        assert diary.profile(s)[1]["aspiration"] == "skip" and not views.aspiration_state(s)["ask"]["should_ask"]
    assert r["next_question"]["kind"] != "aspiration"
    observe_as(env, "이어짐")                                                       # 다음 글엔 새 계기 없음
    _, r = put(env, "걷기 5", "밤에 운동장을 걸었다.", "2026-10-05T22:00:00+09:00")
    with env.repo.session(U1) as s:
        ob = diary.profile(s)[1]
        should = views.aspiration_state(s)["ask"]["should_ask"]
    assert r["next_question"]["kind"] == "aspiration" and ob["aspiration"] == "none" and not ob["reask_pending"] and should


def test_widen_sometimes_and_not_same_twice(env, seen):
    _three_days(env)
    with env.repo.session(U1) as s:
        diary.save_profile(s, onboarding={"aspiration": "stop"})   # 되고 싶은 모습 초대가 끼지 않게
    keys = []
    for i in (4, 5, 6):
        _, r = put(env, f"걷기 {i}", "밤에 운동장을 걸었다.", f"2026-10-0{i}T22:00:00+09:00")
        with env.repo.session(U1) as s:
            keys.append(diary.message(s, s.rows("messages", entry_id=r["id"])[0]).get("widen"))
        if keys[-1]:
            assert r["next_question"]["kind"] == "free" and seen[-1]["widen"]["name"] in r["next_question"]["text"]
    with env.repo.session(U1) as s:
        written = {x["name"] for x in diary.suns(s)}
    axes = [d["name"] for d in load()["domains"] if d["name"] not in written]
    assert keys == [f"sun:{axes[0]}", "", f"sun:{axes[1]}"]    # 글이 없는 기준 축 → 쉼 → 다른 축


def test_twin_material_from_today_tension(env, seen):
    put(env, "혼자", "혼자 걷는 게 편하다.", "2026-10-01T22:00:00+09:00")
    observe_as(env, "긴장")
    put(env, "함께", "같이 걸어야 오래 간다.", "2026-10-02T22:00:00+09:00")
    w = seen[-1]["widen"]
    assert w["kind"] == "twin" and w["past"] and "넓혀 보기" in voice.situations(seen[-1])


def test_goal_conflict_link_ended_when_vow_closes(env):
    put(env, "걷기", "매일 아침 걷기를 하겠다.", "2026-10-01T22:00:00+09:00")
    observe_as(env, "목표 충돌")
    put(env, "책", "매일 아침 책 읽기를 하겠다.", "2026-10-02T22:00:00+09:00")
    with env.repo.session(U1) as s:
        link = views.universe(s)["links"][0]
        assert link["type"] == "목표 충돌" and link["ended"] is False
        st, _ = rules.press(diary.states(s), diary.relations(s), link["id"].split(">")[0], "지켰어요")
        diary.save_states(s, st, diary.states(s))
        assert views.universe(s)["links"][0]["ended"] is True
