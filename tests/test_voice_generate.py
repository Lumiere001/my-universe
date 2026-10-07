"""말 걸기 생성(WS7) 검사. LLM은 가짜로 바꿔 규칙 · 검사 로직만 본다."""
import json

import pytest

from app.core.ontology import load
from app.service import voice
from app.service.voice import checks

TEXT = "지난주에 팀 세 곳을 찾아보기로 했는데 바쁘다는 핑계로 또 미뤘다. 피곤해서 오늘도 못 했다."


@pytest.fixture
def fake(monkeypatch):
    """답을 차례로 돌려주는 가짜 chat. calls 에 받은 messages 가 쌓인다."""
    st = {"answers": [], "calls": []}

    def chat(messages, **kw):
        st["calls"].append(messages)
        a = st["answers"].pop(0) if len(st["answers"]) > 1 else st["answers"][0]
        return json.dumps(a, ensure_ascii=False) if isinstance(a, dict) else a

    monkeypatch.setattr(voice.llm, "chat", chat)
    return st


def ctx(**kw):
    base = {"tone": "팩폭", "text": TEXT, "summary": "팀 찾기를 또 미룬 날", "days_written": 5,
            "thoughts": [{"thought": "또 미뤘다", "kind": "자기평가(부정)", "quote": "또 미뤘다"},
                         {"thought": "실망스럽다", "kind": "감정"}],
            "weather": "구름 조금", "aspiration": {"said": "약속을 지키는 사람이 되고 싶다"}}
    base.update(kw)
    return base


def sys_prompt(st, i=0):
    return st["calls"][i][0]["content"]


# --- 팩폭: 넘지 않는 선 ---

def test_fact_bomb_hits_behavior_ok(fake):
    fake["answers"] = [{"message": "야, 팀 찾기 또 미뤘다. '바쁘다는 핑계'만 반복이고. 오늘 한 곳, 메일 하나 보내.",
                        "next_question": ""}]
    r = voice.generate(ctx())
    assert r["message"].startswith("야,") and r["checks"] == [{"attempt": 1, "problems": []}]
    assert len(fake["calls"]) == 1


@pytest.mark.parametrize("bad", [
    "넌 글렀어. 또 미뤘잖아.",                       # 인격
    "너는 원래 게으른 사람이야. 또 미뤘다.",          # 사람 판정
    "그렇게 미루니까 뚱뚱하지. 오늘 한 곳 찾아.",     # 외모
    "엄마 닮아서 그래. 오늘 한 곳 찾아.",            # 가족
])
def test_fact_bomb_attack_filtered_then_retry(fake, bad):
    good = {"message": "핑계 그만. '또 미뤘다'가 오늘 글이야. 오늘 한 곳 찾아.", "next_question": ""}
    fake["answers"] = [{"message": bad, "next_question": ""}, good]
    r = voice.generate(ctx())
    assert r["message"] == good["message"]
    assert r["checks"][0]["problems"] and r["checks"][1]["problems"] == []
    assert "고칠 것" in sys_prompt(fake, 1)          # 다시 만들 때 문제를 알려 준다


def test_attack_twice_falls_back_to_safe(fake):
    fake["answers"] = [{"message": "넌 글렀어.", "next_question": ""}]
    r = voice.generate(ctx())
    assert r["message"] == voice.SAFE[("팩폭", False)]
    assert len(fake["calls"]) == 2 and r["checks"][-1]["attempt"] == "기본 문장"
    assert checks.line_problems(r["message"]) == []


def test_fact_bomb_prompt_has_strength_and_lines(fake):
    fake["answers"] = [{"message": "핑계 그만. 오늘 한 곳 찾아.", "next_question": ""}]
    voice.generate(ctx())
    s = sys_prompt(fake)
    fb = load()["fact_bomb"]
    assert fb["strength"] in s and all(x in s for x in fb["never_cross"])


def test_gentle_only_for_fact_bomb(fake):
    fake["answers"] = [{"message": "오늘 한 곳만 찾아 봐.", "next_question": ""}]
    voice.generate(ctx(settings={"gentle": True}))
    assert "오늘은 살살: " in sys_prompt(fake)
    fake["calls"].clear()
    voice.generate(ctx(tone="다정하게", settings={"gentle": True}))
    assert "오늘은 살살: " not in sys_prompt(fake)


# --- 위기 ---

