"""
app/api/chat.py

대화(WS19): 이야기하기 화면. 서비스가 먼저 묻고(첫 말은 LLM 없이), 사용자 말 한 턴마다 대화 그래프(app/agents/chat_graph.py)가
답한다(SSE: progress → turn). '대화 마치고 정리하기'는 사용자 말만 근거로 일기 초안을 만들어 일기 그래프에 넣고 save 앞에서
멈춘 결과(status 'confirm')를 준다 → 화면이 요약 확인(POST /diary/{id}/confirm, WS20).
턴 원문은 서버에 둔다(2026-10-13 동규: 사용자별 키로 암호화, 다른 기기에서 이어 하기). 확인 · 저장하면 그 대화는 지운다.
외부 AI 로 나가는 요청(턴 · 정리)은 동의를 먼저 본다.
"""

import contextvars
import json
import queue
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from fastapi.responses import StreamingResponse

from app.agents import chat_graph
from app.api import consent
from app.api import diary as diary_api
from app.api.write import prompt
from app.core import trace
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import DiaryIn, TalkIn, TurnIn
from app.repository import conversations, diary, drafts, views

router = APIRouter(tags=["대화"])
Id = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
MESSAGES = {
    "llm_failed": "별지기가 잠깐 대답하지 못했어요. 다시 보내 주세요.",
    "real_name_leak": "이름을 가리는 중에 문제가 생겨 밖으로 보내지 않았어요. 말은 화면에 그대로 있어요.",
    "internal": "별지기가 답하다 멈췄어요. 다시 보내 주세요.",
}


def _get(s, cid):
    c = conversations.get(s, cid)
    if not c:
        raise ApiError(404, "not_found", "이 대화를 찾지 못했어요. 지워졌을 수 있어요. '새 대화 시작'을 눌러 주세요.")
    return c


def _ev(ev, data):
    return f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/talk", summary="새 대화(서비스가 먼저 묻는 첫 말, LLM 없음)")
