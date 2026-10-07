"""
app/core/llm.py

LLM 클라이언트: Solar Chat과 Solar Embedding (Upstage, OpenAI 호환 API).
여기로 들어오는 글은 이미 가명 처리된 글이어야 한다(실명 금지, app/service/safety).
"""

from openai import OpenAI

from app.core import config

_client = None


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.UPSTAGE_API_KEY, base_url=config.UPSTAGE_BASE_URL)
    return _client


def chat(messages, model=None, **kw):
    """messages: [{"role": ..., "content": ...}] → 답 글."""
    r = client().chat.completions.create(model=model or config.CHAT_MODEL, messages=messages, **kw)
    return r.choices[0].message.content or ""


def embed(texts, query=False):
    """글 목록 → 벡터 목록. 검색어면 query=True."""
    model = config.EMBED_QUERY_MODEL if query else config.EMBED_PASSAGE_MODEL
    texts = [t if t.strip() else "(빈 글)" for t in texts]
    out = []
    for i in range(0, len(texts), 100):  # 한 번에 100개까지
        r = client().embeddings.create(model=model, input=texts[i:i + 100])
        out += [d.embedding for d in r.data]
    return out
