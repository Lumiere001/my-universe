"""
app/api/voice_call.py

전화처럼 이야기하기(ElevenLabs Agents, 2026-11-03). 목소리 · 받아쓰기 · 말 차례는 ElevenLabs 가 맡고, 별지기의 말은 우리 대화 그래프가
만든다(Custom LLM). 그래서 가명 처리 · 위기 판정 · 대화 저장은 글로 하는 이야기하기(app/api/chat.py)와 같은 길을 탄다.
- POST /voice/call: 새 대화를 열고(POST /talk 와 같음) ElevenLabs WebRTC 대화 표(conversation_token)와 우리 통화 표(call_token)를 준다.
  화면은 conversation_token 으로 ElevenLabs 에 붙으며 first_line 을 dynamicVariables.first_line 으로(에이전트 첫 말 "{{first_line}}"),
  call_token 을 customLlmExtraBody.call_token 으로 넘긴다.
- POST /voice/llm/chat/completions: ElevenLabs 서버가 사용자 말 한 차례마다 부르는 OpenAI 호환 주소(에이전트 설정 url 은 .../voice/llm,
  /chat/completions 는 ElevenLabs 가 붙임). 로그인 대신 VOICE_LLM_KEY(Bearer)와 통화 표(elevenlabs_extra_body.call_token)로
  누구의 어느 대화인지 안다. 한 턴을 via=voice 로 돌려 별지기 답을 준다. 턴이 실패해도 HTTP 오류 대신 짧은 말 한 줄(통화가 끊기지 않게).
통화 표 = base64url(JSON{u, c, e}).base64url(HMAC-SHA256). 서명 키는 VOICE_LLM_KEY 에서 용도 문자열을 달리해 뽑는다(새 비밀값 없음).
"""

import base64
import contextvars
import hashlib
import hmac
import json
import queue
import threading
import time
import uuid
from collections import defaultdict
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api import chat as chat_api
from app.core import config, logger
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import CONTROL, TalkIn
from app.service import stt

router = APIRouter(tags=["음성"])
CALL_TTL_S = 20 * 60
FALLBACK = "미안해요, 잠깐 말을 놓쳤어요. 한 번만 다시 말해 줄래요?"
# 답이 이만큼(초) 안에 안 나오면 짧은 소리부터 내보낸다(2026-11-03 동규 「말하면 바로 반응을 안 함」). ElevenLabs 가 바로 읽기 시작한다
FILLER_AFTER, FILLER = 1.5, "음… "
# 같은 대화의 턴은 차례로(말을 끊고 또 말해 ElevenLabs 가 새로 불러도 앞 턴이 저장된 뒤에). ponytail: 한 서버 안에서만 지킴, 여러 대에 걸치면 DB 잠금
_TURN_LOCKS: defaultdict = defaultdict(threading.Lock)


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _sign(body):
    key = hmac.new(config.VOICE_LLM_KEY.encode(), b"my-universe/call-token/v1", hashlib.sha256).digest()
    return _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())


