"""다음 질문 고르기 규칙(LLM 없음)."""
from app.core.ontology import load
from app.service.voice import base_question, next_question_kind as kind

LONG = "오늘은 수업을 듣고 도서관에 갔다. " * 20


def test_first_meeting_asks_weather_then_first_question():
    assert kind({"days_written": 0, "text": "첫 글"}) == "weather"
    assert kind({"days_written": 0, "text": "첫 글", "weather_skipped": True}) == "first"
    assert kind({"days_written": 0, "weather": "맑음"}) == "first"


def test_weather_only_when_mood_hidden():
    short = "수업 듣고 밥 먹음."
    A = {"aspiration": {"said": "x"}}   # 되고 싶은 모습은 이미 있음(초대 질문이 끼지 않게)
    assert kind({**A, "days_written": 4, "text": short}) == "weather"                    # 짧고 감정 없음
    assert kind({**A, "days_written": 4, "text": short, "thoughts": [{"kind": "감정"}]}) == ""   # 감정이 드러남
    assert kind({**A, "days_written": 4, "text": LONG}) == ""                             # 긴 글
    assert kind({**A, "days_written": 4, "text": short, "weather": "흐림"}) == ""         # 이미 고름
    assert kind({**A, "days_written": 4, "text": short, "weather_skipped": True}) == ""   # 건너뛰면 다음엔 안 물음


def test_weather_question_from_ontology():
    q = base_question("weather", {})
    assert all(w["name"] in q and all(x in q for x in w["words"]) for w in load()["weather"])


def test_aspiration_steps_in_order():
    steps = load()["aspiration"]["ask_steps"]
    for i, s in enumerate(steps):
        c = {"days_written": 5, "text": LONG, "aspiration_step": i}
        assert kind(c) == "aspiration" and base_question("aspiration", c) == s["question"]
    assert kind({"days_written": 5, "text": LONG, "aspiration_step": len(steps), "aspiration": {"said": "x"}}) == ""   # 4단계 끝
    assert kind({"days_written": 5, "text": LONG, "aspiration_step": 1, "aspiration_off": True}) == ""


def test_aspiration_invite_after_some_days_only():
    assert kind({"days_written": 1, "text": LONG}) == ""                              # 첫 대화에서 바로 묻지 않음
    assert kind({"days_written": 3, "text": LONG}) == "aspiration_invite"
    assert kind({"days_written": 3, "text": LONG, "aspiration_off": True}) == ""      # 그만 묻기
    assert kind({"days_written": 3, "text": LONG, "aspiration": {"said": "x"}}) == ""  # 이미 있음


def test_commitment_and_open_question():
    c = {"days_written": 5, "text": LONG, "aspiration": {"said": "x"}}
    assert kind({**c, "commitments": [{"text": "메일 보내기", "state": "열림", "overdue": True}]}) == "commitment"
    assert kind({**c, "commitments": [{"text": "메일 보내기", "state": "열림"}]}) == ""
    assert kind({**c, "open_questions": ["어디서 일하고 싶지?"]}) == "open_question"


def test_heavy_day_and_crisis_no_question():
    c = {"days_written": 0, "text": "첫 글"}
    assert kind({**c, "weather": "비"}) == "" and kind({**c, "heavy": True}) == ""
    assert kind({**c, "crisis": True}) == ""
    assert kind({**c, "settings": {"comfort_only": True}}) == ""


def test_first_question_not_repeated():
    q1 = base_question("first", {})
    assert base_question("first", {"past_messages": [q1]}) != q1
