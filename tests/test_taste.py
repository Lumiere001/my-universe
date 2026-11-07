"""취향 고리(voice.taste, 2026-11-07): 좋아요 · 별로로 말하는 방식(제안 · 지난 기록 · 길이)을 사람마다 톰슨 샘플링."""
import random

from app.core import config
from app.repository import diary
from app.service import voice
from app.service.voice import taste
from tests.test_graph_flow import DAY1, NAMES, U1, env, write  # noqa: F401

SHORT_NO = "오늘 아침에 걸은 것, 잘했어요."
LONG_RECALL_SUGGEST = "10월 3일에도 걷기를 적으셨죠. 오늘도 이어 가셨네요. " * 2 + "내일은 5분만 더 걸어 볼까요?"
FORCE = {"suggest": True, "recall": True, "short": True}


def test_ways():
    assert taste.ways(SHORT_NO) == {"suggest": False, "recall": False, "short": True}
    assert taste.ways(LONG_RECALL_SUGGEST) == {"suggest": True, "recall": True, "short": False}
    assert taste.ways("")["short"] is False


def test_tally_counts_each_style_on_off_and_skips_other_values():
    c = taste.tally([(SHORT_NO, "좋아요"), (LONG_RECALL_SUGGEST, "별로"), (SHORT_NO, "맞아요"), ("", "좋아요")])
    assert c["short"] == {True: [1, 0], False: [0, 1]}
    assert c["recall"] == {True: [0, 1], False: [1, 0]}


def test_plan_converges_and_none_without_feedback():
    c = taste.tally([("짧" * 10, "좋아요")] * 6 + [("길" * 100, "별로")] * 4)
    rng = random.Random(7)
    assert sum(taste.plan(c, rng)["short"] for _ in range(200)) >= 180
    assert taste.plan(taste.tally([])) == {"suggest": None, "recall": None, "short": None}
    assert taste.lean(c)["short"] > 0.5


def test_lines():
    assert taste.lines({"suggest": True, "recall": None, "short": None}) == []   # 제안은 voice 가 따로
    assert taste.lines({"recall": True, "short": False}) == [taste.WAYS["recall"][1], taste.WAYS["short"][2]]


def test_suggest_precedence():
    yes, no = {"taste": {"suggest": True}}, {"taste": {"suggest": False}}
    assert voice._suggest(yes, ["무거운 날"]) is False and voice._suggest(yes, ["쉼 권하기"]) is False
    assert voice._suggest({**yes, "settings": {"suggest": "안 함"}}, []) is False
    assert voice._suggest({**no, "settings": {"suggest": "자주"}}, []) is False   # 다이얼보다 이 사람 반응이 먼저
    assert voice._suggest(yes, []) is True
    assert voice._suggest({"taste": {"suggest": None}, "past_messages": ["걸어 볼까요?"]}, []) is False   # 없으면 옛 규칙(가끔)


def test_build_messages_taste_section_not_on_heavy_or_crisis_day():
    ctx = {"taste": FORCE, "liked": ["가" * 150 + " 좋아한 끝"]}
    got = voice.build_messages(ctx, "", [], True)[0]["content"]
    assert "좋아요 · 별로로 배운 것" in got and taste.WAYS["short"][1] in got and "한두 문장, 80자 안" in got
    assert "좋아한 끝" in got and "가" * 120 not in got
    for sit in (["무거운 날"], ["위기", "무거운 날"]):
        heavy = voice.build_messages(ctx, "", sit, False)[0]["content"]
        assert "배운 것" not in heavy and "'좋아요'를 누른" not in heavy and "120자 안팎" in heavy
    assert "배운 것" not in voice.build_messages({}, "", [], False)[0]["content"]


def test_graph_speak_passes_liked_and_taste(env, monkeypatch):
    e1, _, r1 = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    with env.repo.session(U1) as s:
        diary.add_feedback(s, "message", e1, "별로")
        diary.add_feedback(s, "message", e1, "좋아요")   # 마지막으로 누른 값만
    env.fake.sent.clear()
    write(env, U1, "둘째", "오늘도 걸었다. 걷기를 또 적었다.", "2026-10-02T22:00:00+09:00")
    prompt = next(x for x in env.fake.sent if "별지기" in x and "'좋아요'를 누른" in x)
    assert "좋아요 · 별로로 배운 것" in prompt
    assert r1["message"]["text"][-12:] in prompt.split("'좋아요'를 누른")[1]
    assert not [n for n in NAMES if n in "\n".join(env.fake.sent)]   # 좋아한 한마디도 가명으로
    monkeypatch.setattr(config, "TASTE_LOOP", False)
    env.fake.sent.clear()
    write(env, U1, "셋째", "오늘은 쉬었다.", "2026-10-03T22:00:00+09:00")
    assert not [x for x in env.fake.sent if "'좋아요'를 누른" in x or "배운 것" in x]
