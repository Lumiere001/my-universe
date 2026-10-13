"""
app/api/diary.py

일기 쓰기(SSE) · 읽기 · 지우기 · 이어 하기.
그래프는 백그라운드 스레드에서 돌고, 응답은 그 진행을 SSE 로 흘린다(event: progress/result/error, 약 10초마다 ': keep-alive').
손님이 끊어도 스레드는 끝까지 간다(로컬 · Docker). 끊긴 뒤에는 GET /diary/{id} → POST /diary/{id}/resume/stream.
같은 기록을 두 번 돌리지 않게 DB 잠금(entries.locked_until, 조건부 update)을 쓴다 — 인스턴스가 여러 개여도 하나만 돈다.
같은 글(같은 설정) · 같은 원본이 다시 오면 Studio 를 부르지 않고 그 기록으로 안내한다(PRD §8.5 A, 상한이 아니라 중복 막기).
요약 확인(WS20): 대화 초안 · confirm 칸이 참인 글은 save 앞에서 멈춰 status 'confirm' 결과를 주고,
POST /diary/{id}/confirm 이 고친 것을 넣어 저장한다. 텍스트 길(confirm 없음)은 그대로.
"""

import json
import queue
import threading
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.responses import StreamingResponse
from psycopg.errors import UniqueViolation

from app.agents import graph
from app.api import consent
from app.core import config
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import ConfirmIn, DiaryIn
from app.repository import conversations, diary, drafts, views

router = APIRouter(tags=["일기"])
KEEPALIVE_S = 10
Id = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]   # id 모양만(제어 문자 · 다른 글자는 422)
MESSAGES = {
    "studio_timeout": "생각을 나누는 데 시간이 오래 걸리고 있어요. '이어서 하기'를 눌러 주세요.",
    "studio_failed": "생각을 나누다 멈췄어요. '이어서 하기'를 눌러 주세요.",
    "studio_bad_output": "생각을 나눈 결과를 읽지 못했어요. '이어서 하기'를 눌러 주세요.",
    "llm_failed": "별지기가 잠깐 대답하지 못했어요. '이어서 하기'를 눌러 주세요.",
    "real_name_leak": "이름을 가리는 중에 문제가 생겨 밖으로 보내지 않았어요. 글은 안전하게 저장돼 있어요.",
    "internal": "처리하다 멈췄어요. '이어서 하기'를 눌러 주세요.",
    "duplicate": "이미 보낸 글이에요. 정리가 끝나지 않았으니 '이어서 하기'를 눌러 주세요.",
    "duplicate_leak": "이미 보낸 글이에요. 이름을 가리는 중에 문제가 생겨 밖으로 보내지 않았어요. 글은 안전하게 저장돼 있어요.",
}


def _start(repo, uid, eid):
    """그래프를 백그라운드로 돌리고 (사건, 값) 줄을 돌려준다. 부르기 전에 diary.lock 으로 잠금을 잡아 둔다(끝나면 풂)."""
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
            try:
                with repo.session(uid) as s:
                    diary.unlock(s, eid)
            finally:
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


def _limits(s, eid=None):
    """하루 처리 글 수(오늘 시작 · 이어 한 기록 수) · 이번 달 추정 비용 상한. 0 이면 그 상한은 없다(기본).
    이미 오늘 센 기록을 이어 하는 건 하루 수에 더하지 않는다."""
    if config.DAILY_ENTRY_LIMIT > 0:
        today = diary.processed_today(s)
        if eid not in today and len(today) >= config.DAILY_ENTRY_LIMIT:
            raise ApiError(429, "daily_limit", f"오늘은 글을 {config.DAILY_ENTRY_LIMIT}편까지 정리할 수 있어요. 내일 다시 써 주세요.")
    if config.MONTHLY_COST_CAP_USD > 0 and diary.month_cost(s) >= config.MONTHLY_COST_CAP_USD:
        raise ApiError(429, "monthly_budget", "이번 달 정리 한도에 닿았어요. 운영자에게 알려 주세요.")


def _same(repo, uid, eid):
    """이미 받은 글: 끝났으면 그 결과(duplicate: true), 아니면 그 기록을 이어 하라는 error(409 성격).
    실명이 새어 나갈 뻔해 멈춘 글이면 이어 하기를 권하지 않는다(resumable: false)."""
    with repo.session(uid) as s:
        r = views.entry_result(s, eid)
        leak = s.rows("entries", id=eid)[0]["error_code"] == "real_name_leak"
    if r["status"] == "done":
        return "result", {**r, "duplicate": True}
    return "error", {"entry_id": eid, "code": "duplicate", "message": MESSAGES["duplicate_leak" if leak else "duplicate"],
                     "resumable": not leak}


