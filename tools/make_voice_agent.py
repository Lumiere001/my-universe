"""전화처럼 이야기하기(app/api/voice_call.py)에 쓸 ElevenLabs 에이전트를 만든다. 한 번만 돌린다(다시 돌리면 에이전트가 하나 더 생김).

    ELEVENLABS_AGENTS_KEY=… VOICE_LLM_KEY=… uv run --frozen python tools/make_voice_agent.py

키는 환경변수(또는 .env)에서만 읽고 화면에 내보내지 않는다. 키에는 ElevenAgents(쓰기) 권한이 있어야 한다.
1) VOICE_LLM_KEY 를 ElevenLabs 작업 공간 비밀(SECRET_NAME)로 올린다(있으면 값을 바꿈).
2) 에이전트를 만든다: 한국어, 첫 말 = 화면이 넘기는 {{first_line}}, 말은 우리 서버(Custom LLM)가 만들고, 목소리는 config.TTS_VOICE_ID ·
   eleven_flash_v2_5(한국어 되는 저지연 모델), 서명된 대화 표로만 열림, 녹음 · 대화 기록 남기지 않음.
3) 새 에이전트 id 를 출력한다 → Vercel(백엔드) 환경변수 ELEVENLABS_AGENT_ID 에 넣는다.
필드 이름은 https://elevenlabs.io/docs/api-reference/agents/create (2026-11-03 확인). 확인하지 못한 것은 줄 끝에 '확인 못 함'.
"""
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core import config  # noqa: E402

BASE = "https://api.elevenlabs.io/v1"
SECRET_NAME = "MY_UNIVERSE_VOICE_LLM_KEY"
LLM_URL = "https://my-universe-api.vercel.app/voice/llm"   # ElevenLabs 가 /chat/completions 를 붙인다(Groq 안내의 base URL 예와 같음)
TTS_MODEL = "eleven_flash_v2_5"   # 한국어 · 약 100ms(docs/models). 더 풍부한 목소리는 eleven_v4_turbo


def need(name):
    v = getattr(config, name)
    if not v:
        sys.exit(f"{name} 가 없어요(환경변수 또는 .env).")
    return v


def secret_id(h):
    """VOICE_LLM_KEY 를 작업 공간 비밀로(GET · POST /convai/secrets, PATCH /convai/secrets/{id}). 오류 본문은 값이 섞일 수 있어 찍지 않는다."""
    body = {"name": SECRET_NAME, "value": need("VOICE_LLM_KEY")}
    r = httpx.get(f"{BASE}/convai/secrets", headers=h, timeout=30)
    if r.status_code != 200:
        sys.exit(f"비밀 목록을 못 읽었어요(HTTP {r.status_code}).")
    old = next((x["secret_id"] for x in r.json()["secrets"] if x["name"] == SECRET_NAME), None)   # 첫 쪽만 봄(next_cursor 무시)
    r = (httpx.patch(f"{BASE}/convai/secrets/{old}", headers=h, json={"type": "update", **body}, timeout=30) if old else
         httpx.post(f"{BASE}/convai/secrets", headers=h, json={"type": "new", **body}, timeout=30))
    if r.status_code != 200:
        sys.exit(f"비밀을 {'바꾸지' if old else '만들지'} 못했어요(HTTP {r.status_code}).")
    print(f"비밀 {SECRET_NAME}: {'값 바꿈' if old else '새로 만듦'}")
    return r.json()["secret_id"]


def agent(sid):
    return {
        "name": "나의 우주 별지기(전화)",
        "conversation_config": {
            "agent": {
                "first_message": "{{first_line}}",   # POST /voice/call 의 first_line(화면이 dynamicVariables 로 넘김)
                "language": "ko",   # 받아쓰기 · 목소리 언어
                "dynamic_variables": {"dynamic_variable_placeholders": {"first_line": "오늘 하루는 어땠어요?"}},   # 미리 듣기용
                "prompt": {   # custom_llm 이 prompt 아래인 것은 스키마 정의로 추론(예시 본문 없음, 확인 못 함)
                    "prompt": "별지기의 말은 우리 서버가 만든다. 이 글은 쓰지 않는다.",
                    "llm": "custom-llm",
                    "custom_llm": {"url": LLM_URL, "model_id": "my-universe", "api_key": {"secret_id": sid},
                                   "api_type": "chat_completions"},   # api_key 가 'Authorization: Bearer' 로 오는 것은 OpenAI 호환 관례(확인 못 함)
                },
            },
            "tts": {"model_id": TTS_MODEL, "voice_id": config.TTS_VOICE_ID},
            "turn": {"speculative_turn": False},   # 말이 끝나기 전에 미리 부르면 한 차례가 두 턴으로 저장될 수 있어 끈다(기본도 꺼짐)
        },
        "platform_settings": {
            "auth": {"enable_auth": True},   # 서명된 대화 표(GET /convai/conversation/token, POST /voice/call 이 받음)로만 열림
            "overrides": {"custom_llm_extra_body": True},   # 화면의 customLlmExtraBody(call_token)를 우리 서버로 넘김
            # 0일 보관이 받아들여지는지는 확인 못 함(문서는 -1 = 무기한만 밝힘). 거절되면 1로
            "privacy": {"record_voice": False, "retention_days": 0, "delete_audio": True, "delete_transcript_and_pii": True},
        },
    }


def main():
    h = {"xi-api-key": need("ELEVENLABS_AGENTS_KEY")}   # ElevenAgents(작성) 권한 키(없으면 ELEVENLABS_API_KEY)
    sid = secret_id(h)
    r = httpx.post(f"{BASE}/convai/agents/create", headers=h, json=agent(sid), timeout=60)
    if r.status_code != 200:
        sys.exit(f"에이전트를 못 만들었어요(HTTP {r.status_code}): {r.text[:2000]}")   # 비밀 값은 본문에 없음(secret_id 만)
    print(f"ELEVENLABS_AGENT_ID={r.json()['agent_id']}")


if __name__ == "__main__":
    main()
