"""
app/agents/studio.py

Upstage Studio 기록 · 관측 Agent 실행(1차 agent_client.py 를 옮김). 1차 에이전트는 그대로 두고 도구로 감싸 부른다.
Files 업로드 → responses.create(model=agent_id, include=["all"], extra_body={"config_id"}) → 끝날 때까지 조회 → 단계 결과.
보내기 전 llm.guard 의 실명 검사를 반드시 거친다(guard 밖에서 부르면 오류). 캐시는 두지 않는다(원문이 디스크에 남음).
"""

import json
import time

from openai import OpenAI

from app.core import config, llm, logger

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


def _once(agent_id, config_id, html, timeout):
    t0 = time.time()
    up = client().files.create(file=("input.html", html.encode("utf-8"), "text/html"), purpose="user_data")
    r = client().responses.create(model=agent_id, include=["all"],
                                  input=[{"role": "user", "content": [{"type": "input_file", "file_id": up.id}]}],
                                  extra_body={"config_id": str(config_id)})
    while r.status in ("queued", "in_progress"):
        if time.time() - t0 > timeout:
            raise StudioError("studio_timeout", "Studio 응답이 늦어요")
        time.sleep(1.5)
        r = client().responses.retrieve(r.id, include=["all"])
    if r.status != "completed":
        raise StudioError("studio_failed")
    steps = [o.content[0].text for o in r.output if getattr(o, "content", None)]
    if len(steps) < 3:
        raise StudioError("studio_bad_output")
    try:
        parse, data = json.loads(steps[0]), json.loads(steps[-1])
    except json.JSONDecodeError:
        raise StudioError("studio_bad_output")
    pages = max([e.get("page", 1) for e in parse.get("elements", [])] or [1])
    return data, pages


def run(kind, html):
    """kind: 'record' | 'observe'. → 추출 JSON(dict). 실패하면 한 번 다시(limits.retry), 그래도 안 되면 StudioError."""
    m = llm.current()
    if m is None:
        raise RuntimeError("Studio 호출은 llm.guard 안에서만")
    agent_id, config_id = ((config.RECORD_AGENT_ID, config.V8_RECORD_CONFIG_ID) if kind == "record"
                           else (config.OBSERVE_AGENT_ID, config.V8_OBSERVE_CONFIG_ID))
    m.check(html, f"studio_{kind}")
    last = None
    for attempt in (1, 2):
        t0 = time.time()
        try:
            data, pages = _once(agent_id, config_id, html, config.STUDIO_TIMEOUT_S)
        except Exception as e:   # 네트워크 · 실패 상태 · JSON 아님
            last = e
            m.add(config.PRICE_STUDIO_PAGE)   # 실패해도 과금될 수 있어 크게 잡는다
            logger.log("external", what=f"studio_{kind}", ok=False, attempts=attempt,
                       code=getattr(e, "code", type(e).__name__))
            continue
        m.add(pages * config.PRICE_STUDIO_PAGE)
        logger.log("external", what=f"studio_{kind}", ok=True, attempts=attempt, pages=pages,
                   ms=int((time.time() - t0) * 1000))
        return data
    raise last if isinstance(last, StudioError) else StudioError("studio_failed")
