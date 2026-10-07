"""위기 감지 · 돌봄 응답 · 사람 판정 검사. 예문은 모두 지어낸 글이다."""
import json
from types import SimpleNamespace

import pytest

from app.core import llm as core_llm
from app.core.ontology import load
from app.service.safety import care_message, detect_crisis, judged, mask

CRISIS = [
    # 직접 표현
    "죽고 싶다.",
    "요즘 자꾸 죽고 싶다는 생각이 든다.",
    "자살이라는 단어가 머릿속에서 떠나지 않는다.",
    "어젯밤에 또 자해를 했다.",
    "목숨을 끊고 싶다.",
    "극단적 선택을 하고 싶다는 생각까지 했다.",
    "손목을 긋고 싶었다.",
    "옥상에서 뛰어내리고 싶다는 생각이 스쳤다.",
    "유서를 쓰다가 멈췄다.",
    "그냥 확 죽을까.",
    "뒤지고 싶다 진짜",
    # 띄어쓰기 · 맞춤법 틀림 · 줄임
    "죽 고 싶 다",
    "죽고싶다ㅠㅠ",
    "죽고시퍼",
    "자1살 하고 싶어",
    "살기싫다 진짜로",
    # 돌려 말하기
    "그냥 다 끝내고 싶어.",
    "사라지고 싶다. 아무도 모르게.",
    "내일 아침에 눈을 뜨지 않았으면 좋겠다.",
    "살고 싶지 않아.",
    "태어나지 말았어야 했는데.",
    "영원히 잠들고 싶다.",
    "사는 게 의미 없다.",
    "살아야 할 이유를 모르겠다.",
    "하나님, 저를 데려가 주세요.",
    "숙제고 뭐고 내 인생을 끝내고 싶다.",
    # 작별 · 무가치감 + 끝내고 싶음
    "나 같은 건 없는 게 나아.",
    "모두에게 짐만 되는 것 같고 더는 못 버티겠어.",
    "그동안 고마웠어. 다들 잘 있어.",
    "내가 없어지면 다들 편할 텐데. 나는 쓸모없는 사람이야.",
    "희망이 없다. 다 포기하고 싶다.",
    # 수동적 죽음 바람 · 떠난 사람 곁으로 · 돌려 말한 자해(골든셋과 다른 예문)
    "할머니 곁으로 가고 싶다는 생각만 든다.",
    "아빠, 나도 하늘나라로 가고 싶어.",
    "이대로 영영 눈 감았으면 좋겠다.",
    "다음 날 눈이 안 떠졌으면 좋겠어.",
    "자다가 그대로 안 깨어났으면 해.",
    "그냥 다 끝나 버렸으면 좋겠다.",
    "차라리 사고라도 났으면 좋겠다.",
    "어젯밤에 또 내 몸에 상처를 냈다.",
    "자꾸 나 자신을 해치고 싶어진다.",
    # 영어 섞임
    "I want to die.",
    "오늘도 kms 하고 싶은 하루",
    "suicide 생각이 계속 난다",
    "self-harm 다시 시작함",
    "그냥 end it all 하고 싶다",
    # 남 이야기 문장 속이라도 '나'가 겹치면 위기로 본다
    "영화 보다가 나도 주인공처럼 죽고 싶어졌다.",
    "친구한테 말은 못 했지만 나는 요즘 죽고 싶다고 생각한다.",
]

