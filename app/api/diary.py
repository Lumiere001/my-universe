"""
app/api/diary.py

일기 쓰기(SSE) · 읽기 · 지우기 · 이어 하기.
그래프는 백그라운드 스레드에서 돌고, 응답은 그 진행을 SSE 로 흘린다(event: progress/result/error, 약 10초마다 ': keep-alive').
손님이 끊어도 스레드는 끝까지 간다. Vercel 에서도 그러도록 응답(_Drain)이 남은 흐름을 끝까지 읽으며 요청을 붙잡아 둔다.
끊긴 뒤에는 GET /diary/{id} → POST /diary/{id}/resume/stream.
정리가 끝나면 알림(2026-11-04): 정리 중 '끝나면 알림 받기' → POST /diary/{id}/notify 가 그 기기 알림 주소를 이 기록에 암호화해 두고,
그래프가 끝난 뒤 화면이 결과를 받아 거두지 않았으면(앱을 닫음) 알림 한 줄을 보낸다.
같은 기록을 두 번 돌리지 않게 DB 잠금(entries.locked_until, 조건부 update)을 쓴다 — 인스턴스가 여러 개여도 하나만 돈다.
같은 글(같은 설정) · 같은 원본이 다시 오면 Studio 를 부르지 않고 그 기록으로 안내한다(PRD §8.5 A, 상한이 아니라 중복 막기).
요약 확인(WS20): 대화 초안 · confirm 칸이 참인 글은 save 앞에서 멈춰 status 'confirm' 결과를 주고,
POST /diary/{id}/confirm 이 고친 것을 넣어 저장한다. 텍스트 길(confirm 없음)은 그대로.
"""

import contextlib
import contextvars
import json
import queue
import threading
import time
from collections import deque
from datetime import datetime
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, Path, Query, Response
from fastapi.responses import StreamingResponse
from psycopg.errors import UniqueViolation

from app.agents import graph
from app.api import consent
from app.core import config, logger, trace
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import ConfirmIn, DiaryIn, NotifyIn
from app.repository import conversations, diary, drafts, views
from app.service import push

router = APIRouter(tags=["일기"])
KEEPALIVE_S = 10
DONE_GRACE_S = 5   # 정리가 끝난 뒤, 결과를 받은 화면이 알림을 거둘 틈(화면에 있으면 알림을 보내지 않는다)
Id = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]   # id 모양만(제어 문자 · 다른 글자는 422)
MESSAGES = {
    "studio_timeout": "생각을 나누는 데 시간이 오래 걸리고 있어요. '이어서 하기'를 눌러 주세요.",
    "studio_failed": "생각을 나누다 멈췄어요. '이어서 하기'를 눌러 주세요.",
    "studio_rate_limited": "지금 정리 요청이 몰려 잠깐 멈췄어요. 조금 뒤 '이어서 하기'를 눌러 주세요.",
    "studio_bad_output": "생각을 나눈 결과를 읽지 못했어요. '이어서 하기'를 눌러 주세요.",
    "llm_failed": "별지기가 잠깐 대답하지 못했어요. '이어서 하기'를 눌러 주세요.",
    "real_name_leak": "이름을 가리는 중에 문제가 생겨 밖으로 보내지 않았어요. 글은 안전하게 저장돼 있어요.",
    "internal": "정리하다 멈췄어요. '이어서 하기'를 눌러 주세요.",
    "duplicate": "이미 보낸 글이에요. 정리가 끝나지 않았으니 '이어서 하기'를 눌러 주세요.",
    "duplicate_leak": "이미 보낸 글이에요. 이름을 가리는 중에 문제가 생겨 밖으로 보내지 않았어요. 글은 안전하게 저장돼 있어요.",
}


