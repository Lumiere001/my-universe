"""PRD v9 ⑦-2 · ②: 멀어짐을 원문 근거로 알아채고(Q4) → 다음 첫 말의 숨은 이유로(Q6) → 대화 안에서 사용자의 말로 한 번(Q5-1)."""
from datetime import date, timedelta

from app.agents import graph
from app.repository import diary
from app.service import chat
from app.service.rules import drift
from tests.test_api_flow import H1, client  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import U1, env  # noqa: F401  (env 픽스처)
from tests.test_ws12_rules_voice import put
from tests.test_ws19_talk import start

IF_THEN = "피곤하면 오 분만 연락하겠다"


def when(days_ago):   # 걸림 근거는 최근 14일 안에서 센다 → 오늘 기준 날짜로
    return f"{date.fromisoformat(str(diary.today())) - timedelta(days=days_ago)}T22:00:00+09:00"


def test_drift_rules():
    hits = [{"day": "2026-10-20", "entry_id": "e1"}, {"day": "2026-10-28", "entry_id": "e2"}]
    assert drift.kind(hits, "2026-10-30", None, 0) == "멀어짐"
    assert drift.kind(hits, "2026-10-30", None, 0, said="2026-10-27") is None             # 건넨 뒤 7일은 쉼
    assert drift.kind([], "2026-10-30", "2026-10-20", 5) == "가까워지지 못함"
    assert drift.kind([], "2026-10-30", "2026-10-20", 4) is None


def test_chat_direction_rules():
    assert chat.with_direction(["지난 기록 떠올리기"], IF_THEN)[-1] == "어디로 가자"
    assert chat.with_direction(["대화를 마칠 때"], IF_THEN)[-1] == "어디로 가자(마치기 전)"
    assert chat.with_direction(["무거운 날"], IF_THEN) == ["무거운 날"]                    # 무거운 날엔 꺼내지 않음
    bad = chat.problems(f"요즘 멀어졌네요. '{IF_THEN}' 해 볼까요?", sources=[IF_THEN], past_replies=[], direction=True)
    assert any("판정" in p for p in bad)
    ok = chat.problems(f"'{IF_THEN}'고 했었죠. 오늘 해 볼까요?", sources=[IF_THEN], past_replies=[], direction=True, wrap=True)
    assert ok == []                                                                        # 마칠 때도 질문 하나는 됨


def test_drift_becomes_hidden_reason_then_direction(client, env, monkeypatch):  # noqa: F811
    with env.repo.session(U1) as s:
        diary.add_aspiration(s, "", "곁에 있어 주는 친구", "피곤하면 미룬다", IF_THEN, [], why="혼자였던 게 싫어서", scene="먼저 안부")
        diary.save_profile(s, onboarding={"aspiration": "set", "intro": True})
    hit = lambda state, asp, ctx: {"day": state["day"], "entry_id": ctx.entry_id, "quote": "피곤해서 또 미뤘다"}  # noqa: E731
    monkeypatch.setattr(graph, "_obstacle_hit", hit)          # 걸림 비슷함 + Solar 확인을 지났다고 치고
    monkeypatch.setattr(graph, "_vow_missed_hit", lambda *a: None)
    for i in (1, 2):   # 대화로 쓴 일기 두 편에서 걸림이 되풀이 → 멀어짐
        eid = diary.new_id("e")
        with env.repo.session(U1) as s:
            diary.create_entry(s, eid, diary.parse_dt(when(3 - i)), "맑음", f"글 {i}", "피곤해서 연락을 미뤘다.", source="대화")
        graph.run(env.repo, U1, eid)   # 대화 일기는 확인 앞에서 멈춘다 → 확인하면 save
        assert client.post(f"/diary/{eid}/confirm", headers=H1, json={"fixes": [], "agreed": []}).status_code == 200
    with env.repo.session(U1) as s:
        ob = diary.profile(s)[1]
        msg = diary.message(s, s.rows("messages", entry_id=eid)[0])
    assert len(ob["drift_hits"]) == 2 and ob["drift_said"]                               # 근거 · 건넨 날(7일 쉼)
    assert msg["reason"] == "drift" and msg["reveal"] and IF_THEN not in msg["next_question"]   # 첫 질문은 이유를 숨김
    c = start(client)
    assert c["turns"][0]["text"] == chat.FREE and c["reason"] is None                        # 첫 말은 가볍게, 이유 한 줄은 아직
    with env.repo.session(U1) as s:
        from app.repository import conversations
        stored = conversations.get(s, c["id"])
        assert stored["reason"]["direction"] == IF_THEN                                      # 대화 안에서 한 번 건넬 말
        assert stored["topic"] == msg["next_question"]                                        # 숨은 이유 질문은 대화 중에 한 번


