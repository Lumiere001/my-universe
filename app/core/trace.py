"""
app/core/trace.py

OpenTelemetry 추적: 요청 하나가 어떤 단계 · 외부 호출을 거쳤는지(span 나무). docs/trace.md
OTEL_EXPORTER_OTLP_ENDPOINT 가 있을 때만 켠다(예: 로컬 Phoenix http://localhost:6006). 없으면 아무것도 하지 않는다(운영 기본).

원문 · 인용 · 이름 · 프롬프트 · 모델 답은 span 에 넣지 않는다. 속성은 ALLOWED 에 있는 이름만 받고(나머지는 버림),
값은 숫자 · 참거짓 · 이름꼴 글자(영문 · 숫자 · _.:/- 만 64자까지 = id · 코드 · 모델 이름)만 받는다 — 한글 · 빈칸이 든 글은
허용한 이름이어도 버린다. 예외도 메시지 · 스택 없이 종류와 오류 코드만.
"""

import re
from contextlib import contextmanager

from opentelemetry import trace as otel
from opentelemetry.trace import Status, StatusCode

from app.core import config

# 넘기는 이름 → 내보내는 속성 이름(GenAI 시맨틱 규약이 있는 것은 그 이름). 여기 없는 이름은 버린다.
ALLOWED = {
    "kind": "openinference.span.kind",       # Phoenix 그림 구분: AGENT · CHAIN · LLM · EMBEDDING · TOOL
    "system": "gen_ai.system",               # upstage · elevenlabs
    "op": "gen_ai.operation.name",           # chat · embeddings · invoke_agent
    "agent": "gen_ai.agent.name",            # Studio 기록 · 관측 Agent(record · observe)
    "model": "gen_ai.request.model",
    "tokens_in": "gen_ai.usage.input_tokens",
    "tokens_out": "gen_ai.usage.output_tokens",
    "error_type": "error.type",              # 예외 종류 이름(메시지는 남기지 않음)
    "http_status": "http.response.status_code",
    "error_code": "app.error_code",          # runs.error_code 와 같은 코드
    "entry_id": "app.entry_id",              # 기록 id(무작위, 사용자 id 는 넣지 않음)
    "conversation_id": "app.conversation_id",
    "turn": "app.turn",
    "status": "app.status",                  # done · confirm · failed
    "skipped": "app.step.skipped",           # 이어 하기에서 이미 끝난 단계
    "calls": "app.step.calls",               # 그 단계의 외부 호출 수
    "checks": "app.step.checks",             # 한마디 · 답 검사 문제 개수
    "est_usd": "app.est_usd",                # 추정 비용(달러)
    "config_id": "app.studio.config_id",
    "attempts": "app.studio.attempts",
    "pages": "app.pages",
    "texts": "app.embed.texts",              # 벡터로 만든 글 수
    "seconds": "app.audio.seconds",
    "bytes": "app.audio.bytes",
    "format": "app.audio.format",
    "chars": "app.tts.chars",                # 읽어 준 글자 수
    "profile": "app.ontology.profile",       # 온톨로지 모드(v8 · two) — 점수가 바뀌면 어느 판이었는지(강의 10강 버전 ID)
    "stars_new": "app.ontology.stars_new",   # 이 글에서 새로 생긴 작은 별 수
    "stars_joined": "app.ontology.stars_joined",   # 새 이름이었지만 기존 작은 별에 붙인 수(STAR_JOIN_SIM)
    "other_sun": "app.ontology.other_sun",   # 두 영역 밖('그 밖')으로 간 생각 수
}
NAME_LIKE = re.compile(r"[\w.:/-]{1,64}", re.ASCII)
_tracer = None


def clean(attrs):
    """허용한 이름 · 숫자 · 이름꼴 값만 남겨 내보내는 이름으로 바꾼다."""
    out = {}
    for k, v in attrs.items():
        if k in ALLOWED and (isinstance(v, (bool, int, float)) or isinstance(v, str) and NAME_LIKE.fullmatch(v)):
            out[ALLOWED[k]] = round(v, 6) if isinstance(v, float) else v
    return out


def setup(exporter=None):
    """exporter 가 없으면 OTLP/HTTP(OTEL_EXPORTER_OTLP_ENDPOINT, 묶어 보냄). 시험은 메모리 exporter 를 넘긴다(바로 보냄)."""
    global _tracer
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

    if exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        proc = BatchSpanProcessor(OTLPSpanExporter())
    else:
        proc = SimpleSpanProcessor(exporter)
    provider = TracerProvider(resource=Resource.create({"service.name": config.OTEL_SERVICE_NAME}))
    provider.add_span_processor(proc)
    _tracer = provider.get_tracer("my-universe")
    return provider


def _mark(sp, attrs):
    sp.set_attributes(clean(attrs))
    if attrs.get("error_code") or attrs.get("error_type"):
        sp.set_status(Status(StatusCode.ERROR))


def set(**attrs):   # noqa: A001 (trace.set 으로 부름)
    """지금 span 에 속성을 더한다(끝난 뒤 알게 되는 토큰 · 비용 · 오류 코드). error_code 가 있으면 오류로 표시."""
    if _tracer:
        _mark(otel.get_current_span(), attrs)


@contextmanager
def span(name, **attrs):
    """with trace.span("solar.chat", kind="LLM", model=m): … — 꺼져 있으면 그냥 지나간다."""
    if _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(name, record_exception=False, set_status_on_exception=False) as sp:
        _mark(sp, attrs)
        try:
            yield
        except Exception as e:   # 종류 · 코드만(StudioError · OcrError · SpeechError 의 code). 메시지 · 스택은 남기지 않는다
            _mark(sp, {"error_type": type(e).__name__, "error_code": getattr(e, "code", None)})
            raise


def start(name, **attrs):
    """yield 를 건너는 span(스트리밍 응답 안): with trace.use(sp) 로 안쪽을 묶고 끝나면 sp.end()."""
    if _tracer is None:
        return otel.INVALID_SPAN
    sp = _tracer.start_span(name)
    _mark(sp, attrs)
    return sp


def use(sp):
    return otel.use_span(sp, record_exception=False, set_status_on_exception=False)


if config.OTEL_ENDPOINT:
    setup()