def _start(repo, uid, eid, name="diary.stream"):
    """그래프를 백그라운드로 돌리고 (사건, 값) 줄을 돌려준다. 부르기 전에 diary.lock 으로 잠금을 잡아 둔다(끝나면 풂).
    name: 이 실행의 맨 위 span(추적, 부른 쪽 span 이 있으면 그 아래)."""
    q = queue.Queue()

    def work():
        try:
            with trace.span(name, kind="CHAIN", entry_id=eid):
                status = _work()
            _notify_done(repo, uid, eid, status)
        finally:
            q.put(None)   # span 을 닫은 뒤 끝을 알린다

    def _work():
        try:
            graph.run(repo, uid, eid, lambda p: q.put(("progress", p)))
            with repo.session(uid) as s:
                r = views.entry_result(s, eid)
            trace.set(status=r["status"])
            q.put(("result", r))
            return r["status"]
        except Exception as e:
            code = graph.error_code(e)
            trace.set(status="failed", error_code=code)
            q.put(("error", {"entry_id": eid, "code": code, "message": MESSAGES.get(code, MESSAGES["internal"]),
                             "resumable": code != "real_name_leak"}))
        finally:
            with repo.session(uid) as s:
                diary.unlock(s, eid)

    # 지금 문맥(추적 span)을 들고 간다
    threading.Thread(target=contextvars.copy_context().run, args=(work,), name=f"diary-{eid}", daemon=True).start()
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


class _Drain(StreamingResponse):
    """SSE 응답. 손님이 끊어도(앱을 닫음) 남은 흐름을 끝까지 읽어 이 요청을 살려 둔다 — 요청이 끝나면 Vercel 이 인스턴스를 멈출 수 있어
    정리가 멈추고 '끝나면 알림'도 못 간다(2026-11-04). 흐름은 그래프 스레드가 끝나면 끝난다(vercel.json maxDuration 300초 안)."""

    def __init__(self, content):
        self._rest = iter(content)
        super().__init__(self._rest, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True), contextlib.suppress(Exception):
                await anyio.to_thread.run_sync(deque, self._rest, 0)   # 다 읽었으면 바로 끝남


def _stream(q):
    return _Drain(_sse(q))


def _notify_done(repo, uid, eid, status):
    """'끝나면 알림 받기'를 맡긴 기록이면, 화면이 결과를 받아 거두지 않았을 때(앱을 닫음) 그 기기로 알림 한 줄(일기 내용 없음)."""
    def row(s):
        r = s.rows("entries", id=eid)
        return r[0] if r and r[0].get("notify_enc") else None
    try:
        with repo.session(uid) as s:
            if not row(s) or not config.VAPID_PRIVATE_KEY:
                return
        time.sleep(DONE_GRACE_S)   # 화면에 있으면 결과를 받자마자 DELETE /diary/{id}/notify 로 거둔다
        with repo.session(uid) as s:
            r = row(s)
            if not r:
                logger.log("step", step="push_done", code="seen")
                return
            s.update("entries", {"notify_enc": None}, id=eid)
            sub = diary.unseal(s, "entries.notify", eid, r["notify_enc"])
        url = "/talk" if r.get("source") == "대화" else f"/history?id={eid}"
        res = push.send(sub, push.done_payload(status, url), config.VAPID_PRIVATE_KEY, config.VAPID_SUBJECT)
        logger.log("step", step="push_done", code=None if res == "ok" else res)
    except Exception as e:   # 알림은 덤: 정리 결과에는 영향 없음
        logger.log("error", step="push_done", code="internal", what=type(e).__name__)


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
        q = _start(repo, user["id"], eid, "diary.write")
        out = None
        while (item := q.get()) is not None:
            out = item
        ev, data = out
    if ev == "error":
        raise ApiError(409 if dup else 502, data["code"], data["message"])
    return data