def start(body: TalkIn | None = None, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        consent.check(s)
        drafts.expire(s, repo.vectors)
        for c in conversations.recent(s, limit=20):   # 말 한마디 없이 둔 대화는 새로 열 때 치운다
            if not c["turn_count"]:
                conversations.delete(s, id=c["id"])
        c = chat_graph.start(s, prompt(s), body and body.from_entry, views.aspiration_state(s)["ask"]["should_ask"])
        return chat_graph.view(c)


@router.get("/talk", summary="이어 할 대화(최근 것부터, 다른 기기에서 이어 하기)")
def recent(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return {"conversations": [chat_graph.view(c) for c in conversations.recent(s)]}


@router.get("/talk/{cid}", summary="대화 하나")
def get_talk(cid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return chat_graph.view(_get(s, cid))


@router.delete("/talk/{cid}", status_code=204, summary="대화 지우기(확인 전 초안도 같이)")
def delete_talk(cid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        c = _get(s, cid)
        e = diary.entry(s, c["entry_id"]) if c.get("entry_id") else None
        if e and diary.is_locked(e):
            raise ApiError(409, "already_running", "정리가 끝난 뒤에 지울 수 있어요.")
        if e and e.get("confirmed") == drafts.WAITING:
            diary.delete_entry(s, repo.vectors, e["id"])
        conversations.delete(s, id=cid)
    return Response(status_code=204)


def _turn_queue(repo, uid, cid, text, via="text"):
    q = queue.Queue()

    def work():
        try:
            with trace.span("talk.turn", kind="CHAIN", conversation_id=cid):
                _work()
        finally:
            q.put(None)   # span 을 닫은 뒤 끝을 알린다

    def _work():
        try:
            v = chat_graph.turn(repo, uid, cid, text, lambda p: q.put(("progress", p)), via)
            q.put(("turn", v) if v else ("error", {"conversation_id": cid, "code": "not_found",
                                                   "message": "이 대화를 찾지 못했어요. 지워졌을 수 있어요. '새 대화 시작'을 눌러 주세요.", "resumable": False}))
        except Exception as e:
            code = chat_graph.error_code(e)
            trace.set(error_code=code)
            code = code if code in MESSAGES else "internal"
            q.put(("error", {"conversation_id": cid, "code": code, "message": MESSAGES[code], "resumable": code != "real_name_leak"}))

    threading.Thread(target=contextvars.copy_context().run, args=(work,), name=f"talk-{cid}", daemon=True).start()
    return q


def _check(repo, uid, cid):
    with repo.session(uid) as s:
        _get(s, cid)
        consent.check(s)


@router.post("/talk/{cid}/turn/stream", summary="사용자 말 한 턴(SSE: progress → turn | error)")
def turn_stream(body: TurnIn, cid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    _check(repo, user["id"], cid)
    return diary_api._stream(_turn_queue(repo, user["id"], cid, body.text, body.via))


@router.post("/talk/{cid}/turn", summary="사용자 말 한 턴(스트림 없이, 시험 · curl용)")
def turn(body: TurnIn, cid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    _check(repo, user["id"], cid)
    q = _turn_queue(repo, user["id"], cid, body.text, body.via)
    out = None
    while (item := q.get()) is not None:
        out = item
    ev, data = out
    if ev == "error":
        raise ApiError(404 if data["code"] == "not_found" else 502, data["code"], data["message"])
    return data


@router.post("/talk/{cid}/finish/stream", summary="대화 마치고 정리하기(SSE: 초안 → 일기 그래프 → 확인을 기다리는 결과)")
def finish(cid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    uid = user["id"]
    with repo.session(uid) as s:
        c = _get(s, cid)
        consent.check(s)
        drafts.expire(s, repo.vectors)
        if not c["turn_count"]:
            raise ApiError(409, "no_turns", "먼저 이야기를 들려주세요.")
        e = diary.entry(s, c["entry_id"]) if c.get("entry_id") else None
        if e and diary.is_locked(e):
            raise ApiError(409, "already_running", "지금 정리하고 있어요. 조금만 기다려 주세요.")
        if e and drafts.pending(e) and c.get("drafted") == c["turn_count"]:   # 그 뒤로 말이 없으면 만든 초안 그대로
            return diary_api._stream(_done(views.entry_result(s, e["id"])))
        if e and e.get("confirmed") == drafts.WAITING:   # 이야기가 늘었으면 초안을 다시 만든다
            diary.delete_entry(s, repo.vectors, e["id"])
        n = c["turn_count"]

    def gen():
        yield _ev("progress", {"conversation_id": cid, "entry_id": None, "step": "draft", "label": "대화를 일기로 정리하는 중",
                               "done": 0, "total": 7})
        sp = trace.start("talk.finish", kind="CHAIN", conversation_id=cid)   # yield 를 건너므로 with 대신 직접 끝냄
        try:
            with trace.use(sp):   # 일기 그래프 span 이 이 span 아래로(스레드가 문맥을 들고 감)
                first, q = draft()
            if first:
                yield first
            if q:
                yield from diary_api._sse(q)
        finally:
            sp.end()

    def draft():
        """→ (먼저 보낼 사건, 일기 그래프 줄). 둘 중 하나만."""
        try:
            d = chat_graph.make_draft(repo, uid, cid)
            eid, dup = diary_api._create(repo, uid, DiaryIn(text=d["text"], title=d["title"], source="대화", confirm=True))
        except ApiError as err:
            trace.set(error_code=err.code)
            return _ev("error", {"entry_id": None, "code": err.code, "message": err.message, "resumable": False}), None
        except Exception as err:
            code = chat_graph.error_code(err)
            trace.set(error_code=code)
            return _ev("error", {"entry_id": None, "code": code, "message": diary_api.MESSAGES.get(code, diary_api.MESSAGES["internal"]),
                                 "resumable": False}), None
        trace.set(entry_id=eid)
        with repo.session(uid) as s:
            c = conversations.get(s, cid)
            if c:
                c["entry_id"], c["drafted"] = eid, n
                conversations.save(s, c)
        if dup:
            return _ev(*diary_api._same(repo, uid, eid)), None
        return None, diary_api._start(repo, uid, eid)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _done(result):
    q = queue.Queue()
    q.put(("result", result))
    q.put(None)
    return q
