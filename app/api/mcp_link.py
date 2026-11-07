"""
app/api/mcp_link.py — AI 비서에 연결(원격 MCP, 시험판 2026-11-07).

설정 '앱 → AI 비서에 연결'에서 연결 주소를 만들면 그 사람 전용 열쇠가 든 주소(/mcp/<열쇠>)를 한 번 보여 준다. Claude 앱의
'커스텀 커넥터 추가'에 주소만 붙이면, AI 비서가 노션 · 메모 · 파일에서 읽은 일기를 이 주소의 도구로 넘긴다(토큰 복사 없음).
열쇠 = 사용자 id · 열쇠 id · 만료를 사용자별 HMAC(security.digest)으로 서명한 것. 저장하는 건 지금 열쇠 id · 만료뿐(설정, 암호화).
30일 뒤 만료, '연결 끊기'나 새 주소를 만들면 예전 주소는 바로 안 된다. 이 열쇠로는 아래 도구 셋만 쓸 수 있다(다른 API 는 안 열림).
MCP 는 Streamable HTTP 의 상태 없는 JSON 응답만 한다(initialize · tools/list · tools/call · ping) — 의존성 추가 없음.
도구 이름 · 설명 · 입력 검사는 로컬 stdio 판과 같다(app/service/mcp_input.py). 정리는 앱 가져오기처럼 오래된 글부터 한 편씩.
Vercel 은 응답이 끝나면 함수를 멈출 수 있어서, 도구는 바로 답하고 정리는 이 주소로 한 번 더 보낸 내부 요청(x/run)이 맡는다:
그 응답은 흘려보내는 SSE(/diary/stream 과 같은 _Drain)라 보낸 쪽이 끊어도 끝까지 돌고, 5분 한도(maxDuration 300)에 가까우면
남은 글을 다음 x/run 으로 넘긴다. 하루 글 수 · 월 비용 상한은 /diary 와 같은 _create 가 건다.
"""

import hmac
import json
import queue
import secrets
import time
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Body, Depends, Path, Request, Response
from pydantic import ValidationError

from app.api import consent
from app.api import diary as diary_api
from app.core import logger, security
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import DiaryIn
from app.repository import diary, views
from app.service import mcp_input as mi

router = APIRouter(tags=["AI 비서 연결"])
DAYS = 30
VERSION = "2025-06-18"   # 클라이언트가 다른 판을 말하면 그 판으로 답한다(도구만 쓰니 판마다 같음)
NEW_ENTRY_UNTIL_S = 170  # x/run 하나가 새 글을 시작하는 시한(한 편 60~120초, 함수 한도 300초 안에서 끝나게). 넘으면 다음 x/run 으로


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


def _kick(url, bodies):
    """정리를 이 주소의 x/run 에 맡긴다: 응답 머리만 받고 끊는다(받는 쪽은 _Drain 이라 끝까지 돎). 못 맡기면 RuntimeError."""
    msg = {"jsonrpc": "2.0", "id": 0, "method": "x/run", "params": {"bodies": bodies}}
    try:
        with httpx.stream("POST", url, json=msg, timeout=20) as r:
            ok = r.status_code == 200
    except httpx.HTTPError:
        ok = False
    if not ok:
        raise RuntimeError("정리를 시작하지 못했어요. 잠시 뒤 다시 넣어 주세요(이미 넣은 글은 건너뛰어요).")


def _run(repo, uid, url, bodies):
    """x/run 의 SSE 흐름: 오래된 글부터 기록 만들기(/diary 와 같은 동의 · 한도 · 같은 글 확인) → 정리 끝까지 기다림 → 다음 글."""
    t0 = time.monotonic()
    yield ": run\n\n"
    for i, b in enumerate(bodies):
        if time.monotonic() - t0 > NEW_ENTRY_UNTIL_S:
            try:
                _kick(url, bodies[i:])
            except RuntimeError:
                logger.log("error", step="mcp_import", code="kick_failed", left=len(bodies) - i)
            return
        try:
            eid, dup = diary_api._create(repo, uid, DiaryIn(**b))
            if dup:
                continue
            q = diary_api._start(repo, uid, eid, "mcp.import")
            while True:
                try:
                    if q.get(timeout=diary_api.KEEPALIVE_S) is None:
                        break
                except queue.Empty:
                    yield ": keep-alive\n\n"
        except Exception as e:   # noqa: BLE001 — 한 편이 어떻게 실패하든 다음 글로(멈춘 글은 앱에서 '이어서 하기')
            logger.log("error", step="mcp_import", code=getattr(e, "code", type(e).__name__))


def _send(repo, uid, url, bodies):
    _kick(url, bodies)
    return {"accepted": len(bodies), "est_minutes": len(bodies), "note": mi.NOTE}


