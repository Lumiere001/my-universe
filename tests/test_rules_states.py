"""상태 모델 · 사용자 버튼 · 기한 · 우주 배치용 요약."""
import pytest

from app.core.ontology import load
from app.service.rules import advance, due_vows, filter_relations, parse_due, press, universe_view

O = load()


def T(i, day, kind, topic="걷기", domain="건강", certainty="단정", rid=None, **kw):
    return {"id": i, "record_id": rid or f"R{day}", "day": day, "kind": kind, "certainty": certainty,
            "topic": topic, "domain": domain, "quote": "", "thought": kw.pop("thought", ""), "self_change": "",
            "people": [], **kw}


class U:
    """글을 날짜 순으로 하나씩 넣으며 규칙 → 상태를 미는 작은 도우미."""

    def __init__(self):
        self.thoughts, self.relations, self.states, self.records = {}, [], {}, {}

    def write(self, ts, cands=()):
        for t in ts:
            self.thoughts[t["id"]] = t
            self.records[t["record_id"]] = {"id": t["record_id"], "day": t["day"]}
        kept, _ = filter_relations(list(cands), self.thoughts, self.states)
        self.relations += kept
        self.states = advance(self.states, self.thoughts, kept, ts[0]["record_id"])
        return kept


def test_state_names_come_from_ontology():
    names = {s for v in O["states"].values() for s in v["states"]}
    assert {"열림", "지켜짐", "그만둠", "해소", "블랙홀", "후보", "확정"} <= names
    assert {b["name"] for b in O["state_buttons"]} == {"지켰어요", "그만둘래요", "맞아요"}


def test_reflection_keeps_vow_open_with_mistake_mark():
    u = U()
    u.write([T("v", "2026-03-20", "다짐", thought="매일 아침 30분 걷겠다")])
    assert u.states["v"]["state"] == "열림"
    u.write([T("r", "2026-04-08", "자기평가(부정)")], [{"a": "v", "b": "r", "type": "긴장"}])
    s = u.states["v"]
    assert s["state"] == "열림" and s["marks"] == ["실수"]
    assert s["history"][-1]["thought"] == "r" and s["history"][-1]["relation"] == "v>r"


def test_vow_kept_by_text_and_by_buttons():
    u = U()
    u.write([T("v", "2026-03-20", "다짐")])
    u.write([T("k", "2026-07-10", "자기평가(긍정)")], [{"a": "v", "b": "k", "type": "해소"}])
    assert u.states["v"]["state"] == "지켜짐"
    u2 = U()
    u2.write([T("v", "2026-03-20", "다짐")])
    st, _ = press(u2.states, u2.relations, "v", "그만둘래요", day="2026-04-01")
    assert st["v"]["state"] == "그만둠" and st["v"]["history"][-1]["button"] == "그만둘래요"
    assert u2.states["v"]["state"] == "열림"   # 받은 dict 는 그대로
    with pytest.raises(ValueError):
        press(st, [], "v", "지켰어요")         # 닫힌 다짐에는 버튼이 안 먹음


def test_question_resolves():
    u = U()
    u.write([T("q", "2026-04-20", "질문", topic="리더십", domain="공동체", certainty="판단 보류")])
    assert u.states["q"]["state"] == "열림"
    u.write([T("b", "2026-08-15", "신념·원칙", topic="리더십", domain="공동체")], [{"a": "q", "b": "b", "type": "이어짐"}])
    assert u.states["q"]["state"] == "해소" and u.states["q"]["history"][-1]["thought"] == "b"


def test_tension_reappearing_grows_black_hole():
    u = U()
    kw = dict(topic="혼자와 함께", domain="관계")
    u.write([T("a", "2026-04-05", "신념·원칙", **kw)])
    u.write([T("b", "2026-04-12", "해석", **kw)], [{"a": "a", "b": "b", "type": "긴장", "axis": "혼자 ↔ 함께"}])
    g = u.states["긴장:a>b"]
    assert (g["state"], g["size"]) == ("열림", 0)
    u.write([T("c", "2026-05-01", "해석", **kw)], [{"a": "b", "b": "c", "type": "긴장"}])
    assert (u.states["긴장:a>b"]["state"], u.states["긴장:a>b"]["size"]) == ("블랙홀", 1)
    u.write([T("d", "2026-06-01", "해석", **kw)], [{"a": "x", "b": "y", "type": "긴장"}, {"a": "c", "b": "d", "type": "긴장", "axis": "혼자↔함께"}])
    assert u.states["긴장:a>b"]["size"] == 2
    u.write([T("e", "2026-06-20", "신념·원칙", **kw)], [{"a": "d", "b": "e", "type": "해소"}])
    assert u.states["긴장:a>b"]["state"] == "해소"


def test_tension_same_day_does_not_grow():
    u = U()
    kw = dict(topic="혼자와 함께", domain="관계")
    u.write([T("a", "2026-04-05", "해석", **kw)])
    u.write([T("b", "2026-04-12", "해석", **kw), T("c", "2026-04-12", "해석", **kw)],
            [{"a": "a", "b": "b", "type": "긴장"}, {"a": "a", "b": "c", "type": "긴장"}])
    g = u.states["긴장:a>b"]
    assert (g["state"], g["size"], g["relations"]) == ("열림", 0, ["a>b", "a>c"])


