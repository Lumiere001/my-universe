"""
app/core/llm.py

LLM 클라이언트: Solar Chat과 Solar Embedding (Upstage, OpenAI 호환 API).
여기로 들어오는 글은 이미 가명 처리된 글이어야 한다(실명 금지, app/service/safety).

백엔드는 외부 호출을 `with guard(people):` 안에서만 한다. guard 안에서는 보내기 바로 전에
assert_no_real_names 로 사용자 입력 부분을 검사하고(실명이면 RealNameLeak, 보내지 않음), 호출 수 · 추정 비용을 센다.
guard 밖(도구 · 평가 스크립트의 가상 인물 데이터)은 검사 없이 그대로 보낸다.
"""

import contextvars
import re
from contextlib import contextmanager

from openai import OpenAI

from app.core import config, logger, trace
from app.service.safety.pseudonym import _strings, assert_no_real_names

_client = None
# 코드가 쓴 고정 라벨(Studio 입력 머리말 '기존 작은 별' · 판정 라벨 '[별지기 한마디]'). 한 글자 이름(별)이 여기에 걸리는
# 오탐을 막으려고 검사 전에 뺀다. 사용자 글은 mask 가 그 이름을 이미 모두 가명으로 바꿨으니 남은 라벨 속 글자는 코드가 쓴 것이다.
FIXED = re.compile(r"별지기|작은 별")
_guard = contextvars.ContextVar("llm_guard", default=None)


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.UPSTAGE_API_KEY, base_url=config.UPSTAGE_BASE_URL)
    return _client


class Meter:
    """한 단계에서 나간 외부 호출 수 · 추정 비용 · 실명 검사 수."""

    def __init__(self, people):
        self.people, self.calls, self.usd, self.checked = people, 0, 0.0, 0

    def check(self, payload, what):
        """보내기 직전 검사. 실명이 있으면 RealNameLeak(기록에는 이름 없이 남김)."""
        try:
            assert_no_real_names([FIXED.sub("·", x) for x in _strings(payload)], self.people)
        except Exception:
            logger.log("guard", what=what, ok=False, code="real_name_leak")
            raise
        self.checked += 1
        logger.log("guard", what=what, ok=True)

    def add(self, usd):
        self.calls += 1
        self.usd += usd


@contextmanager
def guard(people):
    m = Meter(people)
    token = _guard.set(m)
    try:
        yield m
    finally:
        _guard.reset(token)


def current():
    return _guard.get()


def chat(messages, model=None, **kw):
    """messages: [{"role": ..., "content": ...}] → 답 글."""
    model = model or config.CHAT_MODEL
    with trace.span("solar.chat", kind="LLM", system="upstage", op="chat", model=model):   # 프롬프트 · 답은 넣지 않음
        m = _guard.get()
        if m:   # 시스템 프롬프트는 코드가 쓴 v8.json 규칙 글이라 사용자 · 도구 입력(user · assistant · tool)만 본다
            m.check([x["content"] for x in messages if x.get("role") != "system"], "solar_chat")
        r = client().chat.completions.create(model=model, messages=messages, **kw)
        u = getattr(r, "usage", None)
        tin, tout = (getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0) if u else (0, 0)
        usd = (tin * config.PRICE_CHAT_IN_PER_M + tout * config.PRICE_CHAT_OUT_PER_M) / 1e6
        trace.set(tokens_in=tin, tokens_out=tout, est_usd=usd)
        if m:
            m.add(usd)
            logger.log("external", what="solar_chat", tokens_in=tin, tokens_out=tout)
        return r.choices[0].message.content or ""


def embed(texts, query=False):
    """글 목록 → 벡터 목록. 검색어면 query=True."""
    model = config.EMBED_QUERY_MODEL if query else config.EMBED_PASSAGE_MODEL
    texts = [t if t.strip() else "(빈 글)" for t in texts]
    with trace.span("embed", kind="EMBEDDING", system="upstage", op="embeddings", model=model, texts=len(texts)):
        m = _guard.get()
        if m:
            m.check(texts, "solar_embed")
        out, tokens = [], 0
        for i in range(0, len(texts), 100):  # 한 번에 100개까지
            r = client().embeddings.create(model=model, input=texts[i:i + 100])
            out += [d.embedding for d in r.data]
            n = getattr(getattr(r, "usage", None), "total_tokens", 0) or 0
            tokens += n
            if m:
                m.add(n * config.PRICE_EMBED_PER_M / 1e6)
        trace.set(tokens_in=tokens, est_usd=tokens * config.PRICE_EMBED_PER_M / 1e6)
        return out