def test_crisis_no_llm_call(fake):
    fake["answers"] = [{"message": "x", "next_question": ""}]
    r = voice.generate(ctx(crisis=True))
    assert r["mode"] == "care" and r["message"] == "" and fake["calls"] == []
    assert voice.next_question_kind(ctx(crisis=True)) == ""


def test_crisis_method_place_filtered():
    assert checks.line_problems("옥상에 올라가지 마") and checks.line_problems("수면제")
    assert checks.line_problems("오늘 한 곳 찾아") == []


# --- 무거운 날: 제안 없음 ---

@pytest.mark.parametrize("weather", ["비", "천둥"])
def test_heavy_weather_no_suggestion(fake, weather):
    fake["answers"] = [{"message": "슬펐겠다. 내일 10분만 걸어 볼까요?", "next_question": "뭐 할래?"},
                       {"message": "슬픈 날엔 슬픈 채로 있어도 괜찮아요.", "next_question": ""}]
    r = voice.generate(ctx(tone="다정하게", weather=weather))
    assert r["mode"] == "comfort" and r["next_question"] == ""
    assert not checks.has_suggestion(r["message"])
    assert "제안 없이" in sys_prompt(fake)
    assert r["checks"][0]["problems"] == ["무거운 날인데 제안이 있음"]


def test_heavy_always_suggesting_falls_back(fake):
    fake["answers"] = [{"message": "내일 한 번만 해 볼까요?", "next_question": ""}]
    for tone in ["다정하게", "담백하게", "고양이처럼", "팩폭"]:
        r = voice.generate(ctx(tone=tone, heavy=True))
        assert r["message"] == voice.SAFE[(tone, True)] and not checks.has_suggestion(r["message"])


def test_comfort_only_button(fake):
    fake["answers"] = [{"message": "오늘 버틴 것도 한 일이에요.", "next_question": ""}]
    r = voice.generate(ctx(tone="다정하게", settings={"comfort_only": True}))
    assert r["mode"] == "comfort"


def test_clear_weather_is_normal(fake):
    fake["answers"] = [{"message": "핑계 그만. 오늘 한 곳 찾아.", "next_question": ""}]
    assert voice.generate(ctx(weather="맑음"))["mode"] == "normal"


# --- 반복 검사 ---

def test_repeat_with_past_messages(fake):
    past = ["야, 팀 찾기 또 미뤘다. 오늘 한 곳, 메일 하나 보내."]
    fake["answers"] = [{"message": "야, 팀 찾기 또 미뤘네. 오늘 한 곳, 메일 하나 보내.", "next_question": ""},
                       {"message": "세 곳 중 0곳. 숫자가 말해 준다. 오늘 저녁에 메일 하나.", "next_question": ""}]
    r = voice.generate(ctx(past_messages=past))
    assert "지난 한마디" in r["checks"][0]["problems"][0] and r["checks"][1]["problems"] == []


def test_repeat_twice_falls_back(fake):
    past = ["오늘 쓴 거 잘 봤어."]
    fake["answers"] = [{"message": "오늘 쓴 거 잘 봤어.", "next_question": ""}]
    r = voice.generate(ctx(past_messages=past))
    assert r["checks"][-1]["attempt"] == "기본 문장" and len(fake["calls"]) == 2


def test_repeat_checks_whole_history_not_just_recent():
    past = ["피곤한 게 아니라 안 간 거야. 그거 하고 얘기해."] + [f"다른 말 {i}번째입니다 정말로요." for i in range(30)]
    assert checks.repeat_problems("피곤한 게 아니라 안 간 거야. 오늘은 달라.", past)
    assert checks.repeat_problems("오늘은 메일 하나 보내고 자.", past) == []


# --- 원문 근거 ---

def test_quote_must_be_in_text(fake):
    fake["answers"] = [{"message": "'다 포기하고 싶다'라고 썼지. 핑계 그만.", "next_question": ""},
                       {"message": "'또 미뤘다'라고 썼지. 핑계 그만.", "next_question": ""}]
    r = voice.generate(ctx())
    assert r["checks"][0]["problems"] == ["원문에 없는 인용: '다 포기하고 싶다'"]
    assert r["message"].startswith("'또 미뤘다'")


def test_quote_from_reached_moment_ok():
    assert checks.quote_problems("‘약속은 지키고 싶었다’", ["오늘 글", "약속은 지키고 싶었다"]) == []
    assert checks.quote_problems("“없는 말”", ["오늘 글"])


# --- 되고 싶은 모습: 닿은 순간 인정, 거리 숫자 · 멀어짐 금지 ---

