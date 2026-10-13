"""WS21 말로 쓰기 · 읽어 주기: 녹음 조각 받아쓰기(ElevenLabs 가짜) → 대화 턴(via=voice) · 긴 이야기는 바로 '지금까지 정리' →
정리하기 → 요약 확인(source=대화). 녹음은 어디에도 남지 않음, 4MB 넘는 조각은 거절(화면이 나눠 보냄), 형식 검사, 동의,
분 · 글자 단위 비용 기록. 외부 호출은 모두 가짜, 가상 인물 글만."""
import io
import json
import wave

import httpx
import pytest

from app.core import config
from app.service import stt
from tests.test_api_flow import H1, client, events  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import U1, env  # noqa: F401  (env 픽스처)
from tests.test_ws19_talk import last, say, start, talk  # noqa: F401  (talk 픽스처)
from tests.test_ws20_confirm import finish

LONG = ("오늘은 아침 일찍 일어나서 공원을 한 바퀴 걸었다. 바람이 차가웠지만 기분이 맑아졌다. " * 8).strip()   # 녹음으로 한 긴 이야기


def wav(seconds, rate=16000, sound=False):
    n = int(seconds * rate) * 2
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((bytes(range(256)) * (n // 256 + 1))[:n] if sound else bytes(n))
    return b.getvalue()


@pytest.fixture
def eleven(monkeypatch):
    """httpx.post 를 가짜로: 받아쓰기는 queue 의 글을 차례로, 읽어 주기는 mp3 바이트. calls 에 보낸 것(바이트 포함)을 남긴다."""
    st = type("S", (), {"queue": [], "calls": [], "fail": False})()

    def post(url, headers=None, files=None, data=None, json=None, params=None, timeout=None):
        st.calls.append({"url": url, "headers": headers, "files": files, "data": data, "json": json, "params": params})
        if st.fail:
            return httpx.Response(500, json={"detail": "down"})
        if url.endswith("/speech-to-text"):
            text = st.queue.pop(0) if st.queue else "아침에 공원을 걸었어요."
            return httpx.Response(200, json={"text": text, "language_code": "kor",
                                             "words": [{"text": "x", "type": "word", "start": 0.1, "end": 61.2}]})
        return httpx.Response(200, content=b"ID3fake-mp3")

    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(stt.httpx, "post", post)
    return st


def send(client, body, h=H1, ctype="audio/wav"):  # noqa: F811
    return client.post("/voice/transcribe", headers={**h, "Content-Type": ctype}, content=body)


def vsay(client, cid, text):  # noqa: F811
    r = client.post(f"/talk/{cid}/turn/stream", headers=H1, json={"text": text, "via": "voice"})
    return last(events(r.text))


def runs(env, step):  # noqa: F811
    with env.repo.session(U1) as s:
        return s.rows("runs", step=step)


def test_kind_by_bytes():
    assert stt.kind(wav(0.1)) == "wav"
    assert stt.kind(b"\x00\x00\x00\x20ftypM4A ") == "m4a"          # 휴대폰 음성 메모 · 사파리 녹음
    assert stt.kind(b"\x1a\x45\xdf\xa3\x01") == "webm"              # 크롬 녹음
    assert stt.kind(b"OggS\x00") == "ogg"                           # 파이어폭스 녹음
    assert stt.kind(b"ID3\x04") == "mp3" and stt.kind(b"\xff\xfb\x90") == "mp3"
    assert stt.kind(b"%PDF-1.7") is None and stt.kind(b"") is None
    assert stt.wav_seconds(wav(2.5)) == 2.5 and stt.wav_seconds(b"junk") == 0.0


def test_transcribe_sends_korean_scribe_and_keeps_no_audio(client, env, eleven):  # noqa: F811
    audio = wav(90, sound=True)
    r = send(client, audio)
    assert r.status_code == 200, r.text
    assert r.json() == {"text": "아침에 공원을 걸었어요.", "seconds": 90.0}       # WAV 는 머리말 길이(낱말 끝 61.2초 아님)
    c = eleven.calls[-1]
    assert c["url"] == "https://api.elevenlabs.io/v1/speech-to-text" and c["headers"] == {"xi-api-key": "test-key"}
    assert c["data"] == {"model_id": "scribe_v2", "language_code": "ko", "tag_audio_events": "false", "diarize": "false"}
    assert c["files"]["file"][1] == audio and c["files"]["file"][2] == "audio/wav"
    [run] = runs(env, "stt")                                                     # 원장: 분 단위 비용, 원문 · 녹음 없음
    assert run["calls"] == 1 and run["est_usd"] == round(1.5 * config.PRICE_STT_PER_MIN, 5)
    assert run["meta"] == {"seconds": 90.0, "bytes": len(audio), "format": "wav"}
    values = [v for rows in env.repo.store.tables.values() for row in rows for v in row.values()]
    assert not any(audio[1000:1300] in bytes(v) for v in values if isinstance(v, (bytes, bytearray, memoryview)))
    assert "공원" not in json.dumps(env.repo.store.tables, default=str, ensure_ascii=False)   # 서버 저장 0(녹음 · 받아쓴 글)
    logs = "".join(p.read_text() for p in env.logs.glob("*.log"))
    assert "elevenlabs_stt" in logs and "공원" not in logs                       # 로그엔 길이 · 크기만


def test_non_wav_seconds_from_words(client, env, eleven):  # noqa: F811
    r = send(client, b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 100, ctype="audio/x-m4a")
    assert r.status_code == 200 and r.json()["seconds"] == 61.2
    assert eleven.calls[-1]["files"]["file"][2] == "audio/mp4"


def test_input_checks_size_format_consent_key(client, env, eleven, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "VOICE_MAX_BYTES", 1000)
    r = send(client, wav(1))                                                     # 32KB > 1000B
    assert r.status_code == 413 and r.json()["error"]["code"] == "too_large"
    monkeypatch.setattr(config, "VOICE_MAX_BYTES", 4 * 1024 * 1024)
    assert send(client, b"%PDF-1.7 not audio").json()["error"]["code"] == "bad_format"
    assert send(client, b"").status_code == 415
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "")
    r = send(client, wav(1))
    assert r.status_code == 503 and r.json()["error"]["code"] == "voice_unconfigured"
    monkeypatch.setattr(config, "ELEVENLABS_API_KEY", "test-key")
    eleven.fail = True
    r = send(client, wav(1))
    assert r.status_code == 502 and r.json()["error"]["code"] == "stt_failed"
    assert [x["error_code"] for x in runs(env, "stt")] == ["voice_unconfigured", "stt_failed"]
    eleven.fail = False
    with env.repo.session(U1) as s:
        s.delete("consents")
    n = len(eleven.calls)
    assert send(client, wav(1)).json()["error"]["code"] == "consent_required" and len(eleven.calls) == n   # 동의 전엔 안 나감
    assert client.post("/voice/speak", headers=H1, json={"text": "안녕"}).status_code == 403
    assert send(client, wav(1), h={}).status_code == 401


def test_over_4_5mb_recording_goes_through_in_pieces(client, env, eleven):  # noqa: F811
    """Vercel 본문 한도: 3분 44.1kHz WAV(약 16MB)는 한 번에 못 보냄 → 화면처럼 16kHz 모노 2분 조각으로 나눠 보내면 끝까지 된다."""
    whole = wav(180, rate=44100)
    assert len(whole) > 4.5 * 1024 * 1024
    assert send(client, whole).status_code == 413
    pieces = [wav(120), wav(60)]                                                 # MicButton 의 PIECE_S(120초) 조각
    assert all(len(p) < config.VOICE_MAX_BYTES for p in pieces)
    eleven.queue = ["아침에 공원을 걸었다.", "바람이 차가웠지만 기분이 맑아졌다."]
    text = " ".join(send(client, p).json()["text"] for p in pieces)
    assert text == "아침에 공원을 걸었다. 바람이 차가웠지만 기분이 맑아졌다."
    assert sum(r["meta"]["seconds"] for r in runs(env, "stt")) == 180.0


def test_voice_turns_summary_and_confirm(client, env, talk, eleven):  # noqa: F811
    """짧은 턴 2개 + 긴 녹음 이야기 → 대화 턴(via=voice) · 긴 이야기는 바로 '지금까지 정리' → 정리하기 → 요약 확인 → 저장."""
    c = start(client)
    eleven.queue = ["오늘 아침에 공원을 걸었어요.", "민준이가 같이 걷자고 해서 고마웠어요.", LONG]
    for i in range(2):
        said = send(client, wav(5)).json()["text"]
        v = vsay(client, c["id"], said)
        assert v["turns"][-2] == {**v["turns"][-2], "role": "user", "text": said, "via": "voice"}
    assert v["summary"] == ""                                                    # 짧은 말 둘: 아직 정리 전
    v = vsay(client, c["id"], send(client, wav(120)).json()["text"])   # 2분 조각 하나
    assert v["summary"] == talk.summary                                          # 긴 이야기는 바로 정리에 담음
    assert len(talk.reply_calls) == 3
    ctx = talk.reply_calls[-1][-1]["content"]
    assert "공원을 한 바퀴" in ctx                                                 # 별지기는 받아쓴 이야기를 들고 이어 물음
    assert "민준" not in "\n".join(env.fake.sent)                                 # 받아쓴 말도 대화 요청엔 실명 0건
    kind, r = finish(client, c["id"])[-1]
    assert kind == "result" and r["status"] == "confirm" and r["source"] == "대화"   # WS20 확인 화면으로
    done = client.post(f"/diary/{r['id']}/confirm", headers=H1, json={"agreed": ["summary"]}).json()
    assert done["confirmed"] == "확인됨"
    assert client.post(f"/talk/{c['id']}/turn/stream", headers=H1, json={"text": "x", "via": "phone"}).status_code == 422


def test_text_turn_stays_text(client, env, talk):  # noqa: F811
    c = start(client)
    v = last(say(client, c["id"], "아침에 걸었다."))
    assert v["turns"][-2]["via"] == "text"                                        # 글로 쓴 말은 그대로(회귀)


def test_speak_reads_keeper_line(client, env, eleven):  # noqa: F811
    r = client.post("/voice/speak", headers=H1, json={"text": "오늘 아침 공기가 좋았겠어요."})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake-mp3"
    c = eleven.calls[-1]
    assert c["url"] == f"https://api.elevenlabs.io/v1/text-to-speech/{config.TTS_VOICE_ID}"
    assert c["json"] == {"text": "오늘 아침 공기가 좋았겠어요.", "model_id": "eleven_multilingual_v2"}
    assert c["params"] == {"output_format": "mp3_44100_64"}
    [run] = runs(env, "tts")                                                     # 글자 단위 비용, 글은 안 남김
    n = len("오늘 아침 공기가 좋았겠어요.")
    assert run["meta"] == {"chars": n} and run["est_usd"] == round(n / 1000 * config.PRICE_TTS_PER_1K_CHARS, 5)
    assert "공기" not in json.dumps(env.repo.store.tables, default=str, ensure_ascii=False)
    assert client.post("/voice/speak", headers=H1, json={"text": "가" * 2001}).status_code == 422
    eleven.fail = True
    assert client.post("/voice/speak", headers=H1, json={"text": "안녕"}).json()["error"]["code"] == "tts_failed"