def _ready(repo, uid):
    with repo.session(uid) as s:
        if consent.needed(s):
            raise ValueError("나의 우주 앱에서 이용 동의를 먼저 해 주세요(처음 로그인할 때 나오는 화면).")


def _import(repo, uid, url, a):
    bodies = mi.batch(a.get("entries") or [])
    _ready(repo, uid)
    return _send(repo, uid, url, bodies)


def _write(repo, uid, url, a):
    b = mi.body(1, mi.Diary(**a), mi.WRITTEN)
    _ready(repo, uid)
    return _send(repo, uid, url, [b])


def _recent(repo, uid, url, a):
    with repo.session(uid) as s:
        got = views.entry_list(s, max(1, min(int(a.get("n") or 10), 100)))
    return {"diaries": [{"date": e["day"], "title": e["title"], "status": e["status"], "source": e["source"]} for e in got],
            "processing": sum(e["status"] == "processing" for e in got)}


ITEM = mi.Diary.model_json_schema()
TOOLS = {
    "import_diaries": (_import, mi.DOCS["import_diaries"], {
        "type": "object", "required": ["entries"],
        "properties": {"entries": {"type": "array", "maxItems": mi.MAX_BATCH, "items": ITEM}}}),
    "write_diary": (_write, mi.DOCS["write_diary"], ITEM),
    "recent_diaries": (_recent, mi.DOCS["recent_diaries"], {
        "type": "object", "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}}}),
}
def _answer(repo, uid, url, method, params):
    if method == "initialize":
        return {"protocolVersion": params.get("protocolVersion") or VERSION, "capabilities": {"tools": {}},
                "serverInfo": {"name": "나의 우주", "version": "0.1"}, "instructions": mi.INSTRUCTIONS}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": [{"name": n, "description": " ".join(d.split()), "inputSchema": sch} for n, (_, d, sch) in TOOLS.items()]}
    if method == "tools/call":
        name = params.get("name")
        if name not in TOOLS:
            raise LookupError(f"없는 도구예요: {name}")
        try:
            out = TOOLS[name][0](repo, uid, url, params.get("arguments") or {})
        except (ValueError, ValidationError, ApiError, RuntimeError) as e:   # 입력 · 동의 · 한도: AI 비서가 사용자에게 전할 안내
            msg = e.message if isinstance(e, ApiError) else str(e)
            return {"content": [{"type": "text", "text": msg}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}], "structuredContent": out, "isError": False}
    raise LookupError(f"모르는 요청이에요: {method}")


def _bodies(params):
    """x/run 이 받은 본문: 우리가 만든 모양(가져온 글 · 텍스트)만, 50편까지. 열쇠를 가진 사람이 바로 불러도 도구보다 넓게 열리지 않게."""
    bodies = params.get("bodies")
    if not isinstance(bodies, list) or not 0 < len(bodies) <= mi.MAX_BATCH:
        raise ApiError(422, "invalid_input", "입력을 확인해 주세요: bodies")
    for b in bodies:
        if not isinstance(b, dict) or b.get("source") not in (mi.IMPORTED, mi.WRITTEN) or b.get("confirm"):
            raise ApiError(422, "invalid_input", "입력을 확인해 주세요: bodies")
        DiaryIn(**b)
    return bodies


def _self_url(request: Request):
    """이 요청이 들어온 주소(Vercel 은 앞단이 https 를 끊어 주므로 x-forwarded-proto 를 따름)."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{proto}://{request.headers.get('host', request.url.netloc)}{request.url.path}"


@router.post("/mcp/{key}", include_in_schema=False)
def mcp(request: Request, key: str = Path(max_length=200), msg: dict = Body(...), repo=Depends(get_repo)):
    uid = _owner(repo, key)
    if "id" not in msg:   # 알림(notifications/initialized 등): 답 없음
        return Response(status_code=202)
    url = _self_url(request)
    if msg.get("method") == "x/run":   # 내부: 정리 맡기(흘려보내는 응답, 보낸 쪽이 끊어도 끝까지)
        try:
            bodies = _bodies(msg.get("params") or {})
        except ValidationError:
            raise ApiError(422, "invalid_input", "입력을 확인해 주세요: bodies")
        return diary_api._Drain(_run(repo, uid, url, bodies))
    try:
        return {"jsonrpc": "2.0", "id": msg["id"], "result": _answer(repo, uid, url, msg.get("method"), msg.get("params") or {})}
    except LookupError as e:
        return {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": str(e)}}


@router.get("/mcp/{key}", include_in_schema=False)
def mcp_stream(key: str = Path(max_length=200)):
    return Response(status_code=405)   # 서버가 먼저 보내는 흐름(SSE)은 없음