@pytest.mark.parametrize("bad", ["되고 싶은 모습에 70% 가까워졌어요.", "달성률이 올랐어요.", "오늘은 80점이에요.",
                                 "되고 싶은 모습과 거리 3 남았어요.", "오늘은 되고 싶은 모습에서 멀어졌네요."])
def test_aspiration_no_distance_or_away(bad):
    p = checks.problems(bad, "", sources=[TEXT], past=[], comfort=False, aspiration=True)
    assert p


def test_aspiration_reached_ok_and_prompted(fake):
    reached = [{"quote": "약속한 대로 메일 한 통을 보냈다", "note": "약속을 지킴"}]
    fake["answers"] = [{"message": "'약속한 대로 메일 한 통을 보냈다' — 그게 약속을 지키는 모습이에요.",
                        "next_question": ""}]
    r = voice.generate(ctx(tone="다정하게", reached=reached))
    assert r["checks"] == [{"attempt": 1, "problems": []}]
    assert "되고 싶은 모습에 닿음" in r["situations"]
    assert all(x in sys_prompt(fake) for x in load()["aspiration"]["reached"])


def test_numbers_in_fact_bomb_allowed():
    # 기록의 숫자(3주째 · 10분)는 때려도 된다. 거리 · 점수만 금지
    assert checks.line_problems("수영 3주째 안 갔다. 내일 10분만.") == []


# --- 기도 · 편지 ---

def test_prayer_prompt(fake):
    fake["answers"] = [{"message": "기도로 하루를 닫았네요.", "next_question": ""}]
    voice.generate(ctx(tone="담백하게", addressee="신"))
    h = next(x for x in load()["addressee_handling"] if x["addressee"] == "신")
    assert h["do"] in sys_prompt(fake) and h["dont"] in sys_prompt(fake)
    assert "편지(" not in sys_prompt(fake)


def test_letter_prompt_with_person_history(fake):
    fake["answers"] = [{"message": "사람1에게 쓴 편지, 잘 받았어요.", "next_question": ""}]
    voice.generate(ctx(tone="다정하게", addressee="특정 인물", person_history=["지난달 사람1과 국수를 먹음"]))
    h = next(x for x in load()["addressee_handling"] if x["addressee"] == "특정 인물")
    assert h["do"] in sys_prompt(fake) and "기도(" not in sys_prompt(fake)
    assert "지난달 사람1과 국수를 먹음" in fake["calls"][0][1]["content"]


def test_me_has_no_prayer_or_letter(fake):
    fake["answers"] = [{"message": "핑계 그만.", "next_question": ""}]
    voice.generate(ctx(addressee="나"))
    assert "기도(" not in sys_prompt(fake) and "편지(" not in sys_prompt(fake)


# --- 상황 ---

def test_late_night_long():
    long = TEXT * 20
    assert "늦은 밤 길게" in voice.situations(ctx(text=long, written_at="2026-10-09T01:30:00"))
    assert "늦은 밤 길게" not in voice.situations(ctx(text=TEXT, written_at="2026-10-09T01:30:00"))   # 짧음
    assert "늦은 밤 길게" not in voice.situations(ctx(text=long, written_at="2026-10-09T20:30:00"))   # 저녁


def test_late_night_heavy_no_schedule_reminder(fake):
    fake["answers"] = [{"message": "오늘은 무거운 채로 있어도 괜찮아요.", "next_question": ""}]
    voice.generate(ctx(tone="다정하게", text=TEXT * 20, written_at="2026-10-09T01:30:00", weather="비"))
    assert "내일 일정" not in sys_prompt(fake)


def test_complex_day_and_rest():
    qs = [{"thought": "어디로 갈까", "kind": "질문"}, {"thought": "맞나", "kind": "해석", "certainty": "고민 중"}]
    assert "생각이 복잡한 날" in voice.situations(ctx(thoughts=qs))
    assert "생각이 복잡한 날" not in voice.situations(ctx())
    s = voice.situations(ctx(weather="흐림"))
    assert "쉼 권하기" in s and not voice._suggest(ctx(weather="흐림"), s)


def test_suggest_frequency():
    s = voice.situations(ctx())
    assert voice._suggest(ctx(), s)
    last = ["내일 한 곳만 볼까요?"]
    assert not voice._suggest(ctx(past_messages=last), s)                           # 가끔: 지난번에 했으면 뺀다
    assert voice._suggest(ctx(past_messages=last, settings={"suggest": "자주"}), s)
    assert not voice._suggest(ctx(settings={"suggest": "안 함"}), s)


