"""가명 처리 · 새 이름 찾기 · 사람 지우기. 사람과 예문은 모두 지어낸 가상 인물이다."""
import re

import pytest

from app.service.safety import RealNameLeak, assert_no_real_names, find_new_names, forget, mask, unmask
from app.service.safety.pseudonym import POOL, _cls

PEOPLE = [
    {"name": "민준", "nicknames": ["준이"], "relation": "선배"},
    {"name": "지수", "nicknames": ["곰돌이"], "relation": "룸메이트"},
    {"name": "한별", "nicknames": [], "relation": "친구"},
    {"name": "서연", "nicknames": ["연이"], "relation": "동생"},
    {"name": "박도현", "nicknames": ["도현"], "relation": "팀원"},
    {"name": "Alex", "nicknames": [], "relation": "교환학생"},
]
REAL = [t for p in PEOPLE for t in [p["name"], *p["nicknames"]]]

ROUND_TRIP = [
    "민준이가 먼저 물어봐 줬다.",
    "민준 선배랑 밥을 먹었다.",
    "민준 형이랑 산책했다.",
    "민준이는 오늘도 늦었다.",
    "민준이한테 고맙다고 말하지 못했다.",
    "준이가 커피를 사 줬다.",
    "준이랑 같이 도서관에 갔다.",
    "지수가 빨래를 개 줬다.",
    "지수야, 고마워.",
    "지수는 요즘 바쁘다.",
    "지수를 기다리다가 잠들었다.",
    "지수와 다퉜다.",
    "곰돌이가 또 내 과자를 먹었다.",
    "곰돌이랑 영화를 봤다.",
    "한별이 웃었다.",
    "한별이랑 동아리방에 있었다.",
    "한별로부터 연락이 왔다.",
    "한별아, 내일 보자.",
    "한별의 말이 오래 남았다.",
    "서연이 생일이라 케이크를 샀다.",
    "서연 씨에게 메일을 보냈다.",
    "서연과 함께 발표를 준비했다.",
    "연이가 전화했다.",
    "박도현 님이 회의를 이끌었다.",
    "도현 씨는 꼼꼼하다.",
    "도현이랑 마감 때문에 밤을 샜다.",
    "Alex랑 영어로 이야기했다.",
    "민준이랑 지수가 같이 왔고, 한별은 늦었다.",
    "서연 쌤한테 혼났다. 지수한테 털어놨다.",
    "곰돌이가 준이랑 싸웠다.",
    "수빈이가 짚어 줬다. 태호 형이랑 밥을 먹었다.",
    "오늘은 혼자 있었다. 아무도 만나지 않았다.",
    "다가온 시험 때문에 서아처럼 조용히 공부했다.",   # 가명 풀의 말이 이미 글에 있어도 왕복된다
]


def test_round_trip_count():
    assert len(ROUND_TRIP) >= 30


@pytest.mark.parametrize("text", ROUND_TRIP)
def test_round_trip(text):
    masked, table = mask(text, PEOPLE)
    assert unmask(masked, table) == text
    assert_no_real_names(masked, PEOPLE)
    assert not any(n in masked for n in ["수빈", "태호"])   # 목록에 없는 새 이름 후보도 가린다


def test_same_class_pseudonym_keeps_particles():
    masked, table = mask("민준이가 왔다. 지수는 갔다. 한별로 정했다.", PEOPLE)
    for p, real in table.items():
        assert _cls(p) == _cls(real)
    assert re.fullmatch(r"\w+이가 왔다\. \w+는 갔다\. \w+로 정했다\.", masked)


def test_same_person_same_pseudonym():
    masked, table = mask("민준이가 왔다. 민준 선배는 웃었다.", PEOPLE)
    assert len(table) == 1 and masked.count(next(iter(table))) == 2


