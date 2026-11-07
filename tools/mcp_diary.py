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
import hashlib
import logging
import os
import queue
import re
import threading
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field

API = os.environ.get("MY_UNIVERSE_API", "http://localhost:8001").rstrip("/")
TZ = ZoneInfo("Asia/Seoul")
IMPORTED, WRITTEN = "지난 글 묶음", "텍스트"   # app/models SOURCES
MAX_BATCH = 50          # 한 번에 받는 편수(정리는 한 편 1분쯤 · $0.15쯤 — app/service/importer 어림값)
MAX_TEXT = 8000         # 백엔드 MAX_TEXT_CHARS 기본값(넘으면 서버도 422)
MAX_TITLE = 120         # 백엔드 MAX_TITLE_CHARS 기본값
ENTRY_TIMEOUT_S = 600   # 한 편 정리를 기다리는 시간. 넘겨도 서버는 끝까지 정리한다(recent_diaries 로 보임)
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

_jobs = queue.Queue()   # 보낼 글(POST /diary 본문). 일꾼 하나가 차례로
_problems = []          # 보내지 못한 글(토큰 만료 · 한도 …) — recent_diaries 가 보여 줌


class Diary(BaseModel):
    text: str = Field(description="일기 본문. 사용자가 쓴 그대로(고치거나 요약하지 않음), 8,000자까지")
    date: str | None = Field(None, description="글이 다루는 날 YYYY-MM-DD. 모르면 비움(서버가 제목 · 본문 속 날짜를 읽음)")
    title: str = Field("", description="제목. 없으면 비움")


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


def _body(i, e: Diary, source):
    """한 편 → POST /diary 본문. 틀리면 몇 번째 글이 왜 틀렸는지 ValueError."""
    text, title = e.text.strip(), " ".join(e.title.split())
    if not text:
        raise ValueError(f"{i}번 글: 본문이 비어 있어요.")
    if len(text) > MAX_TEXT:
        raise ValueError(f"{i}번 글: {MAX_TEXT:,}자까지 넣을 수 있어요(지금 {len(text):,}자). 나눠서 넣어 주세요.")
    if len(title) > MAX_TITLE:
        raise ValueError(f"{i}번 글: 제목은 {MAX_TITLE}자까지예요.")
    body = {"text": text, "title": title, "source": source}
    if e.date:
        try:
            day = date.fromisoformat(e.date) if DAY.fullmatch(e.date) else None
        except ValueError:
            day = None
        if not day:
            raise ValueError(f"{i}번 글: 날짜는 YYYY-MM-DD 로 적어 주세요(받은 값 {e.date!r}).")
        now = datetime.now(TZ)
        if day > now.date():
            raise ValueError(f"{i}번 글: 앞으로의 날짜({e.date})예요.")
        # 앱 가져오기와 같게: 그날 낮 12시에 쓴 글로(오늘이면 지금까지), 글이 다루는 날은 그대로 확실
        body |= {"day": e.date, "written_at": min(datetime(day.year, day.month, day.day, 12, tzinfo=TZ), now).isoformat()}
    if source == IMPORTED:   # 같은 원본 표시: 다시 넣어도 서버가 같은 글로 알아봄(앱의 '파일:' 표시와 같은 방식)
        body["source_ref"] = "mcp:" + hashlib.sha256(f"{e.date}\n{title}\n{text}".encode()).hexdigest()[:32]
    return body


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
    return {"accepted": len(bodies), "waiting": waiting, "est_minutes": waiting,
            "note": "정리는 한 편에 1분쯤, 오래된 글부터 차례로 해요. recent_diaries 로 상태(done = 끝)를 볼 수 있어요."}


def import_diaries(entries: list[Diary]) -> dict:
    """다른 곳(노션 · 메모 앱 · 파일 …)에 있던 지난 일기 여러 편을 나의 우주로 가져온다(한 번에 50편까지).
    본문은 사용자가 쓴 그대로 넘긴다. 한 편마다 AI 정리(유료, 1분쯤)가 돌아서 몇 편을 넣을지 사용자에게 먼저 확인한다.
    날짜 순서와 관계없이 넣어도 오래된 글부터 정리한다. 이미 넣은 글은 다시 정리하지 않는다. 바로 돌려주고 정리는 뒤에서 한다."""
    if not entries:
        raise ValueError("가져올 글이 없어요.")
    if len(entries) > MAX_BATCH:
        raise ValueError(f"한 번에 {MAX_BATCH}편까지 넣을 수 있어요(받은 글 {len(entries)}편). 나눠서 넣어 주세요.")
    bodies = [_body(i, e, IMPORTED) for i, e in enumerate(entries, 1)]   # 하나라도 틀리면 아무것도 보내지 않음
    _ready()
    return _queue(sorted(bodies, key=lambda b: b.get("day") or "9999"))   # 날짜 없는 글은 뒤로(받은 순서 그대로)


def write_diary(text: str, date: str | None = None, title: str = "") -> dict:
    """오늘(또는 date 날)의 일기 한 편을 나의 우주에 쓴다. 본문은 사용자가 쓴 그대로 넘긴다.
    AI 정리(유료, 1분쯤)는 뒤에서 하고 바로 돌려준다."""
    b = _body(1, Diary(text=text, date=date, title=title), WRITTEN)
    _ready()
    return _queue([b])


def recent_diaries(n: int = 10) -> dict:
    """최근 기록 n편(1~100)의 날짜 · 제목 · 정리 상태(done 끝 · processing 정리 중 · failed 멈춤)만 본다. 본문은 돌려주지 않는다.
    넣기 전에 이미 있는 글인지 확인할 때, 넣은 뒤 정리가 끝났는지 볼 때 쓴다. waiting = 아직 정리 차례를 기다리는 편수."""
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

    server = MCPServer("나의 우주", instructions="사용자의 일기를 나의 우주(일기 앱)로 넘기는 도구. 본문은 고치지 말고 그대로, "
                       "여러 편이면 먼저 recent_diaries 로 이미 있는지 보고, 몇 편을 넣을지 사용자에게 확인한 뒤 import_diaries 로.")
    for f in (import_diaries, write_diary, recent_diaries):
        server.tool()(tool(f))
    logging.getLogger("httpx").setLevel(logging.WARNING)   # 요청마다 남는 줄(주소만)로 AI 비서 기록을 채우지 않게
    server.run()   # stdio


if __name__ == "__main__":
    main()
