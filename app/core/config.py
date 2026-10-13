"""
app/core/config.py

설정은 환경변수에서만 읽는다: .env(키, 동규가 넣음) 다음 .env.local(로컬 전용 값, scripts/dev_up.sh 가 만듦).
이미 잡힌 환경변수가 이긴다(배포 설정 · 시험). 키 값은 화면 · 로그에 내보내지 않는다.
"""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
_given = set(os.environ)
load_dotenv(BASE_DIR / ".env")
for _k, _v in dotenv_values(BASE_DIR / ".env.local").items():   # .env.local 이 .env 를 덮고, 이미 잡힌 환경변수는 못 덮는다
    if _k not in _given and _v is not None:
        os.environ[_k] = _v


def _int(name, default):
    return int(os.getenv(name) or default)


def _float(name, default):
    return float(os.getenv(name) or default)


VERSION = "0.8.0"

# Upstage (Solar Chat · Embedding · Studio)
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY", "")
UPSTAGE_BASE_URL = os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1")
STUDIO_BASE_URL = os.getenv("STUDIO_BASE_URL", "https://api.upstage.ai/v2")
CHAT_MODEL = os.getenv("SOLAR_CHAT_MODEL", "solar-pro4")
EMBED_PASSAGE_MODEL = os.getenv("EMBEDDING_MODEL", "solar-embedding-2-passage")
EMBED_QUERY_MODEL = os.getenv("EMBEDDING_QUERY_MODEL", EMBED_PASSAGE_MODEL.replace("-passage", "-query"))

# Studio 기록 · 관측 Agent. 1판(RECORD_CONFIG_ID=1)은 Streamlit 데모가 계속 쓰고, 새 백엔드는 V8_* (기본 2판).
RECORD_AGENT_ID = os.getenv("RECORD_AGENT_ID", "")
RECORD_CONFIG_ID = os.getenv("RECORD_CONFIG_ID", "1")
OBSERVE_AGENT_ID = os.getenv("OBSERVE_AGENT_ID", "")
OBSERVE_CONFIG_ID = os.getenv("OBSERVE_CONFIG_ID", "1")
V8_RECORD_CONFIG_ID = os.getenv("V8_RECORD_CONFIG_ID", "2")
V8_OBSERVE_CONFIG_ID = os.getenv("V8_OBSERVE_CONFIG_ID", "2")
STUDIO_TIMEOUT_S = _int("STUDIO_TIMEOUT_S", 180)

# Supabase(로그인 · 관계형 DB). 백엔드는 DATABASE_URL 로 붙고 요청마다 그 사용자로 RLS 를 건다.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")   # 계정 지우기(DELETE /me)에서만 쓴다
# 쉼표 목록. 있으면 목록 밖 계정은 403 not_allowed. 없으면 로그인한 누구나(지금 배포, 2026-10-08 동규).
ALLOWED_EMAILS = {e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()}
DATABASE_URL = os.getenv("DATABASE_URL", "")
# 운영 화면 /ops 를 볼 수 있는 구글 계정 이메일(쉼표 목록, WS22 · 결정 13). 비우면 아무도 못 본다(403 not_admin).
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
DIARY_ENC_KEY = os.getenv("DIARY_ENC_KEY", "")      # base64 32바이트. 사용자별 키는 HKDF(이 값, user_id)

# ChromaDB: CHROMA_API_KEY 가 있으면 Chroma Cloud, 없으면 CHROMA_HOST:CHROMA_PORT
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = _int("CHROMA_PORT", 8000)
CHROMA_API_KEY = os.getenv("CHROMA_API_KEY", "")
CHROMA_TENANT = os.getenv("CHROMA_TENANT", "")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "thoughts")

# 화면 · 실행 기록
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "0") == "1"     # 로컬 · Docker 는 1(logs/agent_flow_YYYYMMDD.log), Vercel 은 0(표준 출력)
LOG_DIR = Path(os.getenv("LOG_DIR") or BASE_DIR / "logs")
API_DOCS = os.getenv("API_DOCS", "0") == "1"           # /docs · /openapi.json. 로컬만 1(배포는 끔)

# 운영 한도(연구 근거 아님, 크레딧을 지키는 값)
MAX_TEXT_CHARS = _int("MAX_TEXT_CHARS", 8000)
MAX_TITLE_CHARS = _int("MAX_TITLE_CHARS", 120)
# 운영 상한: 0 = 없음(기본. 2026-10-08 동규 — 실제 배포 · 수익화를 생각할 때 사용량과 비즈니스 모델을 보고 정함). env 로 주면 건다.
DAILY_ENTRY_LIMIT = _int("DAILY_ENTRY_LIMIT", 0)          # 사용자별 하루 글 수
MONTHLY_COST_CAP_USD = _float("MONTHLY_COST_CAP_USD", 0)  # 사용자별 이번 달 추정 비용 상한(달러)
RESUME_LIMIT = _int("RESUME_LIMIT", 0)                     # 기록 하나당 '이어서 하기' 횟수
RUN_LOCK_S = _int("RUN_LOCK_S", 600)                       # 실행 잠금(노드가 끝날 때마다 늘림). 서버가 죽으면 이만큼 뒤 '멈춤'
TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Seoul")

# 비용 추정(요금표 기준 어림값, 크게 잡음)
PRICE_STUDIO_PAGE = 0.05            # Parse $0.01 + Extract $0.04 (1쪽)
PRICE_CHAT_IN_PER_M = _float("PRICE_CHAT_IN_PER_M", 1.0)
PRICE_CHAT_OUT_PER_M = _float("PRICE_CHAT_OUT_PER_M", 2.0)
PRICE_EMBED_PER_M = _float("PRICE_EMBED_PER_M", 0.1)
