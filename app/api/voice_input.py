"""
app/api/voice_input.py

말로 쓰기 · 읽어 주기(WS21).
- POST /voice/transcribe: 녹음 조각 하나(본문 그대로, VOICE_MAX_BYTES 아래) → 받아쓴 글. 서버는 조각을 모으지 않는다:
  Vercel 본문 한도(4.5MB) 때문에 긴 녹음은 화면(components/MicButton.tsx)이 16kHz 모노 WAV 2분 조각으로 나눠 하나씩 보내고
  받아쓴 글을 이어 붙인다. 녹음은 받아쓴 뒤 바로 버린다(저장 · 로그 0). 받아쓴 글은 화면이 대화 턴(via=voice)이나 쓰기 칸으로
  넣어 기존 길(위기 판정 · 가명 처리 · 요약 확인)을 그대로 탄다.
- POST /voice/speak: 별지기 말 → mp3(읽어 주기, 화면에서 켜고 끔).
ElevenLabs 로 나가므로 동의를 먼저 본다. 비용은 runs(step stt · tts)에 분 · 글자 단위 추정으로 남긴다.
"""

import time

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field
from starlette.concurrency import run_in_threadpool

from app.api import consent
from app.core import config
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import In
from app.repository import diary
from app.service import stt

router = APIRouter(tags=["음성"])
TOO_LARGE = "녹음이 너무 커요. 화면을 새로 고친 뒤 다시 올려 주세요."
FAILED = {"unconfigured": (503, "voice_unconfigured", "지금은 말로 하기를 쓸 수 없어요. 운영자에게 알려 주세요."),
          "stt": (502, "stt_failed", "받아쓰지 못했어요. 잠시 뒤 다시 해 주세요."),
          "tts": (502, "tts_failed", "읽어 주지 못했어요. 글은 그대로 볼 수 있어요.")}


class SpeakIn(In):
    text: str = Field(min_length=1, max_length=2000)


async def _body(request):
    """본문을 VOICE_MAX_BYTES 까지만 읽는다(넘으면 413, 끝까지 받지 않음)."""
    if int(request.headers.get("content-length") or 0) > config.VOICE_MAX_BYTES:
        raise ApiError(413, "too_large", TOO_LARGE)
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > config.VOICE_MAX_BYTES:
            raise ApiError(413, "too_large", TOO_LARGE)
    return bytes(buf)


def _fail(repo, uid, step, t0, e):
    status, code, msg = FAILED["unconfigured" if e.code == "unconfigured" else step]
    with repo.session(uid) as s:
        diary.add_run(s, None, step, (time.time() - t0) * 1000, 0 if e.code == "unconfigured" else 1, 0.0, code)
    raise ApiError(status, code, msg)


def _transcribe(repo, uid, audio):
    with repo.session(uid) as s:
        consent.check(s)
    fmt = stt.kind(audio)
    if not fmt:
        raise ApiError(415, "bad_format", "m4a · mp3 · wav · webm 녹음만 받아요.")
    t0 = time.time()
    try:
        out = stt.transcribe(audio, fmt)
    except stt.SpeechError as e:
        _fail(repo, uid, "stt", t0, e)
    with repo.session(uid) as s:
        diary.add_run(s, None, "stt", (time.time() - t0) * 1000, 1, out["usd"], None,
                      {"seconds": round(out["seconds"], 1), "bytes": len(audio), "format": fmt})
    return {"text": out["text"], "seconds": round(out["seconds"], 1)}


@router.post("/voice/transcribe", summary="녹음 조각 하나 받아쓰기(본문 = 녹음 바이트, 4MB 아래)")
async def transcribe(request: Request, user=Depends(get_user), repo=Depends(get_repo)):
    return await run_in_threadpool(_transcribe, repo, user["id"], await _body(request))


@router.post("/voice/speak", summary="별지기 말 읽어 주기(mp3)", response_class=Response)
def speak(body: SpeakIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        consent.check(s)
    t0 = time.time()
    try:
        audio, usd = stt.speak(body.text)
    except stt.SpeechError as e:
        _fail(repo, user["id"], "tts", t0, e)
    with repo.session(user["id"]) as s:
        diary.add_run(s, None, "tts", (time.time() - t0) * 1000, 1, usd, None, {"chars": len(body.text)})
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