NOT_CRISIS = [
    # 관용 표현
    "배고파 죽겠다.",
    "웃겨 죽겠네 ㅋㅋㅋ",
    "이 떡볶이 죽을 만큼 맛있다.",
    "과제가 날 죽인다.",
    "더워 죽겠다.",
    "피곤해 죽을 것 같다.",
    "귀여워 죽겠어.",
    "새벽까지 게임하다 죽는 줄 알았다.",
    "축구하다가 자살골을 넣었다.",
    "과제 다 끝내고 싶다.",
    "이번 프로젝트 빨리 끝내고 싶다.",
    "유서 깊은 성당을 구경했다.",
    "숙제 포기하고 싶다.",
    "고향 집 떠나면서 강아지한테 잘 있어 하고 인사했다.",
    "졸려서 눈 감고 싶다.",
    "기말고사가 다 끝났으면 좋겠다.",
    "이 장마가 그냥 끝났으면 좋겠다.",
    "아이가 넘어져서 무릎에 상처가 났다.",
    "할아버지 산소에 다녀왔다.",
    "무슨 일이라도 생기면 꼭 연락해.",
    # 남 이야기 · 뉴스 · 영화 · 교육
    "뉴스에서 청년 자살률이 높다는 기사를 봤다.",
    "자살예방 교육을 들었다.",
    "영화 주인공이 자살하는 장면이 너무 슬펐다.",
    "드라마 줄거리: 주인공이 생을 마감하려다 구조된다.",
    "소설 속 등장인물이 사라지고 싶다고 말한다.",
    "친구가 죽고 싶다고 해서 마음이 쓰였다.",
    "수업 시간에 자해 예방에 대해 배웠다.",
    "그 노래 가사는 '영원히 잠들고 싶어'로 시작한다.",
    # 평범한 날
    "오늘은 정말 행복했다. 하늘이 맑았다.",
    "시험 망해서 짜증난다.",
]


@pytest.mark.parametrize("text", CRISIS)
def test_crisis_detected(text):
    r = detect_crisis(text)
    assert r["crisis"] and r["signals"], text


@pytest.mark.parametrize("text", NOT_CRISIS)
def test_not_crisis(text):
    assert detect_crisis(text) == {"crisis": False, "signals": []}, text


def test_counts():
    assert len(CRISIS) >= 30 and len(NOT_CRISIS) >= 20


def test_crisis_in_long_diary():
    diary = "아침에 수업을 들었다. 점심은 학식. 오후엔 동아리 모임.\n밤에 혼자 있으니 그냥 다 끝내고 싶다는 생각이 들었다."
    assert detect_crisis(diary)["crisis"]


def test_one_weak_signal_is_not_enough():
    assert not detect_crisis("더는 못 버티겠다 싶을 만큼 바빴다.")["crisis"]


# 금지 낱말: 방법 · 장소
METHOD_PLACE = ["약을", "수면제", "번개탄", "투신", "옥상", "한강", "다리", "칼", "끈", "목을", "높은 곳", "철로", "선로", "가스"]


@pytest.mark.parametrize("tone", [None, "다정하게", "담백하게", "고양이처럼", "팩폭"])
def test_care_message(tone):
    m = care_message(tone)
    assert "109" in m and "마들랜" in m and "24시간" in m
    assert "안전" in m and "?" in m          # 안전 여부를 직접 묻는다
    assert [w for w in METHOD_PLACE if w in m] == []
    assert "냥" not in m and "야," not in m   # 말투와 상관없이 같은 돌봄 글
    assert m == care_message()


def test_care_message_without_resources_keeps_care_drops_details():
    """API 결과의 care.message: 109 · 마들랜 자세한 안내는 아래 단추(care.resources)와 겹쳐 빼고, 단추를 가리키는 한 줄만."""
    full, short = care_message(), care_message("팩폭", resources=False)
    assert care_message(resources=True) == full and "카카오톡" in full and "문자를 보내도" in full
    assert "카카오톡" not in short and "문자를 보내도" not in short and "365일" not in short
    assert "안전" in short and "?" in short and "119" in short and "아래 단추" in short   # 안전 질문 · 긴급 번호는 남는다
    assert [w for w in METHOD_PLACE if w in short] == []
    assert short.count("\n") == full.count("\n") - 1


def test_care_message_matches_ontology_resources():
    m = care_message()
    for r in load()["crisis"]["resources"]:
        assert r["contact"].split()[0] in m or "마들랜" in r["contact"]
        assert r["name"].split()[-1] in m


@pytest.mark.parametrize("text", ["글쓴이는 의지가 약한 사람이다", "너는 원래 게으른 사람이야", "넌 진짜 회피하는 타입이야",
                                  "이건 우울증 같아요", "공황장애가 있는 것 같네요", "넌 늘 그런 식인 애야",
                                  "당신은 원래 겁이 많은 성격이군요"])
def test_judged(text):
    assert judged(text)


@pytest.mark.parametrize("text", ["다짐이 두 번 나왔고, 이후 반성이 한 번 나왔다.", "수영 3주째 안 갔다. 핑계 그만.",
                                  "이번 주도 바빴죠. 내일 10분만 해 볼까요?"])
