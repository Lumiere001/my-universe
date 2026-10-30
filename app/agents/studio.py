"""
app/agents/studio.py

Upstage Studio 기록 · 관측 Agent 실행(1차 agent_client.py 를 옮김). 1차 에이전트는 그대로 두고 도구로 감싸 부른다.
Files 업로드 → responses.create(model=agent_id, include=["all"], extra_body={"config_id"}) → 끝날 때까지 조회 → 단계 결과.
돌려주는 dict = Extract JSON + "_classify"(Classify 단계가 고른 갈래 글자).
보내기 전 llm.guard 의 실명 검사를 반드시 거친다(guard 밖에서 부르면 오류). 캐시는 두지 않는다(원문이 디스크에 남음).
올린 입력 파일은 실행이 끝나면(성공 · 실패 · 시간 초과 모두) 지운다.
"""

import json
import time

from openai import OpenAI

from app.core import config, llm, logger, trace

_client = None


class StudioError(RuntimeError):
    def __init__(self, code, message="Studio 실행이 실패했어요"):
        super().__init__(message)
        self.code = code


def client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.UPSTAGE_API_KEY, base_url=config.STUDIO_BASE_URL)
    return _client


def _delete_file(fid):
    """올린 입력 파일(가명 일기 HTML)을 지운다. 실패해도 일기 처리는 계속하고 오류 코드만 남긴다."""
    try:
        client().files.delete(fid)
    except Exception as e:
        logger.log("external", what="studio_file_delete", ok=False, code=type(e).__name__,
                   http=getattr(e, "status_code", None))


def _once(agent_id, config_id, html, timeout):
    t0 = time.time()
    up = client().files.create(file=("input.html", html.encode("utf-8"), "text/html"), purpose="user_data")
    try:
        r = client().responses.create(model=agent_id, include=["all"],
                                      input=[{"role": "user", "content": [{"type": "input_file", "file_id": up.id}]}],
                                      extra_body={"config_id": str(config_id)})
        while r.status in ("queued", "in_progress"):
            if time.time() - t0 > timeout:
                raise StudioError("studio_timeout", "Studio 응답이 늦어요")
            time.sleep(1.5)
            r = client().responses.retrieve(r.id, include=["all"])
    finally:
        _delete_file(up.id)
    if r.status != "completed":   # Studio 는 요청 한도 초과를 HTTP 429 가 아니라 실패 상태 + error.code 로 돌려준다(2026-10-30 확인)
        code = getattr(getattr(r, "error", None), "code", None)
        e = StudioError("studio_rate_limited" if code == "rate_limit_exceeded" else "studio_failed")
        e.detail = code or r.status   # Studio 가 준 이유(원문 없는 짧은 코드) — 실패 원인을 기록에서 보려고
        raise e
    steps = [o.content[0].text for o in r.output if getattr(o, "content", None)]
    if len(steps) < 3:
        raise StudioError("studio_bad_output")
    try:
        parse, data = json.loads(steps[0]), json.loads(steps[-1])
    except json.JSONDecodeError:
        raise StudioError("studio_bad_output")
    data["_classify"] = steps[1].strip()   # Classify 갈래(기록: 글 유형 4갈래, 관측: 관측 상태). 단계 순서 = Parse · Classify · Extract
    pages = max([e.get("page", 1) for e in parse.get("elements", [])] or [1])
    return data, pages


def run(kind, html):
    """kind: 'record' | 'observe'. → 추출 JSON(dict). 실패하면 한 번 다시(limits.retry), 그래도 안 되면 StudioError."""
    m = llm.current()
    if m is None:
        raise RuntimeError("Studio 호출은 llm.guard 안에서만")
    agent_id, config_id = ((config.RECORD_AGENT_ID, config.V8_RECORD_CONFIG_ID) if kind == "record"
                           else (config.OBSERVE_AGENT_ID, config.V8_OBSERVE_CONFIG_ID))
    with trace.span("studio.run", kind="AGENT", system="upstage", op="invoke_agent", agent=kind, config_id=str(config_id)):
        m.check(html, f"studio_{kind}")
        last, usd0, tries = None, m.usd, 0
        for attempt in (1, 2, 3):   # 보통은 두 번, 요청 한도 초과면 쉬었다가 세 번까지
            tries = attempt
            t0 = time.time()
            try:
                data, pages = _once(agent_id, config_id, html, config.STUDIO_TIMEOUT_S)
            except Exception as e:   # 네트워크 · 실패 상태 · JSON 아님
                last = e
                m.add(config.PRICE_STUDIO_PAGE)   # 실패해도 과금될 수 있어 크게 잡는다
                logger.log("external", what=f"studio_{kind}", ok=False, attempts=attempt,
                           code=getattr(e, "code", type(e).__name__), detail=getattr(e, "detail", None))
                limited = getattr(e, "status_code", None) == 429 or getattr(e, "code", None) == "studio_rate_limited"
                if attempt == 3 or (attempt == 2 and not limited):
                    break
                if limited:   # 너무 잦은 요청이면 쉬고 다시(업스테이지 가이드 3.1). 여러 사람이 동시에 쓸 때(파일럿) 실패하지 않게 점점 길게
                    time.sleep(config.STUDIO_RETRY_WAIT_S * (4 if getattr(e, "code", None) == "studio_rate_limited" else 1) * attempt)
                continue
            m.add(pages * config.PRICE_STUDIO_PAGE)
            logger.log("external", what=f"studio_{kind}", ok=True, attempts=attempt, pages=pages,
                       ms=int((time.time() - t0) * 1000))
            trace.set(attempts=attempt, pages=pages, est_usd=m.usd - usd0)
            return data
        trace.set(attempts=tries, est_usd=m.usd - usd0)
        raise last if isinstance(last, StudioError) else StudioError("studio_failed")
