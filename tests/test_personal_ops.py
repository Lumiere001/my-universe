"""개인 맞춤 Ops(2026-10-30): 모두에게 같은 공통 틀 위에, 사람마다 그 사람 반응으로만 도는 개인 고리.
③ '별로' 받은 한마디는 다시 쓰지 않음(다음 한마디 프롬프트의 개인 금지 목록), ① 개인 지표는 사람마다 · 운영에는 분포만."""
import json
from datetime import date, datetime, timedelta, timezone

from app.repository import diary, ops
from app.service import voice
from tests.test_graph_flow import DAY1, U1, env, write  # noqa: F401


def test_disliked_message_goes_to_next_prompt_as_never_again(env):
    e1, _, r1 = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    with env.repo.session(U1) as s:
        diary.add_feedback(s, "message", e1, "별로")
    env.fake.sent.clear()
    write(env, U1, "둘째", "오늘도 걸었다. 걷기를 또 적었다.", "2026-10-02T22:00:00+09:00")
    voice_prompt = next(x for x in env.fake.sent if "별지기" in x and "'별로'라고 한 한마디" in x)
    assert r1["message"]["text"][-12:] in voice_prompt.split("'별로'라고 한 한마디")[1]   # 가명 처리된 지난 한마디(끝부분)가 금지 목록에
    msgs = voice.build_messages({"disliked": ["힘내요!"]}, "편지", [], False)
    assert "힘내요!" in msgs[0]["content"]
    assert "'별로'" not in voice.build_messages({}, "편지", [], False)[0]["content"]   # 없으면 칸도 없음
    long = "가" * 150 + " 다음엔 하나만 적어 볼까요?"
    got = voice.build_messages({"disliked": [long]}, "편지", [], False)[0]["content"]
    assert "적어 볼까요?" in got and "가" * 120 not in got   # 끝부분만(길게 넣으면 한마디도 길어졌다)


def _fb(user, target, value, days_ago, today=date(2026, 10, 30)):
    at = datetime.combine(today - timedelta(days=days_ago), datetime.min.time(), timezone.utc) + timedelta(hours=3)
    return {"user_id": user, "target": target, "value": value, "created_at": at}


def test_personal_metrics_per_user_and_spread_only():
    today = date(2026, 10, 30)
    fb = ([_fb("u1", "relation", "맞아요", 20)] * 5 + [_fb("u1", "relation", "아니에요", 2)] * 4 + [_fb("u1", "relation", "맞아요", 1)]
          + [_fb("u1", "star", "옮김", 3)] * 2 + [_fb("u2", "relation", "맞아요", 1)] * 2 + [_fb("u2", "message", "별로", 1)] * 5)
    entries = [{"user_id": "u1", "status": "done"}] * 10 + [{"user_id": "u2", "status": "done"}] * 4
    per = ops.personal(fb, entries, today)
    assert per["u1"]["links_yes"] == {"now": 0.2, "before": 1.0}   # 최근 14일 5번 중 '맞아요' 1 — 자기 기준(1.0)보다 나빠짐
    assert per["u1"]["fixes"] == 2.0                                 # 글 10편당 AI 정리를 고친 수
    assert per["u2"]["links_yes"]["now"] is None                     # 반응 2번은 믿기 어려움(PERSONAL_MIN)
    assert per["u2"]["dislike"]["now"] == 1.0
    spread = ops.personal_spread(per)
    assert spread["links_yes"] == {"users": 1, "median": 0.2, "worse": 1}
    assert spread["dislike"] == {"users": 1, "median": 1.0, "worse": 0}
    assert spread["fixes"] == {"users": 2, "median": 1.0}
    assert "u1" not in json.dumps(spread)                            # 운영에는 사람 id 없이 분포만
