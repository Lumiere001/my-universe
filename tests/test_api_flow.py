"""API 전체 흐름(docs/api-v8.md). 로그인 · 저장소 · 외부 호출은 가짜(메모리 저장소, FakeUpstage)."""
import json

import pytest
from fastapi.testclient import TestClient

import main
from app.api import diary as diary_api
from app.core import config
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from tests.test_graph_flow import CRISIS, DAY1, DAY2, NAMES, U1, env  # noqa: F401  (env 픽스처)

U2 = "22222222-2222-2222-2222-222222222222"
TOKENS = {"tok1": {"id": U1, "email": "jiho@my-universe.test"}, "tok2": {"id": U2, "email": "other@my-universe.test"}}
H1, H2 = {"Authorization": "Bearer tok1"}, {"Authorization": "Bearer tok2"}
RESULT_KEYS = {"id", "status", "step", "written_at", "title", "weather", "crisis", "care", "info", "thoughts", "relations",
               "past", "reached", "message", "next_question", "people_questions"}


@pytest.fixture
def client(env):  # noqa: F811
    from fastapi import Header

    def fake_user(authorization: str = Header(default="")):
        u = TOKENS.get(authorization.removeprefix("Bearer "))
        if not u:
            raise ApiError(401, "unauthorized", "로그인이 필요해요.")
        return u

    main.app.dependency_overrides[get_user] = fake_user
    main.app.dependency_overrides[get_repo] = lambda: env.repo
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def events(text):
    out = []
    for block in text.split("\n\n"):
        lines = [x for x in block.split("\n") if x and not x.startswith(":")]
        if lines:
            ev = lines[0].removeprefix("event: ")
            out.append((ev, json.loads(lines[1].removeprefix("data: "))))
    return out


def write(client, title, text, when, h=H1, weather=None):
    r = client.post("/diary/stream", headers=h, json={"title": title, "text": text, "written_at": when, "weather": weather})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return r.text, events(r.text)


def test_public_and_auth(client):
    assert client.get("/health").json() == {"status": "ok", "version": "0.8.0"}
    assert "kinds" in client.get("/ontology").json()
    r = client.get("/universe")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_stream_progress_then_result(client):
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    prog = [d for e, d in ev if e == "progress"]
    assert [p["step"] for p in prog] == ["safety", "names", "record", "past", "observe", "voice", "save"]
    assert all(p["entry_id"] == prog[0]["entry_id"] and p["total"] == 7 for p in prog)
    assert [p["done"] for p in prog] == list(range(1, 8))
    kind, res = ev[-1]
    assert kind == "result" and set(res) == RESULT_KEYS and res["id"] == prog[0]["entry_id"]
    assert res["status"] == "done" and res["thoughts"] and res["message"]["mode"] == "normal"
    _, ev2 = write(client, *DAY2, "2026-10-03T22:00:00+09:00")
    res2 = ev2[-1][1]
    assert res2["past"] and res2["relations"]
    u = client.get("/universe", headers=H1).json()
    assert set(u) == {"suns", "stars", "planets", "links", "twins", "blackholes", "north_star", "people"}
    p = u["planets"][0]
    assert {"thought_count", "certainty", "has_question", "ring", "order", "people"} <= set(p)
    assert u["links"] and u["links"][0]["to_planet"] == res2["id"]
    lst = client.get("/diary", headers=H1).json()["entries"]
    assert [e["id"] for e in lst] == [res2["id"], res["id"]] and lst[0]["star"] == "아침 걷기"
    assert client.get(f"/diary/{res['id']}", headers=H1).json()["thoughts"] == res["thoughts"]


def test_keepalive_comment(client, env, monkeypatch):  # noqa: F811
    import time
    monkeypatch.setattr(diary_api, "KEEPALIVE_S", 0.05)
    slow = env.fake.chat.completions.create
    monkeypatch.setattr(env.fake.chat.completions, "create", lambda **kw: (time.sleep(0.3), slow(**kw))[1])
    text, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    assert ": keep-alive" in text and ev[-1][0] == "result"


def test_crisis_care(client, env):  # noqa: F811
    _, ev = write(client, *CRISIS, "2026-10-02T23:30:00+09:00")
    assert [d["step"] for e, d in ev if e == "progress"] == ["safety", "save"]
    res = ev[-1][1]
    assert res["crisis"] and res["care"]["resources"][0]["contact"] == "109"
    assert env.fake.calls == {"record": 0, "observe": 0, "chat": 0, "embed": 0}


