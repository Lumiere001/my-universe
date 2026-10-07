"""
app/core/config.py

설정은 환경변수(.env)에서만 읽는다. 키 값은 화면 · 로그에 내보내지 않는다.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

# Upstage (Solar Chat · Embedding · Studio)
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY", "")
UPSTAGE_BASE_URL = os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1")
CHAT_MODEL = os.getenv("SOLAR_CHAT_MODEL", "solar-pro2")
EMBED_PASSAGE_MODEL = os.getenv("EMBEDDING_MODEL", "solar-embedding-2-passage")
EMBED_QUERY_MODEL = os.getenv("EMBEDDING_QUERY_MODEL", EMBED_PASSAGE_MODEL.replace("-passage", "-query"))

# Studio 기록 · 관측 Agent (1차 에이전트를 그대로 도구로 감싸 부른다)
RECORD_AGENT_ID = os.getenv("RECORD_AGENT_ID", "")
RECORD_CONFIG_ID = os.getenv("RECORD_CONFIG_ID", "1")
OBSERVE_AGENT_ID = os.getenv("OBSERVE_AGENT_ID", "")
OBSERVE_CONFIG_ID = os.getenv("OBSERVE_CONFIG_ID", "1")
