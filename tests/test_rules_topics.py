"""주제 재사용 입력 · 해 이름 금지 · 합치기 후보 · 삶의 영역(혼합형)."""
from app.service.rules import clean_record, link_domain, match_topic, merge_candidates, sun_list, topic_input


def test_topic_input_lists_existing_stars():
    s = topic_input({"진로": "삶의 성취", "혼자와 함께": "관계"})
    assert s.endswith("기존 작은 별: 진로, 혼자와 함께") and "다시 쓴다" in s
    assert topic_input([]).endswith("없음")


def test_match_topic_reuses_existing_names():
    topics = {"혼자와 함께": "관계"}
    assert match_topic("혼자와  함께", topics) == ("혼자와 함께", None)
    assert match_topic("혼자와함께", topics) == ("혼자와 함께", None)
    assert match_topic("혼자 vs 함께", topics, aliases={"혼자 vs 함께": "혼자와 함께"}) == ("혼자와 함께", None)
    assert match_topic("부모님", topics) == ("부모님", None)   # 새 이름


def test_match_topic_forbids_sun_names():
    # 그 해의 작은 별이 하나뿐이면 그 이름으로 한 단계 구체적으로
    assert match_topic("관계", {"혼자와 함께": "관계"}) == ("혼자와 함께", None)
    # 둘 이상이거나 없으면 고치지 못하고 표시
    assert match_topic("관계", {"혼자와 함께": "관계", "부모님": "관계"}) == ("관계", "해 이름")
    assert match_topic("건강", {}) == ("건강", "해 이름")
    # 사용자가 추가한 해 이름도 금지
    assert match_topic("통일 사역", {}, suns=["통일 사역"]) == ("통일 사역", "해 이름")


def test_match_topic_flags_value_names_and_empty():
    # 가치 이름(Schwartz 10개)은 주제가 아니다: 해 이름처럼 표시(고칠 근거가 없어 그대로)
    assert match_topic("배려", {"부모님": "관계"}) == ("배려", "가치 이름")
    assert match_topic(" 성취 ", {}) == ("성취", "가치 이름")
    assert match_topic("", {}) == ("", "빈 주제") and match_topic(None, {}) == ("", "빈 주제")
    # 가치 낱말이 든 구체적인 주제는 그대로
    assert match_topic("친구 배려하기", {}) == ("친구 배려하기", None)


def test_clean_record_marks_value_topic():
    from app.service.rules import clean_record
    r = clean_record({"thoughts": [{"thought": "먼저 챙기고 싶다", "kind": "소망", "certainty": "단정", "topic": ["배려"]},
                                   {"thought": "잘 모르겠다", "kind": "질문", "certainty": "판단 보류", "topic": []}]})
    assert [(t["topic"], t["problems"]) for t in r["thoughts"]] == [("배려", ["가치 이름"]), ("", ["빈 주제"])]


def test_link_domain_mixed():
    assert link_domain("진로") == "삶의 성취"
    assert link_domain("부모님과 대화") == "관계"                     # 대표 낱말이 이름에 들어 있음
    assert link_domain("북한 이탈 청년", suns=[{"name": "통일 사역", "keywords": ["북한"]}]) == "통일 사역"
    # 낱말로 안 되면 중심 보정 임베딩이 가장 가까운 해
    center = [1.0, 1.0, 0.0]
    vecs = {"건강": [[1.0, 2.0, 0.0]], "여가": [[1.0, 1.0, 1.0]]}
    assert link_domain("새벽 수영", vec=[1.0, 1.0, 3.0], sun_vecs=vecs, center=center) == "여가"
    assert link_domain("알 수 없는 말") is None


def test_sun_list_hides_axes_without_writing():
    ts = [{"domain": "관계"}, {"domain": "삶의 성취"}, {"domain": None}]
    out = sun_list(ts, suns=["통일 사역"])
    assert out["shown"] == ["삶의 성취", "관계", "통일 사역"]
    assert "건강" in out["hidden"] and "관계" not in out["hidden"] and len(out["hidden"]) == 7


def test_merge_candidates():
    topics = {"혼자와 함께": "관계", "혼자와함께": "관계", "부모님": "관계", "엄마": "관계", "진로": "삶의 성취"}
    vecs = {"부모님": [1, 0.1], "엄마": [1, 0.2], "혼자와 함께": [0, 1], "진로": [1, 0.15]}
    got = merge_candidates(topics, vecs)
    assert got[0]["why"] == "띄어쓰기만 달라요"
    pairs = {(g["a"], g["b"]) for g in got}
    assert ("부모님", "엄마") in pairs
    assert not any("진로" in p for p in pairs)   # 다른 해와는 합치지 않음


def test_many_topics_become_one():
    """품질 4판: 주제 칸에 이름을 쉼표로 여럿 쓰면 글에 낱말이 나오는 이름 하나로(같으면 앞 이름). 가운뎃점은 나누지 않음."""
    from app.service.rules.topics import one_topic
    assert one_topic("독서노트 습관, 진로 선택, 혼자 있는 시간", "당분간은 모임을 줄이고 내 시간을 지키고 싶다") == "혼자 있는 시간"
    assert one_topic("진로 선택, 공채 준비", "오늘은 쉬었다") == "진로 선택"
    assert one_topic("학업·동아리", "x") == "학업·동아리" and one_topic("", "x") == ""
    raw = {"summary": "", "addressee": "나", "events": [], "thoughts": [
        {"thought": "내 시간을 지키고 싶다", "kind": "다짐", "certainty": "단정", "value": "", "quote": "내 시간을 지키고 싶다",
         "topic": "독서노트 습관, 진로 선택, 혼자 있는 시간", "people": ""}]}
    t = clean_record(raw, topics={"독서노트 습관": "배움", "혼자 있는 시간": "관계"})["thoughts"][0]
    assert (t["topic"], t["domain"]) == ("혼자 있는 시간", "관계")


