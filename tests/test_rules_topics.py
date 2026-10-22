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
