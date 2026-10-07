"""관계 규칙 v8: 판단형은 같은 주제, 영향형은 근거가 있으면 영역을 넘음, 같은 쌍은 하나, 감정끼리 금지."""
from app.service.rules import filter_relations


def T(i, day, kind, topic, domain, certainty="단정", rid=None, **kw):
    return {"id": i, "record_id": rid or f"R{day}", "day": day, "kind": kind, "certainty": certainty,
            "topic": topic, "domain": domain, "quote": kw.pop("quote", ""), "thought": "", "self_change": "", **kw}


def TH(*ts):
    return {t["id"]: t for t in ts}


def rel(a, b, type_, **kw):
    return {"a": a, "b": b, "type": type_, "explanation": kw.pop("explanation", "원문 근거 설명"), **kw}


def run(cands, *ts, states=None):
    return filter_relations(cands, TH(*ts), states)


def test_change_only_within_same_topic():
    a = T("a", "2026-03-14", "신념·원칙", "진로", "삶의 성취")
    b = T("b", "2026-09-20", "신념·원칙", "진로", "삶의 성취", self_change="큰 회사 → 작은 팀")
    c = T("c", "2026-09-21", "신념·원칙", "배움", "삶의 성취")
    kept, dropped = run([rel("a", "b", "바뀜", author_stated="예"), rel("a", "c", "바뀜")], a, b, c)
    assert [(k["type"], k["line"]) for k in kept] == [("바뀜", "실선")]
    assert dropped[0]["reason"].startswith("판단형(바뀜)인데 다른 주제")


def test_solid_needs_both_agents():
    a = T("a", "2026-03-14", "신념·원칙", "진로", "삶의 성취")
    b = T("b", "2026-09-20", "신념·원칙", "진로", "삶의 성취")   # 기록 Agent가 스스로 쓴 변화를 안 뽑음
    kept, _ = run([rel("a", "b", "바뀜", author_stated="예")], a, b)
    assert kept[0]["line"] == "점선"


def test_dotted_always_needs_confirm_solid_never():
    """점선 = AI 추정 → 맞아요/아니에요 단추(v8.json line_styles). 영역 안 점선도 확인을 받는다."""
    a = T("a", "2026-03-14", "신념·원칙", "진로", "삶의 성취")
    b = T("b", "2026-09-20", "신념·원칙", "진로", "삶의 성취", self_change="큰 회사 → 작은 팀")
    for stated, line, confirm in (("예", "실선", False), ("아니오", "점선", True), (None, "점선", True)):
        kept, _ = run([rel("a", "b", "바뀜", author_stated=stated)], a, b)
        assert (kept[0]["line"], kept[0]["needs_confirm"], kept[0]["cross_domain"]) == (line, confirm, False)


def test_emotions_are_not_change_or_resolution():
    a = T("a", "2026-05-02", "감정", "진로", "삶의 성취")
    b = T("b", "2026-08-28", "감정", "진로", "삶의 성취")
    kept, dropped = run([rel("a", "b", "바뀜"), rel("b", "a", "해소")], a, b)
    assert kept == [] and {d["reason"] for d in dropped} == {"감정끼리는 바뀜이 아님", "감정끼리는 해소이 아님"}
    kept, _ = run([rel("a", "b", "이어짐")], a, b)   # 감정끼리 이어짐은 됨
    assert [k["type"] for k in kept] == ["이어짐"]


def test_same_pair_keeps_one_by_priority():
    a = T("a", "2026-04-05", "신념·원칙", "혼자와 함께", "관계")
    b = T("b", "2026-04-12", "해석", "혼자와 함께", "관계")
    kept, dropped = run([rel("a", "b", "이어짐"), rel("b", "a", "긴장"), rel("a", "b", "바뀜")], a, b)
    assert [k["type"] for k in kept] == ["바뀜"]
    assert sum("하나" in d["reason"] for d in dropped) == 2


def test_different_pairs_all_kept():
    a = T("a", "2026-04-05", "해석", "x", "관계")
    b = T("b", "2026-04-12", "해석", "x", "관계")
    c = T("c", "2026-04-12", "해석", "x", "관계", rid="R2026-04-12")
    kept, _ = run([rel("a", "b", "이어짐"), rel("a", "c", "이어짐")], a, b, c)
    assert len(kept) == 2