def test_change_candidate_confirmed_on_other_day_or_button():
    kw = dict(topic="혼자와 함께", domain="관계")
    u = U()
    u.write([T("a", "2026-04-05", "신념·원칙", **kw)])
    u.write([T("b", "2026-04-12", "신념·원칙", **kw)], [{"a": "a", "b": "b", "type": "바뀜"}])
    assert u.states["a>b"]["state"] == "후보"
    st, rels = press(u.states, u.relations, "a>b", "맞아요")
    assert st["a>b"]["state"] == "확정" and rels[0]["line"] == "실선"
    u.write([T("c", "2026-05-01", "해석", **kw)], [{"a": "b", "b": "c", "type": "이어짐"}])
    assert u.states["a>b"]["state"] == "확정" and u.states["a>b"]["history"][-1]["thought"] == "c"


def test_self_written_change_confirmed_at_once():
    u = U()
    u.write([T("a", "2026-03-14", "신념·원칙", topic="진로")])
    u.write([T("b", "2026-09-20", "신념·원칙", topic="진로", self_change="큰 회사 → 작은 팀")],
            [{"a": "a", "b": "b", "type": "바뀜", "author_stated": "예"}])
    assert u.states["a>b"]["state"] == "확정"


def test_self_written_change_to_open_question_stays_candidate():
    # 4/5 "혼자가 편하다" → 4/12 "지난주엔 혼자가 편하다 했는데 … 어느 쪽이 진짜 나일까" = 바뀜 후보
    kw = dict(topic="혼자와 함께", domain="관계")
    u = U()
    u.write([T("a", "2026-04-05", "신념·원칙", **kw)])
    u.write([T("b", "2026-04-12", "질문", certainty="판단 보류", self_change="혼자 → 함께", **kw)],
            [{"a": "a", "b": "b", "type": "바뀜", "author_stated": "예"}])
    assert u.states["a>b"]["state"] == "후보"


def test_no_button_deletes_dotted_relation():
    u = U()
    u.write([T("a", "2026-03-14", "해석")])
    u.write([T("b", "2026-03-20", "해석")], [{"a": "a", "b": "b", "type": "긴장"}])
    st, rels = press(u.states, u.relations, "a>b", "아니에요")
    assert rels == [] and "긴장:a>b" not in st
    with pytest.raises(ValueError):
        press(st, rels, "a>b", "아니에요")


@pytest.mark.parametrize("text,day,want", [
    ("금요일까지 첨삭을 끝내겠다", "2026-10-08", "2026-10-09"),   # 목 → 금
    ("다음 주까지 정리하겠다", "2026-10-08", "2026-10-18"),
    ("이번 달까지 끝내겠다", "2026-12-03", "2026-12-31"),
    ("다음 달까지 끝내겠다", "2026-12-03", "2027-01-31"),
    ("10월 3일까지 내겠다", "2026-10-08", "2027-10-03"),
    ("매일 아침 걷겠다", "2026-10-08", None),
])
def test_parse_due(text, day, want):
    assert parse_due(text, day) == want


def test_overdue_open_vows_are_checkin_material():
    u = U()
    u.write([T("v", "2026-10-08", "다짐", thought="금요일까지 동생 원서 첨삭을 끝내 주겠다")])
    u.write([T("w", "2026-10-08", "다짐", rid="R2", thought="매일 걷겠다")])
    assert due_vows(u.states, "2026-10-09") == []
    assert [d["thought"] for d in due_vows(u.states, "2026-10-12")] == ["v"]
    assert u.states["v"]["state"] == "열림"   # 저절로 닫지 않음


def test_universe_view():
    u = U()
    u.write([T("a1", "2026-03-20", "다짐", people=["민수"]), T("a2", "2026-03-20", "해석")])
    u.write([T("b1", "2026-04-05", "신념·원칙", topic="혼자와 함께", domain="관계")])
    u.write([T("c1", "2026-04-12", "해석", topic="혼자와 함께", domain="관계")],
            [{"a": "b1", "b": "c1", "type": "긴장"}, {"a": "a1", "b": "c1", "type": "이어짐", "quoted": "예",
                                                    "explanation": "원문 근거"}])
    u.write([T("d1", "2026-05-01", "해석", topic="혼자와 함께", domain="관계")], [{"a": "c1", "b": "d1", "type": "긴장"}])
    u.records["R0"] = {"id": "R0", "day": "2026-03-01"}   # 생각 없는 글
    v = universe_view(u.records, u.thoughts, u.relations, u.states, suns=["통일 사역"])
    assert [s["name"] for s in v["suns"]] == ["관계", "건강", "통일 사역"]
    assert "여가" in v["hidden_axes"]
    star = next(s for s in v["stars"] if s["name"] == "혼자와 함께")
    assert star["planets"] == ["R2026-04-05", "R2026-04-12", "R2026-05-01"]   # 가까울수록 먼저 쓴 기록
    p = {x["id"]: x for x in v["planets"]}
    assert p["R2026-03-20"]["ring"] == "열림" and p["R2026-04-12"]["orbit"] == 1 and p["R0"]["star"] is None
    assert v["people"] == {"민수": ["R2026-03-20"]}
    cross = next(line for line in v["lines"] if line["from"] == "a1")
    assert cross["show"] == "on_tap" and cross["line"] == "점선" and cross["needs_confirm"]
    assert v["binaries"] == [] and v["black_holes"][0]["size"] == 1
    st, _ = press(u.states, u.relations, "a1", "지켰어요")
    v = universe_view(u.records, u.thoughts, u.relations, st)
    assert {x["id"]: x for x in v["planets"]}["R2026-03-20"]["ring"] == "채워짐"