def test_not_judged(text):
    assert not judged(text)


# --- 2단 판정: 규칙이 놓친 글만 Solar 로(가짜 클라이언트) ---

PEOPLE = [{"name": "윤서진", "nicknames": ["서진", "진이"], "relation": "언니"}, {"name": "도담", "relation": "친구"}]
QUIET = "서진 언니한테 전화했다. 도담이랑 진이 얘기도 했는데 요즘 다 귀찮고 기운이 없다."   # 규칙은 위기 아님


@pytest.fixture
def client(monkeypatch):
    """llm.client() 자리에 가짜. sent 에 실제로 나갈 요청(kwargs)이 쌓인다."""
    st = {"sent": [], "answer": '{"crisis": true, "reason": "기운이 없고 다 귀찮음"}'}

    def create(**kw):
        st["sent"].append(kw)
        if isinstance(st["answer"], Exception):
            raise st["answer"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=st["answer"]))])

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(core_llm, "client", lambda: fake)
    return st


def test_default_is_rules_only(client):
    assert detect_crisis(QUIET) == {"crisis": False, "signals": []}
    assert detect_crisis(QUIET, people=PEOPLE) == {"crisis": False, "signals": []}
    assert client["sent"] == []


def test_rules_hit_skips_llm(client):
    assert detect_crisis("죽고 싶다.", people=PEOPLE, llm=True)["crisis"] and client["sent"] == []


def test_llm_second_stage(client):
    r = detect_crisis(QUIET, people=PEOPLE, llm=True)
    assert r == {"crisis": True, "signals": [{"type": "llm", "match": "기운이 없고 다 귀찮음"}]}
    client["answer"] = '{"crisis": false, "reason": "피곤함"}'
    assert detect_crisis(QUIET, people=PEOPLE, llm=True) == {"crisis": False, "signals": []}
    assert len(client["sent"]) == 2 and client["sent"][0]["temperature"] == 0


def test_payload_has_no_real_names(client):
    detect_crisis(QUIET, people=PEOPLE, llm=True)
    raw = json.dumps(client["sent"], ensure_ascii=False)
    assert [t for p in PEOPLE for t in [p["name"], *p.get("nicknames", [])] if t in raw] == []
    assert "전화했다" in raw                                   # 이름 말고는 그대로 보낸다


def test_payload_hides_new_names_without_people(client):
    detect_crisis("민혁이가 연락했는데 답을 못 했다. 기운이 없다.", llm=True)
    assert client["sent"] and "민혁" not in json.dumps(client["sent"], ensure_ascii=False)


def test_llm_answer_with_broken_json(client):
    # Solar 가 reason 안에 따옴표를 그대로 넣어 JSON 이 깨진 실제 꼴
    client["answer"] = '{"crisis": false, "reason": "기운 없다"는 피로 표현}'
    assert detect_crisis(QUIET, people=PEOPLE, llm=True) == {"crisis": False, "signals": []}
    client["answer"] = '{"crisis": true, "reason": "다 귀찮음"이 오래감}'
    assert detect_crisis(QUIET, people=PEOPLE, llm=True)["signals"] == [{"type": "llm", "match": '다 귀찮음"이 오래감'}]


def test_llm_reason_is_unmasked(client):
    _, table = mask(QUIET, PEOPLE)
    alias = next(k for k, v in table.items() if v == "도담")
    client["answer"] = json.dumps({"crisis": True, "reason": f"{alias} 얘기 뒤 무기력"}, ensure_ascii=False)
    assert detect_crisis(QUIET, people=PEOPLE, llm=True)["signals"][0]["match"] == "도담 얘기 뒤 무기력"


@pytest.mark.parametrize("bad", [RuntimeError("network down"), "잘 모르겠어요", '{"crisis": "yes"}'])
def test_llm_error_falls_back_to_rules(client, bad):
    client["answer"] = bad
    r = detect_crisis(QUIET, people=PEOPLE, llm=True)
    assert r["crisis"] is False and [s["type"] for s in r["signals"]] == ["llm_error"]
    assert r["signals"][0]["match"] in ("RuntimeError", "ValueError")   # 원문 · 오류 글 없이 종류 이름만
