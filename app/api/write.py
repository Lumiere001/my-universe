"""
app/api/write.py

쓰기 화면 작은 묶음(WS13): 쓰기 화면 위 별지기 말풍선(GET /diary/prompt) · 글이 다루는 날 고치기(PATCH /diary/{eid}/day).
LLM 을 부르지 않는다. main.py 에서 diary.router 보다 먼저 등록한다(/diary/prompt 가 /diary/{eid} 에 걸리지 않게).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import DayIn
from app.repository import diary, views
from app.service.voice import FIRST_QUESTIONS

router = APIRouter(tags=["일기"])
Id = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
STOPPED = ("skip", "stop", "set")   # 되고 싶은 모습: 넘어감 · 그만 묻기 · 이미 적음 → 지난 질문을 다시 꺼내지 않음


def prompt(s):
    """첫 만남 질문 또는 지난 글의 '다음에 써 볼 질문' + 다짐 안부(기한 지났거나 지난 글에서 나온 열린 다짐 하나).
    날씨 질문은 건너뛰었으면(weather_ask: false) 꺼내지 않는다. 무거운 날 · 오늘은 위로만이면 다짐 안부를 묻지 않는다."""
    st, ob = diary.profile(s)
    last = diary.entries(s, limit=1, status="done")
    if not last:
        return {"kind": "first", "text": FIRST_QUESTIONS[0], "vow": None}
    eid = last[0]["id"]
    m = s.rows("messages", entry_id=eid)
    msg = diary.message(s, m[0]) if m else {}
    raw = m[0]["next_kind"] if m else ""
    kind, text = views.NEXT_KIND.get(raw, "free"), (msg.get("next_question") or "").strip()
    if not text or (kind == "weather" and not st["weather_ask"]) or (kind == "aspiration" and ob["aspiration"] in STOPPED):
        kind, text = "none", ""
    vow = None
    if msg.get("mode") != "comfort" and st.get("comfort_only_today") != diary.today() and raw != "commitment":
        today = diary.today()
        open_ = {k: v for k, v in diary.states(s).items() if v["kind"] == "다짐" and v["state"] == "열림"}
        ts = diary.thoughts(s, id=list(open_)) if open_ else []
        due = [t for t in ts if open_[t["id"]].get("due") and open_[t["id"]]["due"] < today]
        t = (due or [t for t in ts if t["entry_id"] == eid] or [None])[0]
        if t and t.get("text"):
            vow = {"thought_id": t["id"], "text": t["text"], "overdue": t in due}
    return {"kind": kind, "text": text, "vow": vow}


@router.get("/diary/prompt", summary="쓰기 화면 위 별지기 말풍선(첫 만남 질문 · 지난 질문 · 다짐 안부)")
def get_prompt(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return prompt(s)


@router.patch("/diary/{eid}/day", summary="글이 다루는 날 고치기(확실, '날짜 확인 필요' 거둠) → EntryResult")
def set_day(body: DayIn, eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        row = s.rows("entries", id=eid)
        if not row:
            raise ApiError(404, "not_found", "기록을 찾지 못했어요.")
        if diary.is_locked(row[0]):
            raise ApiError(409, "already_running", "정리가 끝난 뒤에 고칠 수 있어요.")
        diary.set_day(s, eid, body.day)
        return views.entry_result(s, eid)