def test_unmask_after_ai_changes_particles():
    masked, table = mask("민준이가 먼저 물어봐 줬다.", PEOPLE)
    p = next(k for k, v in table.items() if v == "민준")
    reply = f"{p}은 먼저 다가갔어요. {p}과 이야기한 날이네요."   # 외부 AI가 조사를 바꿔 붙임
    assert unmask(reply, table) == "민준은 먼저 다가갔어요. 민준과 이야기한 날이네요."


def test_pseudonyms_avoid_words_in_text():
    text = "서아와 도윤과 다솔이라는 낱말이 들어간 글. 민준이 왔다. 한별이 웃었다. 지수도 왔다."
    masked, table = mask(text, PEOPLE)
    assert not ({"서아", "도윤", "다솔"} & set(table))
    assert unmask(masked, table) == text


def test_many_people_do_not_run_out():
    people = [{"name": f"가{chr(0xAC00 + 28 * i + 4)}", "relation": "친구"} for i in range(30)]   # 받침 ㄴ 이름 30명
    text = " ".join(p["name"] + "이가 왔다." for p in people)
    masked, table = mask(text, people)
    assert len(table) == 30 and unmask(masked, table) == text
    assert_no_real_names(masked, people)


##################################################
# 외부 요청에 실명 0건
##################################################

def test_fake_external_flow_has_no_real_names():
    sent = []
    pool = [n for ns in POOL.values() for n in ns]

    def fake_solar(payload):   # 가짜 외부 클라이언트: 받은 것을 적어 두고, 가명에 조사를 바꿔 붙여 답한다
        sent.append(payload)
        content = payload["messages"][-1]["content"]
        people = [n for n in pool if n in content]
        return {"summary": content.replace("이랑", "와"), "people": people}

    for text in ROUND_TRIP:
        masked, table = mask(text, PEOPLE)
        payload = {"messages": [{"role": "system", "content": "일기를 요약해 줘."}, {"role": "user", "content": masked}],
                   "meta": {"people": list(table)}}
        assert_no_real_names(payload, PEOPLE)
        reply = fake_solar(payload)
        summary = unmask(reply["summary"], table)
        assert [unmask(p, table) for p in reply["people"]] == [table.get(p, p) for p in reply["people"]]
        assert any(r in summary for r in REAL) == any(r in text for r in REAL)

    leaked = [r for payload in sent for r in REAL if r in repr(payload)]
    assert leaked == [] and len(sent) == len(ROUND_TRIP)


@pytest.mark.parametrize("payload", [
    "지수가 왔다",
    {"messages": [{"role": "user", "content": "곰돌이랑 놀았다"}]},
    {"inputs": {"people": ["서아", "민준"]}},
    ["괜찮다", ("Alex",)],
    {"민준": 1},
])
def test_assert_no_real_names_raises(payload):
    with pytest.raises(RealNameLeak) as e:
        assert_no_real_names(payload, PEOPLE)
    assert not any(r in str(e.value) for r in REAL)   # 예외 글에도 실명을 넣지 않는다


def test_assert_no_real_names_passes_clean_payload():
    assert_no_real_names({"messages": [{"role": "user", "content": "서아가 왔다"}], "n": 3}, PEOPLE)


##################################################
# 새 이름 찾기
##################################################

def test_find_new_names_auto():
    r = find_new_names("수빈이가 짚어 줬다. 태호 형이랑 밥을 먹었다. 민준이가 웃었다.", PEOPLE)
    assert r == {"auto": ["수빈", "태호"], "ask": []}


@pytest.mark.parametrize("text", ["오후에 선배랑 카페에 갔다.", "졸업한 선배를 만났다.", "학교 선배랑 이야기했다.",
                                  "고양이가 울었다.", "아저씨가 길을 알려 줬다.", "마음이 무겁다.", "하나님, 감사합니다.",
                                  "서아이가 왔다."])
def test_find_new_names_not_names(text):
    assert find_new_names(text, PEOPLE) == {"auto": [], "ask": []}


