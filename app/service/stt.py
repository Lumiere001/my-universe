"""
app/service/stt.py

말로 쓰기 · 읽어 주기(WS21): ElevenLabs 받아쓰기(Scribe, 한국어)와 읽어 주기(TTS). 2026-10-13 동규 결정.
- 녹음은 메모리에서 바로 보내고 버린다(파일 · DB · 로그에 남기지 않음). 기록에는 길이 · 크기 · 형식 · 비용만.
- 목소리 · 읽을 글은 이름을 가릴 수 없어 실명 검사(llm.guard) 예외다 — 개인정보처리방침 · 첫 사용 동의에 밝혀 둠(WS24).
- 형식은 확장자 · Content-Type 이 아니라 파일 앞 바이트로 본다(m4a · mp3 · wav · webm, 브라우저 녹음 ogg).
"""

import io
import wave

import httpx

from app.core import config, logger

BASE = "https://api.elevenlabs.io/v1"
MIME = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/mp4", "webm": "audio/webm", "ogg": "audio/ogg"}


class SpeechError(Exception):
    """ElevenLabs 가 답하지 못함(키 없음 = unconfigured, 그 밖 = failed). 메시지에 녹음 · 글을 넣지 않는다."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def kind(b):
    """파일 앞 바이트 → 형식 이름, 모르면 None."""
    if b[:4] == b"RIFF" and b[8:12] == b"WAVE":
        return "wav"
    if b[4:8] == b"ftyp":
        return "m4a"
    if b[:4] == b"\x1aE\xdf\xa3":
        return "webm"
    if b[:4] == b"OggS":
        return "ogg"
    if b[:3] == b"ID3" or (len(b) > 1 and b[0] == 0xFF and b[1] & 0xE0 == 0xE0):
        return "mp3"
    return None


def wav_seconds(b):
    try:
        with wave.open(io.BytesIO(b)) as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


def _call(path, **kw):
    if not config.ELEVENLABS_API_KEY:
        raise SpeechError("unconfigured")
    try:
        r = httpx.post(f"{BASE}{path}", headers={"xi-api-key": config.ELEVENLABS_API_KEY}, timeout=120, **kw)
    except httpx.HTTPError as e:
        logger.log("error", step=path, code="speech_failed", what=type(e).__name__)
        raise SpeechError("failed") from None
    if r.status_code != 200:
        logger.log("error", step=path, code="speech_failed", http=r.status_code)
        raise SpeechError("failed")
    return r


def transcribe(audio, fmt):
    """녹음 바이트 → {"text", "seconds", "usd"}. seconds 는 WAV 머리말, 아니면 마지막 낱말이 끝난 때."""
    r = _call("/speech-to-text", files={"file": (f"voice.{fmt}", audio, MIME[fmt])},
              data={"model_id": config.STT_MODEL, "language_code": "ko", "tag_audio_events": "false", "diarize": "false"}).json()
    sec = wav_seconds(audio) if fmt == "wav" else 0.0
    sec = sec or max((w.get("end") or 0 for w in r.get("words") or []), default=0.0)
    usd = sec / 60 * config.PRICE_STT_PER_MIN
    logger.log("external", what="elevenlabs_stt", seconds=round(sec, 1), bytes=len(audio), format=fmt, est_usd=round(usd, 5))
    return {"text": (r.get("text") or "").strip(), "seconds": sec, "usd": usd}


def speak(text, voice=None):
    """글 → (mp3 바이트, 추정 비용). voice = 설정 tts_voice(목록 밖 · 없음이면 기본 목소리)."""
    vid = config.TTS_VOICES.get(voice) or config.TTS_VOICE_ID
    r = _call(f"/text-to-speech/{vid}", params={"output_format": "mp3_44100_64"},
              json={"text": text, "model_id": config.TTS_MODEL})
    usd = len(text) / 1000 * config.PRICE_TTS_PER_1K_CHARS
    logger.log("external", what="elevenlabs_tts", chars=len(text), est_usd=round(usd, 5))
    return r.content, usd
