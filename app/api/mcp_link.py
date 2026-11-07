"""
app/api/mcp_link.py — AI 비서에 연결(원격 MCP, 시험판 2026-11-07).

설정 '앱 → AI 비서에 연결'에서 연결 주소를 만들면 그 사람 전용 열쇠가 든 주소(/mcp/<열쇠>)를 한 번 보여 준다. Claude 앱의
'커스텀 커넥터 추가'에 주소만 붙이면, AI 비서가 노션 · 메모 · 파일에서 읽은 일기를 이 주소의 도구로 넘긴다(토큰 복사 없음).
열쇠 = 사용자 id · 열쇠 id · 만료를 사용자별 HMAC(security.digest)으로 서명한 것. 저장하는 건 지금 열쇠 id · 만료뿐(설정, 암호화).
30일 뒤 만료, '연결 끊기'나 새 주소를 만들면 예전 주소는 바로 안 된다. 이 열쇠로는 아래 도구 셋만 쓸 수 있다(다른 API 는 안 열림).
MCP 는 Streamable HTTP 의 상태 없는 JSON 응답만 한다(initialize · tools/list · tools/call · ping) — 의존성 추가 없음.
도구 이름 · 설명 · 입력 검사는 로컬 stdio 판(tools/mcp_diary.py)과 같다. 정리는 앱 가져오기처럼 오래된 글부터 한 편씩, 응답과 따로 도는 스레드에서.
"""

import hmac
import json
import secrets
import threading
import time
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Depends, Path, Response
from pydantic import ValidationError

from app.api import consent
from app.api import diary as diary_api
from app.core import logger, security
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import DiaryIn
from app.repository import diary, views
from tools import mcp_diary as stdio

router = APIRouter(tags=["AI 비서 연결"])
DAYS = 30
VERSION = "2025-06-18"   # 클라이언트가 다른 판을 말하면 그 판으로 답한다(도구만 쓰니 판마다 같음)
_waiting = Counter()     # 사용자별 아직 정리 차례를 기다리는 편수. ponytail: 프로세스 안에만 — 운영(Vercel)은 DB 큐로


def _sign(uid, kid, exp):
    return security.digest(uid, f"mcp\n{kid}\n{exp}")[:32]


def _link(s):
    return diary.profile(s)[0].get("mcp_link")


