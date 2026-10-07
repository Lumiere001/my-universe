"""
app/api/diary.py

일기 쓰기(SSE) · 읽기 · 지우기 · 이어 하기.
그래프는 백그라운드 스레드에서 돌고, 응답은 그 진행을 SSE 로 흘린다(event: progress/result/error, 약 10초마다 ': keep-alive').
손님이 끊어도 스레드는 끝까지 간다(로컬 · Docker). 끊긴 뒤에는 GET /diary/{id} → POST /diary/{id}/resume/stream.
"""

import json
import queue
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse

from app.agents import graph
from app.core import config
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import DiaryIn
from app.repository import diary, views

router = APIRouter(tags=["일기"])
KEEPALIVE_S = 10
_running, _lock = set(), threading.Lock()
MESSAGES = {
    "studio_timeout": "생각을 나누는 데 시간이 오래 걸리고 있어요. '이어서 하기'를 눌러 주세요.",
    "studio_failed": "생각을 나누다 멈췄어요. '이어서 하기'를 눌러 주세요.",
    "studio_bad_output": "생각을 나눈 결과를 읽지 못했어요. '이어서 하기'를 눌러 주세요.",
    "llm_failed": "별지기가 잠깐 대답하지 못했어요. '이어서 하기'를 눌러 주세요.",
    "real_name_leak": "이름을 가리는 중에 문제가 생겨 밖으로 보내지 않았어요. 글은 안전하게 저장돼 있어요.",
    "internal": "처리하다 멈췄어요. '이어서 하기'를 눌러 주세요.",
}


def _start(repo, uid, eid):
    """그래프를 백그라운드로 돌리고 (사건, 값) 줄을 돌려준다. 같은 기록을 두 번 동시에 돌리지 않는다."""
    with _lock:
        if eid in _running:
            raise ApiError(409, "already_running", "이 기록은 지금 정리 중이에요.")
        _running.add(eid)
    q = queue.Queue()

    def work():
        try:
            graph.run(repo, uid, eid, lambda p: q.put(("progress", p)))
            with repo.session(uid) as s:
                q.put(("result", views.entry_result(s, eid)))
        except Exception as e:
            code = graph.error_code(e)
            q.put(("error", {"entry_id": eid, "code": code, "message": MESSAGES.get(code, MESSAGES["internal"]),
                             "resumable": code != "real_name_leak"}))
        finally:
            with _lock:
                _running.discard(eid)
            q.put(None)

    threading.Thread(target=work, name=f"diary-{eid}", daemon=True).start()
    return q


def _sse(q):
    while True:
        try:
            item = q.get(timeout=KEEPALIVE_S)
        except queue.Empty:
            yield ": keep-alive\n\n"
            continue
        if item is None:
            return
        ev, data = item
        yield f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream(q):
    return StreamingResponse(_sse(q), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _create(repo, uid, body: DiaryIn):
    with repo.session(uid) as s:
        diary.profile(s)
        if diary.entries_today(s) >= config.DAILY_ENTRY_LIMIT:
            raise ApiError(429, "daily_limit", f"오늘은 글을 {config.DAILY_ENTRY_LIMIT}편까지 정리할 수 있어요. 내일 다시 써 주세요.")
        if diary.month_cost(s) >= config.MONTHLY_COST_CAP_USD:
            raise ApiError(429, "monthly_budget", "이번 달 정리 한도에 닿았어요. 운영자에게 알려 주세요.")
        eid = diary.new_id("e")
        written = body.written_at or datetime.now(diary.TZ)
        if not written.tzinfo:
            written = written.replace(tzinfo=diary.TZ)
        diary.create_entry(s, eid, written, body.weather, body.title, body.text)
    return eid


@router.post("/diary/stream", summary="일기 쓰기(SSE 진행)")
def write_stream(body: DiaryIn, user=Depends(get_user), repo=Depends(get_repo)):
    eid = _create(repo, user["id"], body)
    return _stream(_start(repo, user["id"], eid))


@router.post("/diary", summary="일기 쓰기(스트림 없이, 시험 · curl용)")
def write(body: DiaryIn, user=Depends(get_user), repo=Depends(get_repo)):
    eid = _create(repo, user["id"], body)
    q = _start(repo, user["id"], eid)
    out = None
    while (item := q.get()) is not None:
        out = item
    ev, data = out
    if ev == "error":
        raise ApiError(502, data["code"], data["message"])
    return data


@router.post("/diary/{eid}/resume/stream", summary="끊긴 기록 이어 하기(SSE, 끝난 단계는 건너뜀)")
def resume(eid: str, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        if not s.rows("entries", id=eid):
            raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
    return _stream(_start(repo, user["id"], eid))


@router.get("/diary", summary="기록 목록")
def list_entries(limit: int = Query(20, ge=1, le=100), before: datetime | None = None,
                 user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return {"entries": views.entry_list(s, limit, before)}


@router.get("/diary/{eid}", summary="기록 하나(EntryResult)")
def get_entry(eid: str, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        r = views.entry_result(s, eid)
    if not r:
        raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
    if r["status"] == "processing" and eid not in _running:
        r["status"] = "failed"   # 서버가 다시 켜져 멈춘 기록: 화면이 '이어서 하기'를 보이게
    return r


@router.delete("/diary/{eid}", status_code=204, summary="기록 지우기(생각 · 관계 · 벡터까지)")
def delete_entry(eid: str, user=Depends(get_user), repo=Depends(get_repo)):
    if eid in _running:
        raise ApiError(409, "already_running", "정리가 끝난 뒤에 지울 수 있어요.")
    with repo.session(user["id"]) as s:
        if not diary.delete_entry(s, repo.vectors, eid):
            raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
    return Response(status_code=204)