def test_parse_non_json_answer(fake):
    fake["answers"] = ["오늘 쓴 거 봤어. 핑계 그만."]
    assert voice.generate(ctx())["message"] == "오늘 쓴 거 봤어. 핑계 그만."


# --- 다음 질문 · 무거운 날의 다짐 안부 ---

def test_fixed_question_used_verbatim(fake):
    fake["answers"] = [{"message": "오늘 쓴 거 봤어.", "next_question": "LLM이 바꾼 질문"}]
    r = voice.generate(ctx(text="수업 듣고 밥 먹음.", thoughts=[], weather=None, aspiration=None, days_written=0))
    assert r["next_kind"] == "weather" and r["next_question"] == voice.base_question("weather", {})


def test_llm_question_only_for_commitment(fake):
    fake["answers"] = [{"message": "핑계 그만.", "next_question": "달리기, 이번 주엔 한 번 나갔어?"}]
    c = ctx(commitments=[{"text": "주 3회 아침 달리기", "state": "열림", "overdue": True}])
    r = voice.generate(c)
    assert r["next_kind"] == "commitment" and r["next_question"] == "달리기, 이번 주엔 한 번 나갔어?"
    fake["answers"] = [{"message": "핑계 그만.", "next_question": "끼어든 질문"}]
    assert voice.generate(ctx())["next_question"] == ""                               # 고를 질문이 없으면 빈 글


def test_no_commitment_checkin_on_heavy_day():
    c = {"commitments": [{"text": "주 3회 아침 달리기", "state": "열림", "overdue": True}]}
    assert "다짐 안부" in voice.situations(ctx(**c))
    assert "다짐 안부" not in voice.situations(ctx(weather="비", **c))


def test_gentle_day_softens(fake):
    fake["answers"] = [{"message": "야, 또 미뤘다. 오늘 한 곳 찾아.", "next_question": ""},
                       {"message": "또 미뤘네. 오늘은 한 곳만 찾아 보자.", "next_question": ""}]
    r = voice.generate(ctx(settings={"gentle": True}))
    assert r["checks"][0]["problems"] == ["오늘은 살살인데 거친 부름"] and r["checks"][1]["problems"] == []
    s = sys_prompt(fake)
    assert load()["fact_bomb"]["strength"] not in s and load()["tones"][3]["example"] not in s
    fake["calls"].clear()
    voice.generate(ctx())                                                            # 평소 팩폭은 '야,' 그대로
    assert load()["fact_bomb"]["strength"] in sys_prompt(fake)


def test_aspiration_not_used_as_club():
    p = checks.problems("약속 지키는 사람 되고 싶다면서 또 미뤘네.", "", sources=[TEXT], past=[], comfort=False,
                        aspiration=True)
    assert p == ["멀어진 순간을 말함: '되고 싶다면서'"]
    assert checks.problems("또 미뤘네. 오늘 한 곳 찾아.", "", sources=[TEXT], past=[], comfort=False,
                           aspiration=True) == []


def test_cat_tone_and_length():
    kw = dict(sources=[TEXT], past=[], comfort=False, aspiration=False)
    assert checks.problems("또 미뤘네요. 괜찮아요.", "", tone="고양이처럼", **kw) == ["고양이 말끝(냥) 없음"]
    assert checks.problems("또 미뤘다냥. 괜찮다냥.", "", tone="고양이처럼", **kw) == []
    assert checks.problems("오늘 쓴 거 봤어. " * 40, "", **kw)[0].startswith("너무 김")


def test_aspiration_only_shown_on_reached_day(fake):
    fake["answers"] = [{"message": "핑계 그만. 오늘 한 곳 찾아.", "next_question": ""}]
    voice.generate(ctx())
    assert "약속을 지키는 사람이 되고 싶다" not in fake["calls"][0][1]["content"]
    fake["calls"].clear()
    voice.generate(ctx(reached=[{"quote": "또 미뤘다"}]))
    assert "약속을 지키는 사람이 되고 싶다" in fake["calls"][0][1]["content"]


def test_gentle_line_only_in_fact_bomb_prompt(fake):
    fake["answers"] = [{"message": "오늘 기록 잘 받았어요.", "next_question": ""}]
    voice.generate(ctx(tone="담백하게"))
    assert "살살" not in sys_prompt(fake)