def test_error_event_and_resume(client, env):  # noqa: F811
    env.fake.fail_observe = 2
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    kind, err = ev[-1]
    assert kind == "error" and err["code"] == "studio_failed" and err["resumable"] and err["entry_id"]
    assert client.get(f"/diary/{err['entry_id']}", headers=H1).json()["status"] == "failed"
    r = client.post(f"/diary/{err['entry_id']}/resume/stream", headers=H1)
    ev2 = events(r.text)
    assert ev2[-1][0] == "result" and ev2[-1][1]["status"] == "done"
    assert env.fake.calls["record"] == 1


@pytest.mark.parametrize("body,field", [
    ({"text": ""}, "text"),
    ({"text": "가" * (config.MAX_TEXT_CHARS + 1)}, "text"),
    ({"text": "글", "weather": "눈"}, "weather"),
    ({"text": "글", "mood": "x"}, "mood"),
])
def test_input_validation(client, body, field):
    r = client.post("/diary/stream", headers=H1, json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    assert field in r.json()["error"]["message"] and "가가가" not in r.text


def test_daily_limit(client, monkeypatch):
    monkeypatch.setattr(config, "DAILY_ENTRY_LIMIT", 1)
    write(client, *CRISIS, "2026-10-02T23:30:00+09:00")
    r = client.post("/diary/stream", headers=H1, json={"text": "하나 더"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_limit"


def test_monthly_budget(client, monkeypatch):
    monkeypatch.setattr(config, "MONTHLY_COST_CAP_USD", 0.0)
    r = client.post("/diary", headers=H1, json={"text": "글"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "monthly_budget"


def test_settings_fact_bomb_needs_ack(client):
    assert client.get("/me", headers=H1).json()["settings"]["tone"] == "다정하게"
    r = client.patch("/settings", headers=H1, json={"tone": "팩폭"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "fact_bomb_ack_required"
    assert client.patch("/settings", headers=H1, json={"tone": "팩폭", "fact_bomb_ack": True}).json()["tone"] == "팩폭"
    assert client.patch("/settings", headers=H1, json={"tone": "반말"}).status_code == 422
    assert client.patch("/settings", headers=H1, json={"fact_bomb_ack": False}).json()["tone"] == "다정하게"


def test_feedback_buttons(client):
    _, ev1 = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    _, ev2 = write(client, *DAY2, "2026-10-03T22:00:00+09:00")
    rel = ev2[-1][1]["relations"][0]
    assert rel["line"] == "점선"
    r = client.post("/feedback", headers=H1, json={"target": "relation", "target_id": rel["id"], "value": "맞아요"})
    assert r.json()["ok"]
    assert client.get(f"/diary/{ev2[-1][1]['id']}", headers=H1).json()["relations"][0]["line"] == "실선"
    r = client.post("/feedback", headers=H1, json={"target": "relation", "target_id": rel["id"], "value": "아니에요"})
    assert client.get(f"/diary/{ev2[-1][1]['id']}", headers=H1).json()["relations"] == []
    vow = next(t for t in ev1[-1][1]["thoughts"] if t["kind"] == "다짐")
    r = client.post("/feedback", headers=H1, json={"target": "vow", "target_id": vow["id"], "value": "지켰어요"})
    assert r.json()["state"] == {"type": "다짐", "status": "지켜짐", "mistake": False}
    r = client.post("/feedback", headers=H1, json={"target": "vow", "target_id": vow["id"], "value": "지켰어요"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_target"
    client.post("/feedback", headers=H1, json={"target": "weather", "value": "날씨 건너뜀"})
    client.post("/feedback", headers=H1, json={"target": "message", "value": "오늘은 살살"})
    st = client.get("/me", headers=H1).json()["settings"]
    assert st["weather_ask"] is False and st["gentle_today"]
    assert client.post("/feedback", headers=H1, json={"target": "message", "value": "최고"}).status_code == 422
    r = client.post("/feedback", headers=H1, json={"target": "app", "value": "불편한 점 한 줄", "text": "글자가 작아요"})
    assert r.json()["ok"]
    s = client.get("/stats", headers=H1).json()
    assert s["feedback"]["맞아요"] == 1 and s["yes_ratio"] == 0.5 and s["entries"] == 2 and "글자가" not in json.dumps(s)


def test_people_crud_and_forget(client):
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    people = client.get("/people", headers=H1).json()["people"]
    mj = next(p for p in people if p["name"] == "민준")
    assert mj["auto"] and mj["planets"] == [ev[-1][1]["id"]]
    p = client.patch(f"/people/{mj['id']}", headers=H1, json={"relation": "친구", "nickname": "준이"}).json()
    assert p["relation"] == "친구" and p["nickname"] == "준이" and p["auto"] is False
    added = client.post("/people", headers=H1, json={"name": "하린", "relation": "동생"}).json()
    assert added["name"] == "하린"
    r = client.delete(f"/people/{mj['id']}", headers=H1).json()
    assert r["ok"] and r["replaced"] >= 1
    res = client.get(f"/diary/{ev[-1][1]['id']}", headers=H1).json()
    assert "민준" not in json.dumps(res, ensure_ascii=False) and "친구" in json.dumps(res, ensure_ascii=False)
    assert client.delete(f"/people/{mj['id']}", headers=H1).status_code == 404


def test_people_question_answer(client):
    _, ev = write(client, "", "오늘 하늘이랑 공원에 갔다. 날씨가 좋았다.", "2026-10-01T22:00:00+09:00")
    assert ev[-1][0] == "result", ev[-1]
    qs = ev[-1][1]["people_questions"]
    assert qs and qs[0]["name"] == "하늘" and "사람 이름 아님" in qs[0]["options"]
    assert client.post(f"/people/questions/{qs[0]['id']}", headers=H1, json={"answer": "사람 이름"}).json()["ok"]
    assert "하늘" in [p["name"] for p in client.get("/people", headers=H1).json()["people"]]
    assert client.get(f"/diary/{ev[-1][1]['id']}", headers=H1).json()["people_questions"] == []


def test_aspiration_and_north_star(client):
    assert client.get("/aspiration", headers=H1).json()["current"] is None
    a = client.post("/aspiration", headers=H1, json={"now": "미루는 나", "want": "약속을 지키는 사람", "obstacle": "피곤함",
                                                     "if_then": "피곤하면 5분만 걷겠다", "values": ["규범"]}).json()
    assert a["said"] == "약속을 지키는 사람" and a["values"] == ["규범"]
    client.post("/aspiration", headers=H1, json={"want": "꾸준한 사람", "values": ["성취"]})
    st = client.get("/aspiration", headers=H1).json()
    assert st["current"]["said"] == "꾸준한 사람" and [h["said"] for h in st["history"]] == ["약속을 지키는 사람"]
    assert client.post("/aspiration", headers=H1, json={"want": "x", "values": ["성장"]}).status_code == 422
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    ns = client.get("/universe", headers=H1).json()["north_star"]
    assert ns["text"] == "꾸준한 사람" and ns["reached_planets"] == []
    assert client.post("/aspiration/decline", headers=H1, json={"mode": "stop"}).json()["ok"]
    assert client.get("/me", headers=H1).json()["onboarding"]["aspiration"] == "stop"


def test_delete_and_isolation(client, env):  # noqa: F811
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    eid = ev[-1][1]["id"]
    assert client.get(f"/diary/{eid}", headers=H2).status_code == 404
    assert client.get("/universe", headers=H2).json()["planets"] == []
    assert client.delete(f"/diary/{eid}", headers=H2).status_code == 404
    assert client.delete(f"/diary/{eid}", headers=H1).status_code == 204
    assert client.get(f"/diary/{eid}", headers=H1).status_code == 404
    assert env.repo.vectors.get(U1) == {}


def test_plain_post_and_cors(client):
    r = client.post("/diary", headers=H1, json={"title": DAY1[0], "text": DAY1[1]})
    assert r.status_code == 200 and r.json()["status"] == "done"
    r = client.options("/universe", headers={"Origin": config.FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET",
                                             "Access-Control-Request-Headers": "authorization"})
    assert r.headers["access-control-allow-origin"] == config.FRONTEND_ORIGIN
    r = client.options("/universe", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers


def test_client_disconnect_keeps_working(client):
    import time
    with client.stream("POST", "/diary/stream", headers=H1, json={"title": DAY1[0], "text": DAY1[1]}) as r:
        lines = r.iter_lines()
        assert next(lines) == "event: progress"
        eid = json.loads(next(lines).removeprefix("data: "))["entry_id"]
    for _ in range(100):   # 손님이 끊어도 서버 쪽 처리는 끝까지 간다
        if client.get(f"/diary/{eid}", headers=H1).json()["status"] == "done":
            break
        time.sleep(0.05)
    assert client.get(f"/diary/{eid}", headers=H1).json()["status"] == "done"


def test_no_real_names_left_the_server(client, env):  # noqa: F811
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    write(client, *DAY2, "2026-10-03T22:00:00+09:00")
    sent = "\n".join(env.fake.sent)
    assert sent and [n for n in NAMES if n in sent] == []