def _create(repo, uid, body: DiaryIn):
    """→ (기록 id, 이미 있던 같은 글인지)."""
    written = body.written_at or datetime.now(diary.TZ)
    if not written.tzinfo:
        written = written.replace(tzinfo=diary.TZ)
    try:
        with repo.session(uid) as s:
            consent.check(s)   # 지금 판에 동의하지 않았으면 403(외부 AI 로 나가기 전에)
            drafts.expire(s, repo.vectors)   # 확인하지 않고 오래 둔 대화 초안 정리(WS20, 따로 도는 작업 없음)
            diary.profile(s)
            same = diary.same_entry(s, body.title, body.text, written, body.source, body.source_ref)
            if same:
                return same, True
            _limits(s)
            eid = diary.new_id("e")
            diary.create_entry(s, eid, written, body.weather, body.title, body.text, body.source, body.source_ref, body.day)
            if body.confirm:   # 요약 확인 뒤 저장(대화 초안은 create_entry 가 이미 '확인 전')
                s.update("entries", {"confirmed": drafts.WAITING}, id=eid)
            diary.lock(s, eid)
            diary.add_run(s, eid, "start")
    except UniqueViolation:   # 같은 원본을 동시에 두 번 가져옴: DB 유일 색인이 뒤의 것을 막음 → 먼저 들어간 기록으로 안내
        with repo.session(uid) as s:
            same = diary.same_entry(s, body.title, body.text, written, body.source, body.source_ref)
        if not same:
            raise
        return same, True
    return eid, False


@router.post("/diary/stream", summary="일기 쓰기(SSE 진행)")
def write_stream(body: DiaryIn, user=Depends(get_user), repo=Depends(get_repo)):
    eid, dup = _create(repo, user["id"], body)
    if dup:
        q = queue.Queue()
        q.put(_same(repo, user["id"], eid))
        q.put(None)
        return _stream(q)
    return _stream(_start(repo, user["id"], eid))


@router.post("/diary", summary="일기 쓰기(스트림 없이, 시험 · curl용)")
def write(body: DiaryIn, user=Depends(get_user), repo=Depends(get_repo)):
    eid, dup = _create(repo, user["id"], body)
    if dup:
        ev, data = _same(repo, user["id"], eid)
    else:
        q = _start(repo, user["id"], eid)
        out = None
        while (item := q.get()) is not None:
            out = item
        ev, data = out
    if ev == "error":
        raise ApiError(409 if dup else 502, data["code"], data["message"])
    return data


@router.post("/diary/{eid}/resume/stream", summary="끊긴 기록 이어 하기(SSE, 끝난 단계는 건너뜀)")
def resume(eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        if not s.rows("entries", id=eid):
            raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
        consent.check(s)
        _limits(s, eid)
        if config.RESUME_LIMIT > 0 and diary.resumes(s, eid) >= config.RESUME_LIMIT:
            raise ApiError(429, "resume_limit", f"이 기록은 {config.RESUME_LIMIT}번까지 이어서 할 수 있어요. 운영자에게 알려 주세요.")
        if not diary.lock(s, eid):
            raise ApiError(409, "already_running", "이 기록은 지금 정리 중이에요.")
        diary.add_run(s, eid, "resume")
    return _stream(_start(repo, user["id"], eid))


@router.get("/diary", summary="기록 목록")
def list_entries(limit: int = Query(20, ge=1, le=100), before: datetime | None = None,
                 user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return {"entries": views.entry_list(s, limit, before)}


@router.get("/diary/{eid}", summary="기록 하나(EntryResult)")
def get_entry(eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        r = views.entry_result(s, eid)
        row = s.rows("entries", id=eid)
    if not r:
        raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
    if r["status"] == "processing" and not diary.is_locked(row[0]):
        r["status"] = "failed"   # 잠금이 풀렸거나 만료(서버가 멈춘 기록): 화면이 '이어서 하기'를 보이게
    return r


@router.delete("/diary/{eid}", status_code=204, summary="기록 지우기(생각 · 관계 · 피드백 · 벡터까지)")
def delete_entry(eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        row = s.rows("entries", id=eid)
        if not row:
            raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
        if diary.is_locked(row[0]):
            raise ApiError(409, "already_running", "정리가 끝난 뒤에 지울 수 있어요.")
        diary.delete_entry(s, repo.vectors, eid)
    return Response(status_code=204)


@router.post("/diary/{eid}/confirm", summary="요약 확인: 고친 것(요약 · 생각 종류 · 생각 빼기)을 넣고 우주에 저장(WS20)")
def confirm(body: ConfirmIn, eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    """확인을 기다리는 초안만. 고친 것 · 맞아요는 오답 재료(feedback, 암호문)로 남기고, 저장하면 그 대화의 턴을 지운다
    (확인한 정리본 = 기록만 남김). save 는 외부 호출이 없지만 대화 길의 마지막이라 동의를 같이 본다."""
    uid = user["id"]
    with repo.session(uid) as s:
        e = diary.entry(s, eid)
        if not e:
            raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
        consent.check(s)
        if not drafts.pending(e):
            raise ApiError(409, "not_waiting", "확인을 기다리는 기록이 아니에요.")
        if not diary.lock(s, eid):
            raise ApiError(409, "already_running", "이 기록은 지금 정리 중이에요.")
        try:
            drafts.confirm(s, repo.vectors, e, body.summary, [f.model_dump() for f in body.fixes], body.agreed)
        except KeyError:
            diary.unlock(s, eid)
            raise ApiError(422, "invalid_input", "고칠 생각을 찾지 못했어요.")
        diary.add_run(s, eid, "confirm")
    try:
        graph.run(repo, uid, eid)   # 끝난 노드는 건너뛰고 save 만(외부 호출 없음)
    except Exception as err:
        code = graph.error_code(err)
        raise ApiError(502, code, MESSAGES.get(code, MESSAGES["internal"]))
    finally:
        with repo.session(uid) as s:
            diary.unlock(s, eid)
    with repo.session(uid) as s:
        conversations.delete(s, entry_id=eid)
        return views.entry_result(s, eid)