@router.post("/diary/{eid}/notify", summary="정리가 끝나면 이 기기로 알림(정리 중일 때만, 알림 주소 · 키는 이 기록에 암호화)")
def notify(body: NotifyIn, eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        row = s.rows("entries", id=eid)
        if not row:
            raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
        if not (config.VAPID_PRIVATE_KEY and diary.is_locked(row[0])):   # 이미 끝났으면 화면이 결과를 받는다
            return {"waiting": False}
        # ponytail: 잠금을 본 뒤 저장하기 전에 정리가 끝나면 알림이 안 간다(그 순간 화면에 있으니 결과를 봄)
        s.update("entries", {"notify_enc": diary.seal(s, "entries.notify", eid, {"endpoint": body.endpoint, "keys": body.keys})},
                 id=eid)
    return {"waiting": True}


@router.delete("/diary/{eid}/notify", status_code=204, summary="화면이 결과를 받았으면 '끝나면 알림'을 거둔다")
def unnotify(eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        s.update("entries", {"notify_enc": None}, id=eid)
    return Response(status_code=204)


@router.post("/diary/{eid}/resume/stream", summary="끊긴 기록 이어 하기(SSE, 끝난 단계는 건너뜀)")
def resume(eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        if not s.rows("entries", id=eid):
            raise ApiError(404, "not_found", "멈춘 기록을 찾지 못했어요. 글을 다시 띄워 주세요.")
        consent.check(s)
        _limits(s, eid)
        if config.RESUME_LIMIT > 0 and diary.resumes(s, eid) >= config.RESUME_LIMIT:
            raise ApiError(429, "resume_limit", f"이 기록은 {config.RESUME_LIMIT}번까지 이어서 할 수 있어요. 운영자에게 알려 주세요.")
        if not diary.lock(s, eid):
            raise ApiError(409, "already_running", "이 글은 지금 정리하고 있어요. 조금만 기다려 주세요.")
        diary.add_run(s, eid, "resume")
    return _stream(_start(repo, user["id"], eid, "diary.resume"))


LIST_MAX = 500   # 지난 기록 달력 · 찾기 · 주제별은 기록을 한 번에 모두 읽는다(더 있으면 before 로 이어 읽음, docs/api-v8.md §2)


@router.get("/diary", summary="기록 목록")
def list_entries(limit: int = Query(20, ge=1, le=LIST_MAX), before: datetime | None = None,
                 user=Depends(get_user), repo=Depends(get_repo)):
    """먼저 쓴 것이 뒤로(written_at 내림차순), before 보다 앞에 쓴 것만."""
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
            raise ApiError(404, "not_found", "이 기록을 찾지 못했어요. 이미 지워졌을 수 있어요.")
        if diary.is_locked(row[0]):
            raise ApiError(409, "already_running", "정리가 끝난 뒤에 지울 수 있어요.")
        diary.delete_entry(s, repo.vectors, eid)
    return Response(status_code=204)


@router.post("/diary/{eid}/confirm", summary="요약 확인: 고친 것(요약 · 생각 종류 · 생각 빼기)을 넣고 우주에 저장(WS20)")
def confirm(body: ConfirmIn, eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    """확인을 기다리는 초안만. 고친 것 · 맞아요는 오답 재료(feedback, 암호문)로 남기고, 저장하면 그 대화의 턴을 기록 안으로
    옮기고 대화 행은 지운다(PRD v9 Q19: 정리본과 대화를 함께 봄). save 는 외부 호출이 없지만 대화 길의 마지막이라 동의를 같이 본다."""
    uid = user["id"]
    with repo.session(uid) as s:
        e = diary.entry(s, eid)
        if not e:
            raise ApiError(404, "not_found", "이 정리를 찾지 못했어요. '대화 마치고 정리하기'를 다시 눌러 주세요.")
        consent.check(s)
        if not drafts.pending(e):
            raise ApiError(409, "not_waiting", "이미 저장했거나 확인할 수 없는 정리예요. 화면을 새로 고쳐 주세요.")
        if not diary.lock(s, eid):
            raise ApiError(409, "already_running", "아직 정리하고 있어요. 조금 뒤 다시 눌러 주세요.")
        try:
            seen = drafts.confirm(s, repo.vectors, e, body.summary, [f.model_dump() for f in body.fixes], body.agreed)
        except KeyError:
            diary.unlock(s, eid)
            raise ApiError(422, "invalid_input", "고칠 생각을 찾지 못했어요. 화면을 새로 고친 뒤 다시 해 주세요.")
        diary.add_run(s, eid, "confirm", meta=seen)   # 운영 지표: 항목 수 · 고친 수(WS22)
    try:
        graph.run(repo, uid, eid)   # 끝난 노드는 건너뛰고 save 만(외부 호출 없음)
    except Exception as err:
        code = graph.error_code(err)
        raise ApiError(502, code, MESSAGES.get(code, MESSAGES["internal"]))
    finally:
        with repo.session(uid) as s:
            diary.unlock(s, eid)
    with repo.session(uid) as s:
        c = conversations.by_entry(s, eid)
        if c and c.get("turns"):
            diary.keep_talk(s, eid, c["turns"])
        conversations.delete(s, entry_id=eid)
        return views.entry_result(s, eid)