def test_two_domain_profile_maps_axes(monkeypatch):
    """두 영역 모드(10/28 멘토링): 고른 기준 축을 커리어 · 인간관계로 묶고 나머지는 '그 밖'(우주에 안 띄움)."""
    from app.core import config
    from app.service.rules import to_sun
    assert to_sun("미래 안정") == "미래 안정"   # 꺼져 있으면 그대로(지금 운영)
    monkeypatch.setattr(config, "ONTOLOGY_PROFILE", "two")
    assert [to_sun(d) for d in ("삶의 성취", "미래 안정", "관계", "공동체", "건강", "커리어", "통일 사역")] == \
        ["커리어", "커리어", "인간관계", "인간관계", "그 밖", "커리어", "통일 사역"]
    shown = sun_list([{"domain": "커리어"}, {"domain": "그 밖"}])
    assert shown == {"shown": ["커리어"], "hidden": ["인간관계"]}
    assert match_topic("커리어", {}) == ("커리어", "해 이름")   # 모드의 해 이름도 주제가 아니다


def test_join_star_uses_nearest_star_center():
    from app.service.rules import join_star
    pool = {"s1": [[1.0, 0.0], [0.9, 0.1]], "s2": [[0.0, 1.0]]}
    assert join_star([1.0, 0.05], pool, tau=0.9) == "s1"
    assert join_star([0.7, 0.7], pool, tau=0.9) is None   # 어느 별과도 충분히 가깝지 않으면 새 별
    assert join_star([1.0, 0.0], pool, tau=None) is None  # 끄면 이름으로만


def test_insight_groups_by_sun_and_star_with_quotes(monkeypatch):
    """나에 대해 알게 된 것: 해 → 작은 별, 이어 온 · 바뀐 · 맞서는(풀린 것 빼고) · 해를 넘는 관계. 원문 인용만, 판정 없음."""
    from app.core import config
    from app.service.rules import insight
    from app.service.rules.insight import _end
    monkeypatch.setattr(config, "ONTOLOGY_PROFILE", "two")
    T = lambda i, rec, day, topic, dom, kind="해석": {  # noqa: E731
        "id": i, "record_id": rec, "day": day, "topic": topic, "domain": dom, "kind": kind, "quote": f"{i} 인용"}
    ts = {t["id"]: t for t in [T("a", "r1", "2026-08-01", "회사 고르기", "커리어"), T("b", "r2", "2026-09-01", "회사 고르기", "커리어"),
                               T("c", "r3", "2026-10-01", "회사 고르기", "커리어"), T("d", "r2", "2026-09-01", "부모님", "인간관계"),
                               T("e", "r4", "2026-09-05", "산책", "그 밖")]}
    rels = [{"type": "이어짐", "from": "a", "to": "b"}, {"type": "바뀜", "from": "a", "to": "c", "line": "실선"},
            {"id": "b>d", "type": "긴장", "from": "b", "to": "d", "line": "점선"}]
    out = insight(ts, rels)
    assert out["period"] == {"from": "2026-08-01", "to": "2026-10-01", "records": 4}
    career, people = out["suns"]
    assert [s["name"] for s in out["suns"]] == ["커리어", "인간관계"]   # '그 밖'은 빠짐
    assert career["stars"][0] == {"name": "회사 고르기", "records": 3, "first": "2026-08-01", "last": "2026-10-01",
                                  "kinds": {"해석": 3}}
    assert career["kept"][0]["times"] == 1 and career["changed"][0]["to"]["quote"] == "c 인용"
    assert out["across"] == [{"type": "긴장", "suns": ["커리어", "인간관계"], "from": _end(ts["b"]),
                              "to": _end(ts["d"]), "rid": "b>d", "line": "점선"}]   # 카드에서 맞아요 · 아니에요를 누를 관계 id


def test_insight_resolution_closes_only_the_earlier_side():
    """해소는 먼저 쓴(열려 있던) 생각만 닫는다. 결론이 나중에 다른 생각과 맞서면 그 긴장은 열려 있다."""
    from app.service.rules import insight
    T = lambda i, day: {"id": i, "record_id": f"r{i}", "day": day, "topic": "이직", "domain": "미래 안정", "kind": "해석",  # noqa: E731
                        "quote": i}
    ts = {i: T(i, d) for i, d in (("x", "2026-08-01"), ("y", "2026-08-02"), ("z", "2026-09-01"), ("w", "2026-10-01"))}
    rels = [{"type": "긴장", "from": "x", "to": "y"}, {"type": "해소", "from": "y", "to": "z"}, {"type": "긴장", "from": "z", "to": "w"}]
    (sun,) = insight(ts, rels)["suns"]
    assert [(p["from"]["thought_id"], p["to"]["thought_id"]) for p in sun["open"]] == [("z", "w")]
