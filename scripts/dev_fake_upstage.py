"""
로컬 화면 확인용 백엔드(유료 호출 0): 로컬 Supabase · ChromaDB 는 그대로 쓰고, Upstage(Studio · Solar)만
tests 의 FakeUpstage 로 바꿔 띄운다. 정리 결과(생각 · 관계 · 한마디)는 가짜라 실제와 다르다 — 화면 흐름 · 캡처용.

    scripts/dev_up.sh                                                       # 먼저(로컬 Supabase · ChromaDB · 계정 · 하늘 데모)
    FRONTEND_ORIGIN=http://localhost:3013 uv run --frozen python scripts/dev_fake_upstage.py 8013

운영 자원에 닿지 않게: DATABASE_URL 이 로컬(127.0.0.1 · localhost)이 아니거나 Chroma Cloud 키가 있으면 띄우지 않는다.
"""

import functools
import sys
import types
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from app.agents import studio  # noqa: E402
from app.core import config, llm  # noqa: E402
from tests.test_graph_flow import FakeUpstage  # noqa: E402

if urlparse(config.DATABASE_URL).hostname not in ("127.0.0.1", "localhost") or config.CHROMA_API_KEY:
    sys.exit("로컬 DB · 로컬 Chroma 에서만 띄워요(.env.local 확인).")

fake = FakeUpstage()
_embed = fake.embeddings.create


@functools.cache
def dim():
    from app.repository.vectors import ChromaVectors
    got = ChromaVectors().col.get(limit=1, include=["embeddings"])["embeddings"]
    return len(got[0]) if len(got) else 1024


def embed(model, input):
    """가짜 벡터(8칸)를 로컬 Chroma 모음의 벡터 크기에 맞춰 늘린다(하늘 데모 벡터와 같은 모음)."""
    out = _embed(model, input)
    for d in out.data:
        d.embedding = (d.embedding * (dim() // len(d.embedding) + 1))[:dim()]
    return out


fake.embeddings = types.SimpleNamespace(create=embed)
config.RECORD_AGENT_ID, config.OBSERVE_AGENT_ID = "rec-agent", "obs-agent"
studio._client = fake
llm._client = types.SimpleNamespace(chat=fake.chat, embeddings=fake.embeddings)

import main  # noqa: E402

uvicorn.run(main.app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8013)