def test_direct_write_gets_direction_in_message(env, monkeypatch):  # noqa: F811
    with env.repo.session(U1) as s:
        diary.add_aspiration(s, "", "곁에 있어 주는 친구", "피곤하면 미룬다", IF_THEN, [])
    hit = lambda state, asp, ctx: {"day": state["day"], "entry_id": ctx.entry_id, "quote": "피곤해서 또 미뤘다"}  # noqa: E731
    monkeypatch.setattr(graph, "_obstacle_hit", hit)
    put(env, "글 1", "피곤해서 연락을 미뤘다.", when(2))
    seen = []
    orig = graph.tools.speak
    monkeypatch.setattr(graph.tools, "speak", lambda ctx, people: seen.append(ctx) or orig(ctx, people))
    put(env, "글 2", "피곤해서 또 연락을 미뤘다.", when(1))
    assert seen[-1]["direction"] == IF_THEN and seen[-1]["drift"] is None                # 직접 쓴 날: 이번 한마디 자리에서(점검 3)


def test_flow_brief_and_ask(client, env):  # noqa: F811
    """PRD v9 Q10 · Q11: 흐름 요약은 기간 안 원문 재료로만, 문장마다 출처(없는 출처는 버림) · 새 기록이 없으면 저장한 것.
    내 일기에 묻기는 찾은 원문으로만 답하고 일기를 만들지 않는다. 기록이 셋보다 적으면 요약하지 않는다."""
    put(env, "걷기 1", "아침에 공원을 걸었다.", when(2))
    assert client.get("/insight/brief?period=all", headers=H1).json() == {"state": "few", "sections": []}
    put(env, "걷기 2", "점심에 동네를 걸었다.", when(1))
    put(env, "걷기 3", "저녁에 강가를 걸었다.", when(0))
    b = client.get("/insight/brief?period=all", headers=H1).json()
    assert b["state"] == "ok" and [x["text"] for x in b["sections"][0]["sentences"]] == ["걷기 이야기가 이어졌어요."]
    assert b["sections"][0]["sentences"][0]["sources"][0]["entry_id"]
    calls = env.fake.calls["chat"]
    assert client.get("/insight/brief?period=all", headers=H1).json() == b and env.fake.calls["chat"] == calls   # 저장한 것
    n = len(client.get("/diary", headers=H1).json()["entries"])
    a = client.post("/insight/ask", headers=H1, json={"question": "걷기 얘기 언제 했지?"}).json()
    assert a["state"] == "ok" and a["sentences"][0]["sources"]
    assert len(client.get("/diary", headers=H1).json()["entries"]) == n                     # 일기로 남지 않음
    assert client.post("/insight/ask", headers=H1, json={"question": "죽고 싶어"}).json()["state"] == "crisis"
    assert client.get("/insight?period=week", headers=H1).status_code == 200