def test_find_new_names_ask():
    people = [{"name": "김서윤", "relation": "선배"}, {"name": "지수", "relation": "사촌"},
              {"name": "지수", "relation": "동아리 친구"}]
    r = find_new_names("하늘이가 놀러 왔다. 서윤이가 연락했다. 지수랑 밥을 먹었다.", people)
    assert r["auto"] == []
    assert sorted((a["name"], a["reason"]) for a in r["ask"]) == [
        ("서윤", "별명"), ("지수", "동명이인"), ("하늘", "이름인지 낱말인지")]


def test_mask_hides_ask_candidates():
    masked, table = mask("하늘이가 놀러 왔다.", [])
    assert "하늘" not in masked and unmask(masked, table) == "하늘이가 놀러 왔다."


##################################################
# 사람 지우기
##################################################

@pytest.mark.parametrize("text,person,want", [
    ("민준이랑 밥 먹었다. 준이가 계산했다.", PEOPLE[0], "선배랑 밥 먹었다. 선배가 계산했다."),
    ("민준이는 웃었고 민준을 따라 나도 웃었다.", PEOPLE[0], "선배는 웃었고 선배를 따라 나도 웃었다."),
    ("지수는 늘 먼저 물어봐 준다. 지수를 만났다.", {"name": "지수", "relation": "동생"}, "동생은 늘 먼저 물어봐 준다. 동생을 만났다."),
    ("민수 형이랑 걸었다. 민수가 웃었다.", {"name": "민수", "relation": "친구"}, "친구랑 걸었다. 친구가 웃었다."),
    ("한별과 이야기했다. 한별이 울었다.", PEOPLE[2], "친구와 이야기했다. 친구가 울었다."),
    ("하은이를 데리러 갔다. 하은으로 정했다.", {"name": "하은", "relation": "막내딸"}, "막내딸을 데리러 갔다. 막내딸로 정했다."),
    ("서연 씨에게 메일을 보냈다.", PEOPLE[3], "동생에게 메일을 보냈다."),
    ("오늘은 혼자 있었다.", PEOPLE[0], "오늘은 혼자 있었다."),
])
def test_forget(text, person, want):
    assert forget(text, person) == want


##################################################
# 왕복 일치 우선: 말 꼴마다 되돌릴 수 있는 가명(골든셋과 다른 인물 · 예문)
##################################################

@pytest.mark.parametrize("text,person", [
    ("서진 선배가 도와줬다. 윤서진 선배 덕분이다.", {"name": "윤서진", "nicknames": ["서진"], "relation": "선배"}),
    ("온온이가 웃었다. 다온을 꼭 안아 줬다.", {"name": "다온", "nicknames": ["온온이"], "relation": "딸"}),
    ("유리 언니가 왔다. 꼬미가 반겼다. 유리는 꼬미를 안았다.", {"name": "유리", "nicknames": ["꼬미"], "relation": "언니"}),
])
def test_round_trip_name_and_nickname(text, person):
    masked, table = mask(text, [person])
    assert unmask(masked, table) == text
    assert_no_real_names(masked, [person])


def test_surname_pseudonym_follows_given_name():
    person = {"name": "윤서진", "nicknames": ["서진"], "relation": "선배"}
    masked, table = mask("윤서진 선배와 서진 선배.", [person])
    inv = {v: k for k, v in table.items()}
    assert len(inv["윤서진"]) == 3 and inv["윤서진"][1:] == inv["서진"] and inv["윤서진"][0] != "윤"
    back = unmask(" / ".join(f"{k}에게 고마움" for k in table), table)   # 외부 AI가 가명으로 새 문장을 써도 되돌아온다
    assert not any(k in back for k in table) and all(v in back for v in table.values())


def test_loose_new_name_with_particle_is_hidden():
    text = "유나가 같이 밥 먹자고 연락했다. 유나는 늘 다정하다. 세라한테 고맙다고 했다."
    masked, table = mask(text, [])
    assert "유나" not in masked and "세라" not in masked and unmask(masked, table) == text
    assert {"유나", "세라"} <= {a["name"] for a in find_new_names(text, [])["ask"]}