def call_token(uid, cid, now=None):
    body = _b64(json.dumps({"u": str(uid), "c": cid, "e": int((now or time.time()) + CALL_TTL_S)}, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"


def read_token(tok):
    """통화 표 → (uid, 대화 id). 서명이 틀리거나 시간이 지났으면 401."""
    try:
        body, sig = str(tok).split(".")
        if not hmac.compare_digest(sig.encode(), _sign(body).encode()):
            raise ValueError
        d = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if d["e"] < time.time():
            raise ValueError
        return d["u"], d["c"]
    except Exception:
        raise ApiError(401, "bad_call_token", "대화가 끝났어요. 다시 시작해 주세요.") from None


@router.post("/voice/call", summary="전화처럼 이야기하기 시작: 새 대화 + ElevenLabs 대화 표 + 우리 통화 표")
def call(body: TalkIn | None = None, user=Depends(get_user), repo=Depends(get_repo)):
    if not (config.ELEVENLABS_AGENT_ID and config.VOICE_LLM_KEY and config.ELEVENLABS_AGENTS_KEY):
        raise ApiError(503, "call_unconfigured", "지금은 목소리로 이야기할 수 없어요. 운영자에게 알려 주세요.")
    c = chat_api.start(body, user, repo)   # POST /talk 와 같음(동의 · 말 없이 둔 대화 치우기 · 첫 말)
    failed = ApiError(502, "call_failed", "목소리 대화를 열지 못했어요. 잠시 뒤 다시 해 주세요.")
    try:
        r = httpx.get(f"{stt.BASE}/convai/conversation/token", params={"agent_id": config.ELEVENLABS_AGENT_ID},
                      headers={"xi-api-key": config.ELEVENLABS_AGENTS_KEY}, timeout=10)
    except httpx.HTTPError as e:
        logger.log("error", step="voice_call", code="call_failed", what=type(e).__name__)
        raise failed from None
    token = (r.json() if r.status_code == 200 else {}).get("token")
    if not token:
        logger.log("error", step="voice_call", code="call_failed", http=r.status_code)
        raise failed
    logger.log("external", what="elevenlabs_call")
    return {"conversation_id": c["id"], "first_line": c["turns"][0]["text"], "conversation_token": token,
            "call_token": call_token(user["id"], c["id"])}


class LlmIn(BaseModel):
    """ElevenLabs Custom LLM 요청(OpenAI chat completions 모양). 쓰는 칸만 읽고 나머지(tools · temperature …)는 버린다."""
    messages: list[dict] = []
    stream: bool = False
    model: Optional[str] = None
    elevenlabs_extra_body: Optional[dict] = None   # 화면의 customLlmExtraBody 가 이 이름으로 온다


def _llm_key(authorization: str = Header(default="")):
    if not (config.VOICE_LLM_KEY and hmac.compare_digest(authorization.encode(), f"Bearer {config.VOICE_LLM_KEY}".encode())):
        raise ApiError(401, "unauthorized", "이 요청은 처리할 수 없어요.")


def _said(messages):
    """마지막 말이 사용자 말이면 그 글(ElevenLabs 가 받아쓴 글), 아니면 빈 글."""
    m = messages[-1] if messages else {}
    if m.get("role") != "user":
        return ""
    c = m.get("content") or ""
    if isinstance(c, list):   # OpenAI 조각 모양 [{"type": "text", "text": ...}]
        c = " ".join(str(p.get("text") or "") for p in c if isinstance(p, dict))
    return CONTROL.sub("", str(c)).strip()[:config.MAX_TEXT_CHARS]


def _turn(repo, uid, cid, text):
    """한 턴을 따로 돌린다 → 큐: ("reply", 별지기 말)이 답이 나오자마자, ("end", run_turn 결과)가 저장까지 끝난 뒤."""
    q = queue.Queue()

    def work():
        with _TURN_LOCKS[cid]:
            q.put(("end", chat_api.run_turn(repo, uid, cid, text, "voice", on_reply=lambda t: q.put(("reply", t)))))
    threading.Thread(target=contextvars.copy_context().run, args=(work,), name=f"voice-{cid}", daemon=True).start()
    return q


def _reply(repo, uid, cid, text):
    """한 턴(via=voice) → 별지기 말. 못 하면 짧은 말 한 줄(통화는 이어 감). 위기 턴은 그래프가 위로 답을 준다(오류 아님)."""
    if not text:
        return ""
    t0 = time.time()
    try:
        chat_api._check(repo, uid, cid)   # 대화가 있는지 · 동의(글 턴과 같음)
    except ApiError as e:
        logger.log("error", step="voice_llm", code=e.code)
        return e.message
    ev, data = chat_api.run_turn(repo, uid, cid, text, "voice")
    logger.log("step", step="voice_llm", ms=int((time.time() - t0) * 1000), code=None if ev == "turn" else data["code"])
    return data["turns"][-1]["text"] if ev == "turn" else FALLBACK


@router.post("/voice/llm/chat/completions", summary="ElevenLabs Custom LLM(OpenAI 호환): 사용자 말 한 차례 → 별지기 답",
             dependencies=[Depends(_llm_key)])
def llm(body: LlmIn, repo=Depends(get_repo)):
    uid, cid = read_token((body.elevenlabs_extra_body or {}).get("call_token"))
    said = _said(body.messages)
    head = {"id": f"chatcmpl-{uuid.uuid4().hex}", "created": int(time.time()), "model": body.model or "my-universe"}
    if not body.stream:
        return {**head, "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": _reply(repo, uid, cid, said)},
                             "finish_reason": "stop"}]}

    def chunk(delta, finish=None):
        return "data: " + json.dumps({**head, "object": "chat.completion.chunk",
                                      "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}, ensure_ascii=False) + "\n\n"

    def gen():
        yield chunk({"role": "assistant", "content": ""})   # 첫 조각은 바로(턴은 몇 초 걸림)
        if said:
            try:
                chat_api._check(repo, uid, cid)   # 대화가 있는지 · 동의(글 턴과 같음)
            except ApiError as e:
                logger.log("error", step="voice_llm", code=e.code)
                said_back = e.message
            else:
                t0, q = time.time(), _turn(repo, uid, cid, said)
                try:
                    ev = q.get(timeout=FILLER_AFTER)
                except queue.Empty:
                    yield chunk({"content": FILLER})
                    ev = q.get()
                said_back = ev[1] if ev[0] == "reply" else None
                if said_back:
                    yield chunk({"content": said_back})   # 별지기 답을 먼저 읽게 하고, 정리 · 저장은 끝까지 기다린다
                end = q.get() if ev[0] == "reply" else ev
                ok = end[1][0] == "turn"
                logger.log("step", step="voice_llm", ms=int((time.time() - t0) * 1000), code=None if ok else end[1][1]["code"])
                said_back = None if said_back else FALLBACK
            if said_back:
                yield chunk({"content": said_back})
        yield chunk({}, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
