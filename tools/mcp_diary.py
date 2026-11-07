# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=2,<3", "httpx>=0.27"]
# ///
"""
tools/mcp_diary.py — 나의 우주 MCP 서버(시험판, 2026-11-07).

사용자의 AI 비서(Claude Desktop · Claude Code …)가 이미 가진 연결(노션 · 메모 앱 · 파일)로 읽은 일기를 나의 우주로 넘기는 얇은 다리.
새 처리 길은 없다: 앱 '지난 일기 가져오기'와 같은 HTTP API 를 그대로 부른다(POST /diary, source='지난 글 묶음' · source_ref).
- import_diaries: 여러 편(한 번에 50편까지)을 받아 오래된 것부터 한 편씩 정리(앱 가져오기와 같은 순서).
- write_diary: 한 편(source='텍스트', 앱 쓰기 화면과 같음).
- recent_diaries: 최근 기록의 날짜 · 제목 · 정리 상태만(본문 · 요약은 돌려주지 않음).
정리는 한 편에 1분쯤 걸려서, 도구는 받기만 하고 바로 돌려준다(AI 비서가 오래 기다리다 끊지 않게). 정리는 이 프로세스의
일꾼 하나가 차례로 한다. 같은 글을 다시 보내도 서버가 알아보고 다시 정리하지 않는다(같은 원본 · 같은 날 같은 글).

    MY_UNIVERSE_TOKEN=<액세스 토큰> uv run tools/mcp_diary.py     # stdio. 설정 예는 docs/mcp.md
환경변수: MY_UNIVERSE_API(기본 http://localhost:8001), MY_UNIVERSE_TOKEN(로그인 액세스 토큰 — 출력 · 로그에 남기지 않는다).
"""

import functools
import logging
import os
import queue
import sys
import threading
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # 저장소 루트: 입력 검사는 원격 판과 같은 파일
from app.service.mcp_input import DOCS, IMPORTED, INSTRUCTIONS, MAX_BATCH, MAX_TEXT, NOTE, WRITTEN, Diary, batch  # noqa: E402,F401
from app.service.mcp_input import body as _body  # noqa: E402

API = os.environ.get("MY_UNIVERSE_API", "http://localhost:8001").rstrip("/")
ENTRY_TIMEOUT_S = 600   # 한 편 정리를 기다리는 시간. 넘겨도 서버는 끝까지 정리한다(recent_diaries 로 보임)

_jobs = queue.Queue()   # 보낼 글(POST /diary 본문). 일꾼 하나가 차례로
_problems = []          # 보내지 못한 글(토큰 만료 · 한도 …) — recent_diaries 가 보여 줌


def _api(method, path, timeout=30, **kw):
    """나의 우주 API 한 번. 오류면 서버의 한국어 안내로 RuntimeError(토큰은 어디에도 남기지 않음)."""
    token = os.environ.get("MY_UNIVERSE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("MY_UNIVERSE_TOKEN 이 비어 있어요. docs/mcp.md 의 '토큰 얻기'를 봐 주세요.")
    try:
        r = httpx.request(method, API + path, headers={"Authorization": f"Bearer {token}"}, timeout=timeout, **kw)
    except httpx.TimeoutException:
        raise RuntimeError("응답이 늦어 기다리지 않았어요. 서버는 정리를 이어 가니 조금 뒤 recent_diaries 로 확인해 주세요.")
    except httpx.HTTPError as e:
        raise RuntimeError(f"나의 우주 서버({API})에 닿지 못했어요: {type(e).__name__}")
    if r.status_code >= 400:
        try:
            msg = r.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            msg = f"서버 응답 {r.status_code}"
        raise RuntimeError(msg)
    return r.json() if r.content else None


def _label(b):
    return f"{b.get('day') or '날짜 없음'} {b['title'] or b['text'][:15] + '…'}"


def _worker():
    while True:
        b = _jobs.get()
        try:
            _api("POST", "/diary", json=b, timeout=ENTRY_TIMEOUT_S)   # 정리(기록 · 관측 Agent)가 끝날 때까지 기다림
        except Exception as e:   # noqa: BLE001 — 한 편이 어떻게 실패하든 일꾼은 살아 다음 글로
            _problems.append(f"{_label(b)}: {e}")
        finally:
            _jobs.task_done()


def _ready():
    """토큰 · 동의를 먼저 본다(값싼 GET 하나). 여기서 막히면 아무것도 받지 않는다."""
    if _api("GET", "/consent")["needed"]:
        raise RuntimeError("나의 우주 앱에서 이용 동의를 먼저 해 주세요(처음 로그인할 때 나오는 화면).")


def _queue(bodies):
    if _sender.ident is None:   # 처음 받을 때 일꾼을 띄운다(백엔드 app/api/mcp_link.py 가 검사만 빌려 쓸 때는 안 띄움)
        _sender.start()
    for b in bodies:
        _jobs.put(b)
    waiting = _jobs.unfinished_tasks
    return {"accepted": len(bodies), "waiting": waiting, "est_minutes": waiting, "note": NOTE}


def import_diaries(entries: list[Diary]) -> dict:
    bodies = batch(entries)
    _ready()
    return _queue(bodies)


def write_diary(text: str, date: str | None = None, title: str = "") -> dict:
    b = _body(1, Diary(text=text, date=date, title=title), WRITTEN)
    _ready()
    return _queue([b])


def recent_diaries(n: int = 10) -> dict:
    got = _api("GET", "/diary", params={"limit": max(1, min(int(n), 100))})["entries"]
    return {"diaries": [{"date": e["day"], "title": e["title"], "status": e["status"], "source": e["source"]} for e in got],
            "waiting": _jobs.unfinished_tasks, "problems": _problems[-10:]}


_sender = threading.Thread(target=_worker, name="diary-sender", daemon=True)


def main():
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError

    def tool(f):   # 우리 안내(ValueError · RuntimeError)만 AI 비서에게 보인다. 그 밖의 오류는 SDK 가 'Error executing tool' 로 가림
        @functools.wraps(f)
        def run(*a, **kw):
            try:
                return f(*a, **kw)
            except (ValueError, RuntimeError) as e:
                raise ToolError(str(e)) from None
        return run

    server = MCPServer("나의 우주", instructions=INSTRUCTIONS)
    for f in (import_diaries, write_diary, recent_diaries):
        server.tool(description=DOCS[f.__name__])(tool(f))
    logging.getLogger("httpx").setLevel(logging.WARNING)   # 요청마다 남는 줄(주소만)로 AI 비서 기록을 채우지 않게
    server.run()   # stdio


if __name__ == "__main__":
    main()