@pytest.mark.parametrize("text", ["버스가 늦게 와서 친구한테 연락했다.", "아무도 연락하지 않았다.", "이모가 전화했다.",
                                  "커피는 식었고 동료랑 웃었다.", "우유가 떨어져서 사러 갔다가 이웃을 만났다.",
                                  "나무가 예뻐서 엄마한테 보냈다. 엄마가 웃었다."])
def test_loose_skips_common_words(text):
    assert find_new_names(text, PEOPLE) == {"auto": [], "ask": []}


##################################################
# 등록 안 된 이름(M1): 과 · 영문 · 조사 없이 행동 낱말 앞. 골든셋 · heldout 과 다른 가상 문장
##################################################

@pytest.mark.parametrize("text,name", [
    ("지훈과 저녁에 통화하다가 웃었다.", "지훈"),
    ("지난주 서준 만났다.", "서준"),
    ("한유진 생일이라 꽃을 샀다.", "한유진"),
    ("수아 카톡이 늦게 왔다.", "수아"),
    ("Lucas랑 점심 먹었다.", "Lucas"),
    ("Olivia 생일 선물을 샀다.", "Olivia"),
    ("Noah를 만나서 얘기했다.", "Noah"),
    ("은호한테 우산을 빌렸다.", "은호"),
])
def test_unregistered_names_are_hidden(text, name):
    masked, table = mask(text, [])
    assert name not in masked and unmask(masked, table) == text
    assert name in [a["name"] for a in find_new_names(text, [])["ask"]]


@pytest.mark.parametrize("text", ["시험 기간이랑 겹쳐서 힘들었다.", "공원이랑 시장을 걸었다.", "Youtube에서 강의를 봤다.",
                                  "그 문제에 대해 이야기했다.", "숙제 하다가 연락했다.", "버스 정류장 근처 카페에 갔다."])
def test_common_words_are_not_new_names(text):
    assert find_new_names(text, []) == {"auto": [], "ask": []}


def test_ambiguous_particle_registers_only_name_like_words():
    assert find_new_names("준혁이랑 밥 먹었다.", [])["auto"] == ["준혁"]
    r = find_new_names("학원이랑 연락이 안 됐다.", [])   # 이름답지 않은 말 + 행동 낱말 → 묻기만(자동 등록 ✗)
    assert r["auto"] == [] and [a["name"] for a in r["ask"]] == ["학원"]


##################################################
# 직함 · 직분이 붙은 이름(민석 팀장님 · 지원 집사님). 사람 목록에 없어도 가명으로 가야 한다
##################################################

@pytest.mark.parametrize("text,name", [
    ("민석 팀장님이 숫자를 다시 보자고 했다.", "민석"),
    ("고민석 팀장님이 칭찬했다.", "고민석"),
    ("오늘 민석 과장님한테 혼났다.", "민석"),
    ("준호 대리가 자료를 넘겨줬다.", "준호"),
    ("수현 부장님께 보고했다.", "수현"),
    ("정우 집사님과 기도 모임을 했다.", "정우"),
    ("혜진 간사님이 밥을 사 주셨다.", "혜진"),
])
def test_titled_names_are_hidden(text, name):
    assert name in find_new_names(text, [])["auto"]
    masked, table = mask(text, [])
    assert name not in masked and unmask(masked, table) == text


@pytest.mark.parametrize("text", ["오늘 이사했다.", "다음 주에 이사 간다.", "주일 대표 기도를 맡았다.", "영업 팀장이 바뀌었다.",
                                  "회의 끝나고 팀장님께 말했다.", "정말 간사해서 싫다.", "담임 목사님 설교가 길었다."])
def test_titles_without_names(text):
    assert find_new_names(text, []) == {"auto": [], "ask": []}


def test_forget_drops_title_with_name():
    person = {"name": "고민석", "nicknames": ["민석"], "relation": "팀장"}
    assert forget("민석 팀장님이 칭찬했다. 고민석 팀장님은 말이 짧다.", person) == "팀장이 칭찬했다. 팀장은 말이 짧다."