@router.get("/mcp/link", summary="AI 비서 연결 상태(주소는 만들 때 한 번만 보여 줌)")
def get_link(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        link = _link(s)
    live = bool(link) and link["exp"] > time.time()
    return {"connected": live, "expires_at": datetime.fromtimestamp(link["exp"], diary.TZ).isoformat() if live else None}


@router.post("/mcp/link", summary="새 연결 주소의 열쇠(예전 주소는 바로 끊김)")
def make_link(user=Depends(get_user), repo=Depends(get_repo)):
    uid, kid = user["id"], secrets.token_hex(6)
    exp = int(time.time() + timedelta(days=DAYS).total_seconds())
    with repo.session(uid) as s:
        diary.save_profile(s, settings={"mcp_link": {"kid": kid, "exp": exp}})
    return {"key": f"{uid}.{kid}.{exp}.{_sign(uid, kid, exp)}", "expires_at": datetime.fromtimestamp(exp, diary.TZ).isoformat()}


@router.delete("/mcp/link", status_code=204, summary="연결 끊기")
def cut_link(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        diary.save_profile(s, settings={"mcp_link": None})
    return Response(status_code=204)


def _owner(repo, key):
    """열쇠 → 사용자 id. 서명이 틀리거나 만료 · 끊긴 열쇠면 ApiError(401)."""
    parts = key.split(".")
    if len(parts) != 4 or not parts[2].isdigit() or not hmac.compare_digest(parts[3], _sign(*parts[:3])):
        raise ApiError(401, "mcp_key_invalid", "연결 주소가 맞지 않아요. 나의 우주 설정에서 새 주소를 만들어 주세요.")
    uid, kid, exp = parts[0], parts[1], int(parts[2])
    with repo.session(uid) as s:
        link = _link(s)
    if exp < time.time() or not link or link["kid"] != kid:
        raise ApiError(401, "mcp_key_expired", "연결이 끝났어요(만료 · 연결 끊기). 나의 우주 설정에서 새 주소를 만들어 주세요.")
    return uid


def _send(repo, uid, bodies):
    """오래된 글부터 한 편씩: 기록 만들기(동의 · 한도 · 같은 글 확인은 /diary 와 같음) → 정리가 끝날 때까지 기다림 → 다음 글."""
    def work():
        for b in bodies:
            try:
                eid, dup = diary_api._create(repo, uid, DiaryIn(**b))
                if not dup:
                    q = diary_api._start(repo, uid, eid, "mcp.import")
                    while q.get() is not None:
                        pass
            except Exception as e:   # noqa: BLE001 — 한 편이 어떻게 실패하든 다음 글로(멈춘 글은 앱에서 '이어서 하기')
                logger.log("error", step="mcp_import", code=getattr(e, "code", type(e).__name__))
            finally:
                _waiting[uid] -= 1
    _waiting[uid] += len(bodies)
    threading.Thread(target=work, name=f"mcp-{uid[:8]}", daemon=True).start()
    return {"accepted": len(bodies), "waiting": _waiting[uid], "est_minutes": _waiting[uid],
            "note": "정리는 한 편에 1분쯤, 오래된 글부터 차례로 해요. recent_diaries 로 상태(done = 끝)를 볼 수 있어요."}


def _ready(repo, uid):
    with repo.session(uid) as s:
        if consent.needed(s):
            raise ValueError("나의 우주 앱에서 이용 동의를 먼저 해 주세요(처음 로그인할 때 나오는 화면).")


def _import(repo, uid, a):
    entries = a.get("entries") or []
    if not entries:
        raise ValueError("가져올 글이 없어요.")
    if len(entries) > stdio.MAX_BATCH:
        raise ValueError(f"한 번에 {stdio.MAX_BATCH}편까지 넣을 수 있어요(받은 글 {len(entries)}편). 나눠서 넣어 주세요.")
    bodies = [stdio._body(i, stdio.Diary(**e), stdio.IMPORTED) for i, e in enumerate(entries, 1)]
    _ready(repo, uid)
    return _send(repo, uid, sorted(bodies, key=lambda b: b.get("day") or "9999"))


def _write(repo, uid, a):
    b = stdio._body(1, stdio.Diary(**a), stdio.WRITTEN)
    _ready(repo, uid)
    return _send(repo, uid, [b])


def _recent(repo, uid, a):
    with repo.session(uid) as s:
        got = views.entry_list(s, max(1, min(int(a.get("n") or 10), 100)))
    return {"diaries": [{"date": e["day"], "title": e["title"], "status": e["status"], "source": e["source"]} for e in got],
            "waiting": _waiting[uid]}


ITEM = stdio.Diary.model_json_schema()
TOOLS = {
    "import_diaries": (_import, stdio.import_diaries.__doc__, {
        "type": "object", "required": ["entries"],
        "properties": {"entries": {"type": "array", "maxItems": stdio.MAX_BATCH, "items": ITEM}}}),
    "write_diary": (_write, stdio.write_diary.__doc__, ITEM),
    "recent_diaries": (_recent, stdio.recent_diaries.__doc__, {
        "type": "object", "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}}}),
}
INSTRUCTIONS = ("사용자의 일기를 나의 우주(일기 앱)로 넘기는 도구. 본문은 고치지 말고 그대로, 여러 편이면 먼저 recent_diaries 로 "
                "이미 있는지 보고, 몇 편을 넣을지 사용자에게 확인한 뒤 import_diaries 로.")


def _answer(repo, uid, method, params):
    if method == "initialize":
        return {"protocolVersion": params.get("protocolVersion") or VERSION, "capabilities": {"tools": {}},
                "serverInfo": {"name": "나의 우주", "version": "0.1"}, "instructions": INSTRUCTIONS}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [{"name": n, "description": " ".join(d.split()), "inputSchema": sch} for n, (_, d, sch) in TOOLS.items()]}
    if method == "tools/call":
        name = params.get("name")
        if name not in TOOLS:
            raise LookupError(f"없는 도구예요: {name}")
        try:
            out = TOOLS[name][0](repo, uid, params.get("arguments") or {})
        except (ValueError, ValidationError, ApiError) as e:   # 입력 · 동의 · 한도: AI 비서가 읽고 사용자에게 전할 안내
            msg = e.message if isinstance(e, ApiError) else str(e)
            return {"content": [{"type": "text", "text": msg}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}], "structuredContent": out, "isError": False}
    raise LookupError(f"모르는 요청이에요: {method}")


@router.post("/mcp/{key}", include_in_schema=False)
def mcp(key: str = Path(max_length=200), msg: dict = Body(...), repo=Depends(get_repo)):
    uid = _owner(repo, key)
    if "id" not in msg:   # 알림(notifications/initialized 등): 답 없음
        return Response(status_code=202)
    try:
        return {"jsonrpc": "2.0", "id": msg["id"], "result": _answer(repo, uid, msg.get("method"), msg.get("params") or {})}
    except LookupError as e:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": str(e)}}


@router.get("/mcp/{key}", include_in_schema=False)
def mcp_stream(key: str = Path(max_length=200)):
    return Response(status_code=405)   # 서버가 먼저 보내는 흐름(SSE)은 없음
