"""전화처럼 이야기하기(ElevenLabs Agents + Custom LLM): POST /voice/call(새 대화 + 대화 표 + 통화 표) · 설정 없음 503 ·
ElevenLabs 실패 502 · /voice/llm/chat/completions 의 Bearer · 통화 표 검사 · 한 턴(via=voice)이 글 대화와 같은 길로 저장 ·
SSE / JSON 답 · 실패해도 말 한 줄 · 외부 요청 실명 0건. 외부 호출은 모두 가짜, 가상 인물 글만."""
import json
import time

import httpx
import pytest

from app.api import voice_call
from app.core import config
from tests.test_api_flow import H1, H2, client  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import CRISIS, NAMES, U1, env  # noqa: F401  (env 픽스처)
from tests.test_ws19_talk import talk  # noqa: F401  (talk 픽스처)

KEY = "test-voice-llm-key"
LLM = "/voice/llm/chat/completions"
BEARER = {"Authorization": f"Bearer {KEY}"}


@pytest.fixture
def eleven(monkeypatch):
    """설정을 채우고 httpx.get(대화 표 요청)을 가짜로. calls 에 보낸 것을 남긴다."""
    st = type("S", (), {"calls": [], "status": 200})()

    def get(url, params=None, headers=None, timeout=None):
        st.calls.append({"url": url, "params": params, "headers": headers})
        if st.status == "down":
            raise httpx.ConnectError("down")
        return httpx.Response(st.status, json={"token": "lk-conv-token", "conversation_id": "conv_x"} if st.status == 200 else {})

    monkeypatch.setattr(config, "VOICE_CALL_ON", True)
    monkeypatch.setattr(config, "ELEVENLABS_AGENT_ID", "agent_test")
    monkeypatch.setattr(config, "VOICE_LLM_KEY", KEY)
    monkeypatch.setattr(config, "ELEVENLABS_AGENTS_KEY", "test-key")
    monkeypatch.setattr(voice_call.httpx, "get", get)
    return st