def test_cross_domain_other_day_is_dotted_and_needs_confirm():
    a = T("a", "2026-05-10", "다짐", "수영", "건강")
    b = T("b", "2026-06-01", "해석", "월세", "생활 수준")
    kept, _ = run([rel("a", "b", "이어짐", quoted="예", author_stated="예")], a, b)
    k = kept[0]
    assert (k["line"], k["needs_confirm"], k["cross_domain"]) == ("점선", True, True)
    kept, dropped = run([rel("a", "b", "이어짐", quoted="아니오")], a, b)   # 원문 근거 없음 → 금지
    assert kept == [] and "원문 설명이 없음" in dropped[0]["reason"]


def test_cross_domain_same_record_needs_flow_and_quote():
    a = T("a", "2026-05-10", "다짐", "수영", "건강", rid="R1")
    b = T("b", "2026-05-10", "해석", "월세", "생활 수준", rid="R1", quote="그래도 알바를 줄이면 월세가 빠듯하다.")
    c = T("c", "2026-05-10", "해석", "월세", "생활 수준", rid="R1", quote="월세가 빠듯하다.")
    kept, dropped = run([rel("a", "b", "긴장", quoted=True), rel("a", "c", "긴장", quoted=True)], a, b, c)
    assert [(k["to"], k["line"], k["needs_confirm"]) for k in kept] == [("b", "실선", False)]
    assert "이어 쓴 흐름" in dropped[0]["reason"]


def test_judgment_type_never_crosses_domain():
    a = T("a", "2026-03-20", "다짐", "걷기", "건강")
    b = T("b", "2026-04-08", "자기평가(부정)", "시험", "삶의 성취")
    kept, dropped = run([rel("a", "b", "어긋남", quoted=True)], a, b)
    assert kept == [] and "다른 주제" in dropped[0]["reason"]


def test_vow_then_reflection_becomes_mismatch_only_while_open():
    a = T("a", "2026-03-20", "다짐", "걷기", "건강")
    b = T("b", "2026-04-08", "자기평가(부정)", "걷기", "건강")
    kept, _ = run([rel("a", "b", "긴장")], a, b)
    assert kept[0]["type"] == "어긋남" and kept[0]["notes"]
    closed = {"a": {"kind": "다짐", "state": "지켜짐"}}
    kept, dropped = run([rel("a", "b", "어긋남")], a, b, states=closed)
    assert kept == [] and "열린 다짐" in dropped[0]["reason"]


def test_vow_resolution_becomes_kept_vow():
    a = T("a", "2026-03-20", "다짐", "걷기", "건강")
    b = T("b", "2026-07-10", "자기평가(긍정)", "걷기", "건강")
    kept, _ = run([rel("a", "b", "해소")], a, b)
    assert (kept[0]["type"], kept[0]["vow_kept"]) == ("이어짐", True)


def test_question_resolved_by_same_topic_assertion():
    a = T("a", "2026-04-20", "질문", "리더십", "공동체", certainty="판단 보류")
    b = T("b", "2026-08-15", "신념·원칙", "리더십", "공동체")
    c = T("c", "2026-08-16", "신념·원칙", "리더십", "공동체", certainty="고민 중")
    kept, dropped = run([rel("a", "b", "이어짐"), rel("a", "c", "해소")], a, b, c)
    assert [k["type"] for k in kept] == ["해소"]
    assert "단정이 아님" in dropped[0]["reason"]


def test_goal_conflict_needs_two_open_vows():
    a = T("a", "2026-05-10", "다짐", "학업", "삶의 성취")
    b = T("b", "2026-05-15", "다짐", "동아리 운영", "공동체")
    c = T("c", "2026-05-15", "해석", "동아리 운영", "공동체", rid="R9")
    kept, _ = run([rel("a", "b", "목표 충돌", quoted=True)], a, b)
    assert kept[0]["type"] == "목표 충돌" and kept[0]["cross_domain"]
    kept, dropped = run([rel("a", "c", "목표 충돌", quoted=True)], a, c)
    assert kept == []
    kept, _ = run([rel("a", "b", "목표 충돌", quoted=True)], a, b, states={"a": {"kind": "다짐", "state": "그만둠"}})
    assert kept == []


def test_unknown_ids_or_types_dropped():
    a = T("a", "2026-05-10", "해석", "x", "관계")
    kept, dropped = run([rel("a", "zz", "이어짐"), rel("a", "a", "이어짐"), {"a": "a", "b": "a", "type": "우정"}], a)
    assert kept == [] and len(dropped) == 3
