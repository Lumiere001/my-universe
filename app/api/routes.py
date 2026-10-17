"""
app/api/routes.py

우주 · 온톨로지 · 피드백 · 사람 · 되고 싶은 모습 · 나 · 설정 · 계정 지우기 · 운영(/health · /stats).
"""

import unicodedata
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from app.core import auth, config, logger
from app.core.ontology import load
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import AnswerIn, AspirationIn, DeclineIn, FeedbackIn, PersonIn, PersonPatch, SettingsPatch
from app.repository import diary, views
from app.service.rules import press

router = APIRouter()
Id = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]   # id 모양만(제어 문자 · 다른 글자는 422)


@router.get("/health", tags=["운영"])
def health():
    return {"status": "ok", "version": config.VERSION}


@router.get("/ontology", tags=["운영"], summary="app/core/ontology/v8.json 그대로")
def ontology():
    return load()


@router.get("/stats", tags=["운영"], summary="원문 없는 운영 숫자(본인 것만)")
def stats(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.stats(s)


@router.get("/universe", tags=["우주"])
def universe(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.universe(s)


##################################################
# 피드백 · 상태 버튼
##################################################

TODAY_FLAGS = {"오늘은 살살": "gentle_today", "오늘은 위로만": "comfort_only_today"}
BLANK = "\u115f\u1160\u3164\uffa0\u2800\ufffc"   # 한글 채움 문자 · 점자 빈칸 · 받아쓰기 자리표: 글자지만 보이지 않음


def _visible(text):
    """보이는 글자가 하나라도 있나. 띄어쓰기 · 제어 · 폭 없는 글자 · 채움 문자만이면 빈 글(화면 OneLine 과 같은 규칙)."""
    return any(not c.isspace() and unicodedata.category(c) not in ("Cc", "Cf") and c not in BLANK for c in text or "")


@router.post("/feedback", tags=["피드백"])
def feedback(body: FeedbackIn, user=Depends(get_user), repo=Depends(get_repo)):
    if body.value == "불편한 점 한 줄" and not _visible(body.text):   # 그냥 받으면 운영 화면 '남긴 말'이 빈 칸으로 남는다
        raise ApiError(422, "invalid_input", "불편한 점을 한 줄 적어 주세요.")
    changed = removed = None
    with repo.session(user["id"]) as s:
        if body.value in ("맞아요", "아니에요", "지켰어요", "그만둘래요"):
            if not body.target_id:
                raise ApiError(422, "invalid_input", "어느 것에 대한 버튼인지 알려 주세요.")
            old = diary.states(s)
            rels = diary.relations(s) if body.value in ("맞아요", "아니에요") else []
            try:
                new, new_rels = press(old, rels, body.target_id, body.value, diary.today())
            except ValueError:
                raise ApiError(409, "invalid_target", "이 버튼을 누를 수 있는 대상이 아니에요.")
            after = {r["id"]: r for r in new_rels}
            for r in rels:
                if r["id"] not in after:
                    s.delete("relations", id=r["id"])
                    removed = {k: r[k] for k in ("type", "from", "to")}   # 오답 재료(피드백 암호문에만)
                elif after[r["id"]] != r:
                    diary.save_relation(s, after[r["id"]])
            diary.save_states(s, new, old)
            changed = new.get(body.target_id)
        elif body.value in TODAY_FLAGS:
            diary.save_profile(s, settings={TODAY_FLAGS[body.value]: diary.today()})
        elif body.value == "날씨 건너뜀":
            diary.save_profile(s, settings={"weather_ask": False}, onboarding={"weather_asked": True})
        diary.add_feedback(s, body.target, body.target_id, body.value,
                           body.text if body.value == "불편한 점 한 줄" else None, relation=removed)
    return {"ok": True, "state": changed and {"type": changed["kind"], "status": changed.get("state"),
                                              "mistake": "실수" in changed.get("marks", [])}}


##################################################
# 사람
##################################################

def _nicks(s):
    return [n.strip() for n in (s or "").split(",") if n.strip()]


@router.get("/people", tags=["사람"])
def list_people(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return {"people": views.people_list(s)}


@router.post("/people", tags=["사람"])
def add_person(body: PersonIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.person_api(diary.add_person(s, body.name, _nicks(body.nickname), body.relation))


@router.patch("/people/{pid}", tags=["사람"])
def update_person(body: PersonPatch, pid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        p = diary.update_person(s, pid, body.name, None if body.nickname is None else _nicks(body.nickname), body.relation)
    if not p:
        raise ApiError(404, "not_found", "사람을 찾지 못했어요.")
    return views.person_api(p)


@router.delete("/people/{pid}", tags=["사람"], summary="지우기 = 저장된 글 속 이름을 관계 말로 바꾸고 문장은 남김")
def delete_person(pid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        n = diary.delete_person(s, pid)
    if n is None:
        raise ApiError(404, "not_found", "사람을 찾지 못했어요.")
    return {"ok": True, "replaced": n}


@router.post("/people/questions/{qid}", tags=["사람"])
def answer_question(body: AnswerIn, qid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        q = next(iter(diary.questions(s, id=qid)), None)
        if not q:
            raise ApiError(404, "not_found", "질문을 찾지 못했어요.")
        people = diary.people(s)
        if body.answer in ("다른 사람", "사람 이름"):
            diary.add_person(s, q["name"])
        elif body.answer == "같은 사람" and q["reason"] == "별명":
            # 이미 있는 이름과 겹치는 사람(find_new_names 의 별명 규칙과 같음)의 별명으로 더한다
            base = q["name"][:-1] if q["name"].endswith("이") else q["name"]
            p = next((p for p in people if any(base in t or t in q["name"] for t in [p["name"], *p["nicknames"]])), None)
            if p:
                diary.update_person(s, p["id"], nicknames=[*p["nicknames"], q["name"]])
        s.update("people_questions", {"answer": body.answer}, id=qid)
    return {"ok": True}


##################################################
# 되고 싶은 모습
##################################################

@router.get("/aspiration", tags=["되고 싶은 모습"])
def get_aspiration(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.aspiration_state(s)


@router.post("/aspiration", tags=["되고 싶은 모습"], summary="새 판(이력 보존)")
def save_aspiration(body: AspirationIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        diary.add_aspiration(s, body.now, body.want, body.obstacle, body.if_then, body.values)
        diary.save_profile(s, onboarding={"aspiration": "set", "aspiration_step": None})
        return views.aspiration_api(diary.aspirations(s)[-1])


@router.post("/aspiration/decline", tags=["되고 싶은 모습"], summary="skip = 이번엔 넘어가기, stop = 그만 묻기")
def decline_aspiration(body: DeclineIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        diary.save_profile(s, onboarding={"aspiration": body.mode, "aspiration_step": None})
    return {"ok": True}


##################################################
# 나 · 설정
##################################################

@router.get("/me", tags=["나"])
def me(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        st, ob = diary.profile(s)
        n = len(s.rows("entries", status="done"))
    return {"user": user, "settings": st,
            "onboarding": {"entries": n, "aspiration": ob["aspiration"], "weather_asked": ob["weather_asked"]}}


@router.delete("/me", tags=["나"], status_code=204, summary="계정과 모든 기록 지우기(되돌릴 수 없음)")
def delete_me(user=Depends(get_user), repo=Depends(get_repo)):
    """순서: 벡터(Chroma) → DB 의 모든 행 → auth 계정(관리 API, 남은 행은 FK cascade). 벡터를 못 지우면 아무것도 안 지우고 오류."""
    uid = user["id"]
    if not (config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY):
        raise ApiError(503, "account_delete_unconfigured", "계정 지우기 설정이 아직 없어요. 운영자에게 알려 주세요.")
    with repo.session(uid) as s:
        if any(diary.is_locked(e) for e in s.rows("entries")):
            raise ApiError(409, "already_running", "정리 중인 기록이 끝난 뒤에 지울 수 있어요.")
    try:
        repo.vectors.delete(uid)
    except Exception as e:
        logger.log("error", what="delete_me", code="vector_delete_failed", user_id=uid, status=type(e).__name__)
        raise ApiError(503, "vector_delete_failed", "기록을 지우지 못했어요. 계정은 그대로예요. 잠시 뒤 다시 해 주세요.")
    with repo.session(uid) as s:
        diary.wipe(s)
    auth.delete_account(uid)
    logger.log("step", what="delete_me", user_id=uid, ok=True)
    return Response(status_code=204)


@router.patch("/settings", tags=["나"])
def patch_settings(body: SettingsPatch, user=Depends(get_user), repo=Depends(get_repo)):
    patch = body.model_dump(exclude_unset=True)
    with repo.session(user["id"]) as s:
        cur, _ = diary.profile(s)
        if patch.get("tone") == "팩폭" and not patch.get("fact_bomb_ack", cur["fact_bomb_ack"]):
            raise ApiError(409, "fact_bomb_ack_required", "팩폭은 경고를 확인한 뒤에 고를 수 있어요.")
        if patch.get("fact_bomb_ack") is False and cur["tone"] == "팩폭" and "tone" not in patch:
            patch["tone"] = "다정하게"   # 경고 확인을 거두면 팩폭도 거둔다
        st, _ = diary.save_profile(s, settings=patch)
    return st