def test_push_subscribe_and_due(client, env, monkeypatch):  # noqa: F811
    """PRD v9 Q8: 고른 30분 자리에 하루 한 번, 고른 별지기 말투의 정해 둔 한 줄(일기 내용 없음). 만료된 구독은 지움."""
    from datetime import datetime as real
    from app.api import routes
    from app.core import config
    from app.service import push
    monkeypatch.setattr(config, "VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setattr(config, "VAPID_PRIVATE_KEY", "priv")
    monkeypatch.setattr(config, "CRON_SECRET", "s3")
    sub = {"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "k", "auth": "a"}, "notify_at": "21:00"}
    assert client.post("/push/subscribe", headers=H1, json=sub).json()["ok"]
    assert client.post("/push/subscribe", headers=H1, json={**sub, "notify_at": "21:30"}).json()["notify_at"] == "21:30"
    assert [x["notify_at"] for x in client.get("/push/subscribe", headers=H1).json()["subs"]] == ["21:30"]   # 같은 기기는 하나
    with env.repo.session(U1) as s:
        assert "abc" not in repr(s.rows("push_subs")[0]["enc"])                         # 구독 주소는 암호문에만
    sent = []
    monkeypatch.setattr(push, "send", lambda s, data, k, subj: sent.append(data) or "ok")

    class At(real):
        @classmethod
        def now(cls, tz=None):
            return real(2026, 11, 2, 21, 40, tzinfo=tz)
    monkeypatch.setattr(routes, "datetime", At)
    assert client.post("/push/due", headers={"X-Cron-Secret": "nope"}).status_code == 403
    r = client.post("/push/due", headers={"X-Cron-Secret": "s3"}).json()
    assert r["sent"] == 1 and "오늘 하루는 어땠어요" in sent[0] and "abc" not in sent[0]       # 기본 별지기(다정하게) 말투
    assert client.post("/push/due", headers={"X-Cron-Secret": "s3"}).json()["sent"] == 0   # 하루 한 번
    with env.repo.session(U1) as s:
        s.update("push_subs", {"last_sent": None})
    monkeypatch.setattr(push, "send", lambda *a: "gone")
    assert client.post("/push/due", headers={"X-Cron-Secret": "s3"}).json()["gone"] == 1
    assert client.get("/push/subscribe", headers=H1).json()["subs"] == []                  # 만료 → 지움(설정에 '꺼졌어요')


def test_topic_asked_once_then_reason_line(client, env, monkeypatch):  # noqa: F811
    """PRD v9 Q6 개정(2026-11-02 동규 A): 지어 둔 질문은 사용자 말과 닿을 때 대화 중 한 번. 건넨 뒤에만 정리본 화면에 이유 한 줄."""
    from tests.test_ws19_talk import fake_talk, say
    talk = fake_talk(env.fake)
    from app.api import chat as chat_api
    monkeypatch.setattr(chat_api, "prompt", lambda s: {"kind": "free", "text": "요즘 저녁엔 뭐 하면서 쉬어요?", "vow": None,
                                                       "reason": {"key": "commitment", "reveal": "저녁 다짐이 떠올라서 물었어요."}})
    c = start(client)
    assert c["turns"][0]["text"] == chat.FREE and c["reason"] is None
    seen = []
    def answer(msgs, used):
        seen.append("topic" in msgs[-1]["content"] and "요즘 저녁엔" in msgs[-1]["content"])
        return {"reply": "저녁 이야기가 나와서요. 요즘 저녁엔 뭐 하면서 쉬어요?" if used else f"그랬군요. {len(seen)}번째 이야기, 그다음엔요?",
                "found": False, "topic": used}
    talk.queue += [lambda m: answer(m, False), lambda m: answer(m, True), lambda m: answer(m, False)]
    ev = say(client, c["id"], "오늘은 그냥 그랬어.")
    assert ev[-1][0] == "turn"
    assert client.get(f"/talk/{c['id']}", headers=H1).json()["reason"] is None                 # 아직 안 건넴
    say(client, c["id"], "저녁엔 좀 쉬었어.")
    assert client.get(f"/talk/{c['id']}", headers=H1).json()["reason"] == "저녁 다짐이 떠올라서 물었어요."
    say(client, c["id"], "응 그랬지.")
    assert seen == [True, True, False]                                                        # 건넨 뒤엔 다시 넣지 않음