def call(client, h=H1):  # noqa: F811
    r = client.post("/voice/call", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def ask(client, tok, said, stream=True, h=BEARER, role="user"):  # noqa: F811
    """ElevenLabs 가 보내는 모양 그대로(시스템 · 첫 말 · 사용자 말, elevenlabs_extra_body)."""
    msgs = [{"role": "system", "content": "별지기"}, {"role": "assistant", "content": "오늘 하루는 어땠어요?"}, {"role": role, "content": said}]
    return client.post(LLM, headers=h, json={"model": "my-universe", "messages": msgs, "stream": stream, "temperature": 0.5,
                                             "max_tokens": 5000, "elevenlabs_extra_body": {"call_token": tok}})


def sse(text):
    return [b.removeprefix("data: ") for b in text.split("\n\n") if b]


def test_call_unconfigured_auth_consent(client, env, eleven, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "VOICE_CALL_ON", False)                             # 기본 꺼짐: 설정이 다 있어도 안 엶
    r = client.post("/voice/call", headers=H1)
    assert r.status_code == 503 and r.json()["error"]["code"] == "call_off"
    assert client.get("/me", headers=H1).json()["voice_call"] is False                # 화면도 전화 단추를 숨김
    monkeypatch.setattr(config, "VOICE_CALL_ON", True)
    assert client.get("/me", headers=H1).json()["voice_call"] is True
    for name in ("ELEVENLABS_AGENT_ID", "VOICE_LLM_KEY", "ELEVENLABS_AGENTS_KEY"):
        monkeypatch.setattr(config, name, "")
        r = client.post("/voice/call", headers=H1)
        assert r.status_code == 503 and r.json()["error"]["code"] == "call_unconfigured", name
        monkeypatch.setattr(config, name, {"ELEVENLABS_AGENT_ID": "agent_test", "VOICE_LLM_KEY": KEY}.get(name, "test-key"))
    assert eleven.calls == [] and client.get("/talk", headers=H1).json()["conversations"] == []   # 대화도 안 열고 밖으로도 안 나감
    assert client.post("/voice/call").status_code == 401
    with env.repo.session(U1) as s:
        s.delete("consents")
    assert client.post("/voice/call", headers=H1).json()["error"]["code"] == "consent_required" and eleven.calls == []


def test_call_opens_talk_and_gives_tokens(client, env, eleven):  # noqa: F811
    out = call(client)
    assert set(out) == {"conversation_id", "first_line", "conversation_token", "call_token"}
    assert out["conversation_token"] == "lk-conv-token"
    assert eleven.calls == [{"url": "https://api.elevenlabs.io/v1/convai/conversation/token", "params": {"agent_id": "agent_test"},
                             "headers": {"xi-api-key": "test-key"}}]
    c = client.get(f"/talk/{out['conversation_id']}", headers=H1).json()            # POST /talk 와 같은 대화(첫 말 = first_line)
    assert c["turn_count"] == 0 and c["turns"][0]["role"] == "keeper" and c["turns"][0]["text"] == out["first_line"]
    assert voice_call.read_token(out["call_token"]) == (U1, out["conversation_id"])
    assert len(out["call_token"]) < 200 and KEY not in out["call_token"]
    for bad in (500, 401, "down"):
        eleven.status = bad
        r = client.post("/voice/call", headers=H1)
        assert r.status_code == 502 and r.json()["error"]["code"] == "call_failed"
    logs = "".join(p.read_text() for p in env.logs.glob("*.log"))
    assert "elevenlabs_call" in logs and "test-key" not in logs and "lk-conv-token" not in logs


def test_llm_rejects_bad_key_and_bad_token(client, env, eleven, talk, monkeypatch):  # noqa: F811
    out = call(client)
    tok, cid = out["call_token"], out["conversation_id"]
    for h in ({}, {"Authorization": "Bearer nope"}, {"Authorization": KEY}, {"Authorization": f"Bearer {KEY}x"}):
        r = ask(client, tok, "아침에 걸었다.", h=h)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized", h
    body, sig = tok.split(".")
    other = voice_call.call_token(U1, "c_other")
    expired = voice_call.call_token(U1, cid, now=time.time() - voice_call.CALL_TTL_S - 1)
    for t in (None, "", "x", f"{body}.{sig[:-2]}AA", f"{other.split('.')[0]}.{sig}", expired, f"{tok}.x"):
        r = ask(client, t, "아침에 걸었다.")
        assert r.status_code == 401 and r.json()["error"]["code"] == "bad_call_token", t
    monkeypatch.setattr(config, "VOICE_LLM_KEY", "rotated-key")                     # 키를 바꾸면 옛 통화 표도 못 씀
    assert ask(client, tok, "x", h={"Authorization": "Bearer rotated-key"}).json()["error"]["code"] == "bad_call_token"
    monkeypatch.setattr(config, "VOICE_LLM_KEY", "")
    assert ask(client, tok, "x", h={"Authorization": "Bearer "}).status_code == 401  # 키가 없으면 아무도 못 부름
    assert client.get(f"/talk/{cid}", headers=H1).json()["turn_count"] == 0 and talk.reply_calls == []


def test_llm_runs_one_talk_turn_stream_and_json(client, env, eleven, talk):  # noqa: F811
    out = call(client)
    tok, cid = out["call_token"], out["conversation_id"]
    r = ask(client, tok, "민준이랑 아침에 30분 걸었다.")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    parts = sse(r.text)
    assert parts[-1] == "[DONE]"
    chunks = [json.loads(p) for p in parts[:-1]]
    assert all(c["object"] == "chat.completion.chunk" and c["id"] == chunks[0]["id"] for c in chunks)
    assert chunks[0]["choices"][0]["delta"] == {"role": "assistant", "content": ""}
    assert chunks[-1]["choices"][0] == {"index": 0, "delta": {}, "finish_reason": "stop"}
    said = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
    c = client.get(f"/talk/{cid}", headers=H1).json()                             # 글 대화와 같은 저장(via=voice)
    assert c["turn_count"] == 1 and [t["role"] for t in c["turns"]] == ["keeper", "user", "keeper"]
    assert c["turns"][1]["text"] == "민준이랑 아침에 30분 걸었다." and c["turns"][1]["via"] == "voice"
    assert said == c["turns"][-1]["text"] and said != voice_call.FALLBACK
    r = client.post(LLM, headers=BEARER, json={"messages": [{"role": "user", "content": [{"type": "text", "text": "공원을 한 바퀴 돌았다."}]}],
                                               "elevenlabs_extra_body": {"call_token": tok}})   # stream 없음 → JSON
    j = r.json()
    assert r.status_code == 200 and j["object"] == "chat.completion" and j["choices"][0]["finish_reason"] == "stop"
    c = client.get(f"/talk/{cid}", headers=H1).json()
    assert c["turn_count"] == 2 and j["choices"][0]["message"] == {"role": "assistant", "content": c["turns"][-1]["text"]}
    assert len(talk.reply_calls) == 2
    sent = "\n".join(env.fake.sent)
    assert not [n for n in NAMES if n in sent]                                     # 전화로 한 말도 대화 요청엔 실명 0건
    logs = "".join(p.read_text() for p in env.logs.glob("*.log"))
    assert "voice_llm" in logs and "민준" not in logs and KEY not in logs


def test_llm_never_drops_the_call(client, env, eleven, talk):  # noqa: F811
    out = call(client)
    tok, cid = out["call_token"], out["conversation_id"]
    for role, said in (("assistant", "아침에 걸었다."), ("user", "  \x00 ")):                 # 사용자 말이 아니거나 빈 말 → 빈 답
        j = ask(client, tok, said, stream=False, role=role).json()
        assert j["choices"][0]["message"] == {"role": "assistant", "content": ""}
    talk.fail = True                                                               # 턴 실패 → 오류 대신 말 한 줄, 저장 안 함
    parts = sse(ask(client, tok, "아침에 걸었다.").text)
    assert parts[-1] == "[DONE]" and json.loads(parts[1])["choices"][0]["delta"]["content"] == voice_call.FALLBACK
    talk.fail = False
    talk.queue.append({"reply": "많이 힘들었겠어요. 이렇게 말해 줘서 고마워요. 여기 함께 있을게요.", "found": False})
    j = ask(client, tok, CRISIS[1], stream=False).json()                          # 위기 턴은 오류가 아니라 위로 답
    c = client.get(f"/talk/{cid}", headers=H1).json()
    assert c["turn_count"] == 1 and c["turns"][-1]["mode"] == "comfort"
    assert j["choices"][0]["message"]["content"] == c["turns"][-1]["text"] != voice_call.FALLBACK
    other = call(client, h=H2)                                                     # 남의 대화 id 를 든 표 → 찾지 못함, 저장 안 함
    j = ask(client, voice_call.call_token(U1, other["conversation_id"]), "아침에 걸었다.", stream=False).json()
    assert "찾지 못했어요" in j["choices"][0]["message"]["content"]
    assert client.get(f"/talk/{other['conversation_id']}", headers=H2).json()["turn_count"] == 0



def test_llm_streams_reply_before_save(client, env, eleven, talk):  # noqa: F811
    """별지기 답은 채움 말 없이 그대로 한 조각(2026-11-03 동규 「음은 어색함」), 같은 대화의 턴은 차례로 저장."""
    out = call(client)
    tok, cid = out["call_token"], out["conversation_id"]
    chunks = [json.loads(p) for p in sse(ask(client, tok, "아침에 걸었다.").text)[:-1]]
    said = [c["choices"][0]["delta"].get("content") for c in chunks if c["choices"][0]["delta"].get("content")]
    c = client.get(f"/talk/{cid}", headers=H1).json()
    assert said == [c["turns"][-1]["text"]] and c["turn_count"] == 1
