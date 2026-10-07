"""목록 밖 값 세 갈래 · 생각 표 정리(강조어 · 감사 · 사람 칸 · 주제 칸)."""
import pytest

from app.core.ontology import is_valid
from app.service.rules import clean_record, normalize, other_candidates, people_of


@pytest.mark.parametrize("field,raw,want", [
    ("kind", "다짐", ("다짐", None)),                       # 목록 안
    ("kind", ["신념 · 원칙"], ("신념·원칙", None)),           # 배열 · 띄어쓰기
    ("kind", "반성", ("자기평가(부정)", None)),               # 비슷한 말 → 바로잡음
    ("kind", "아쉬웠던 점", ("자기평가(부정)", None)),         # 화면 이름
    ("certainty", "질문", ("판단 보류", None)),
    ("certainty", "확실함", ("단정", None)),
    ("value", "Self-direction", ("자율", None)),            # Schwartz 이름
    ("value", "", ("", None)),                               # 가치는 비움 허용
    ("addressee", "주님", ("신", None)),
    ("type", "성찰", ("생각·성찰", None)),
])
def test_normalize_fixes_one_meaning(field, raw, want):
    assert normalize(field, raw) == want


@pytest.mark.parametrize("field,raw", [("value", "성장"), ("kind", "깨달음"), ("certainty", "글쎄")])
def test_normalize_ambiguous_goes_to_other_with_original(field, raw):
    assert normalize(field, raw) == ("기타", raw)


def test_normalize_rejects_open_fields():
    with pytest.raises(KeyError):
        normalize("topic", "진로")


def test_other_candidates_counts_frequent_originals():
    items = [{"original": {"value": "성장"}}, {"original": {"value": "성장"}}, {"original": {"kind": "맺음말"}}, {}]
    assert other_candidates(items) == [{"field": "value", "original": "성장", "count": 2},
                                       {"field": "kind", "original": "맺음말", "count": 1}]


def test_people_of_maps_nickname_and_reports_new():
    book = [{"name": "김민수", "nicknames": ["민수"], "relation": "친구"}]
    assert people_of("민수, 지은", book) == (["김민수", "지은"], ["지은"])
    assert people_of([], book) == ([], [])


RAW = {"summary": ["요약"], "addressee": ["하나님"], "events": ["회의함", ""],
       "thoughts": [
           {"thought": "정말 어느 쪽이 맞는지 모르겠다.", "kind": "질문", "certainty": "단정", "quote": "정말 모르겠다",
            "topic": "진 로", "value": "성장", "people": ""},
           {"thought": "진짜 작은 팀이 나답다.", "kind": "신념", "certainty": "단정", "quote": "작은 팀이 나답다",
            "topic": "진로", "value": "자율"},
           {"thought": "이삿짐을 날라 준 민수가 고마웠다.", "kind": "감정", "certainty": "단정", "quote": "민수가 고마웠다",
            "topic": "관계", "value": "배려", "people": ["민수"]},
           {"thought": "비가 와서 가라앉았다.", "kind": "감정", "certainty": "단정", "quote": "가라앉았다",
            "topic": "마음 건강", "value": ""},
       ]}


def test_clean_record():
    out = clean_record(RAW, people=[{"name": "김민수", "nicknames": ["민수"]}], topics={"진로": "삶의 성취"})
    t1, t2, t3, t4 = out["thoughts"]
    assert out["addressee"] == "신" and out["summary"] == "요약" and out["events"] == ["회의함"]
    # 강조어 + 미정 표현 → 단정 아님 / 강조어만 있으면 단정 유지(금지 사례)
    assert t1["certainty"] == "판단 보류" and t2["certainty"] == "단정"
    # 주제: 띄어쓰기만 다르면 기존 이름, 목록 밖 가치는 기타 + 원래 말
    assert t1["topic"] == "진로" and t1["domain"] == "삶의 성취"
    assert t1["value"] == "기타" and t1["original"] == {"value": "성장"}
    assert t2["kind"] == "신념·원칙"
    # 감정 + 고마움 → 감사 표시 / 고마움 없는 감정에는 없음
    assert t3["flags"] == ["감사"] and t4["flags"] == []
    assert t3["people"] == ["김민수"] and out["new_people"] == []
    # 해 이름 주제는 고칠 수 없으면 표시해서 돌려줌
    assert t3["problems"] == ["해 이름"] and t4["problems"] == []
    assert t4["domain"] == "건강"
    for t in out["thoughts"]:
        assert is_valid("kinds", t["kind"]) and is_valid("certainty", t["certainty"])
