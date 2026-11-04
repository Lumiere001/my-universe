"""정리가 끝나면 알림(2026-11-04): POST/DELETE /diary/{id}/notify(정리 중일 때만, 알림 주소는 암호문) · 끝난 뒤 화면이 거두지 않았으면
그 기기로 한 줄(일기 내용 없음) · 앱을 닫아도(손님이 끊어도) 응답이 흐름을 끝까지 읽어 요청을 붙잡아 둠. 외부 호출은 가짜, 가상 인물 글만."""
import anyio
import pytest
from starlette.requests import ClientDisconnect

from app.api import diary as diary_api
from app.core import config
from app.repository import diary
from tests.test_api_flow import H1, H2, client, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, U1, env  # noqa: F401  (env 픽스처)
from tests.test_ws13_write_screen import _result

SUB = {"endpoint": "https://push.example.test/abc123", "keys": {"p256dh": "k1", "auth": "k2"}}


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(config, "VAPID_PRIVATE_KEY", "test-private")
    monkeypatch.setattr(diary_api, "DONE_GRACE_S", 0)
    monkeypatch.setattr(diary_api.push, "send", lambda sub, data, key, subject: out.append((sub, data)) or "ok")
    return out


def test_notify_only_while_running_and_sealed(client, env, sent):  # noqa: F811
    eid = _result(write(client, *DAY1, "2026-10-01T22:00:00+09:00")[1])["id"]
    assert client.post(f"/diary/{eid}/notify", headers=H1, json=SUB).json() == {"waiting": False}   # 이미 끝남 → 화면이 결과를 받음
    with env.repo.session(U1) as s:
        diary.lock(s, eid)
    assert client.post(f"/diary/{eid}/notify", headers=H1, json=SUB).json() == {"waiting": True}
    with env.repo.session(U1) as s:
        enc = s.rows("entries", id=eid)[0]["notify_enc"]
    assert enc and SUB["endpoint"].encode() not in bytes(enc)                                   # 알림 주소는 암호문으로만
    assert client.post(f"/diary/{eid}/notify", headers=H2, json=SUB).status_code == 404            # 남의 기록
    assert client.post(f"/diary/{eid}/notify", headers=H1, json={**SUB, "endpoint": "http://x.test/1"}).status_code == 422

    diary_api._notify_done(env.repo, U1, eid, "done")                                             # 끝났는데 화면이 안 거둠 → 보냄
    assert len(sent) == 1 and sent[0][0] == SUB
    assert f"/history?id={eid}" in sent[0][1] and "정리가 끝났어요" in sent[0][1]
    assert not any(w in sent[0][1] for w in DAY1[1].split()[:5])                                  # 잠금 화면에 일기 내용 없음
    diary_api._notify_done(env.repo, U1, eid, "done")                                             # 한 번만
    assert len(sent) == 1

    client.post(f"/diary/{eid}/notify", headers=H1, json=SUB)
    assert client.delete(f"/diary/{eid}/notify", headers=H1).status_code == 204                  # 화면이 결과를 받음 → 거둠
    diary_api._notify_done(env.repo, U1, eid, "done")
    assert len(sent) == 1


def test_notify_off_without_vapid(client, env, sent, monkeypatch):  # noqa: F811
    eid = _result(write(client, *DAY1, "2026-10-01T22:00:00+09:00")[1])["id"]
    with env.repo.session(U1) as s:
        diary.lock(s, eid)
    monkeypatch.setattr(config, "VAPID_PRIVATE_KEY", "")
    assert client.post(f"/diary/{eid}/notify", headers=H1, json=SUB).json() == {"waiting": False}


@pytest.mark.parametrize("spec", ["2.0", "2.4"])
def test_drain_reads_to_the_end_when_client_leaves(spec):
    """앱을 닫아 손님이 끊겨도 남은 흐름(그래프가 끝날 때까지)을 다 읽는다 → Vercel 이 요청을 끝내지 않음."""
    seen = []

    def gen():
        for i in range(5):
            seen.append(i)
            yield f"data: {i}\n\n"

    async def receive():
        return {"type": "http.disconnect"}

    async def send(m):
        if spec == "2.4" and m["type"] == "http.response.body" and m.get("body"):
            raise OSError("gone")

    async def run():
        await diary_api._Drain(gen())({"type": "http", "asgi": {"spec_version": spec}}, receive, send)

    if spec == "2.4":
        with pytest.raises(ClientDisconnect):
            anyio.run(run)
    else:
        anyio.run(run)
    assert seen == [0, 1, 2, 3, 4]
