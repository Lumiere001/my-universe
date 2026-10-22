"""
app/api/edit.py

우주 고치기(WS16): 해 추가(가까운 기준 축은 AI 제안, 사용자가 바꿈) · 작은 별 옮기기 · 합치기 제안 → 확인 ·
생각 종류 · 가치 고치기 · 사람을 지울 때 그 사람이 나온 생각도 숨기기. 고친 내용은 오답 재료(feedback)로 남는다.
외부 호출은 해 추가의 기준 축 제안 하나뿐이다(이름이 대표 낱말과 안 겹칠 때 Solar 임베딩 한 번, 가명 처리 · 실명 검사 뒤).
"""

import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import Field, field_validator

from app.agents import tools
from app.agents.graph import OTHER_TOPIC
from app.api import consent
from app.api.routes import Id
from app.core import llm, logger
from app.core.ontology import choices
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import In
from app.repository import diary, views
from app.repository import edit
from app.service.rules import link_domain, merge_candidates

router = APIRouter(tags=["고치기"])
BUSY = "정리 중인 기록이 끝난 뒤에 고칠 수 있어요."


class SunIn(In):
    name: str = Field(min_length=1, max_length=20)

    @field_validator("name")
    @classmethod
    def _one_line(cls, v):
        return " ".join(v.split())


class AxisIn(In):
    axis: Literal[tuple(edit.AXES)]


class MoveIn(In):
    sun_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")


class MergeIn(In):
    from_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    into_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")


class ThoughtPatch(In):
    kind: Optional[str] = None
    value: Optional[str] = None   # null · "" = 가치가 드러나지 않음(비움)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v):
        if v is not None and v not in choices("kinds"):
            raise ValueError("kinds 보기 밖 값")
        return v

    @field_validator("value")
    @classmethod
    def _value(cls, v):
        if v and v not in choices("values"):
            raise ValueError("values 보기 밖 값")
        return v or None


def suggest_axis(name, people):
    """(축, 근거). 대표 낱말 · 이름이 겹치면 그 축, 아니면 중심 보정 임베딩이 가장 가까운 축, 둘 다 안 되면 '사용자 영역'.
    고정 문턱은 두지 않는다(PRD §4.2 유사도). 임베딩 실패 · 실명 검사 실패는 '사용자 영역'으로(사용자가 바꿀 수 있음)."""
    hit = link_domain(name)
    if hit:
        return hit, "낱말", None
    sun_vecs, center = tools.sun_vectors()
    if not (sun_vecs and center):
        return edit.USER_AREA, "없음", None
    t0, v, code = time.time(), None, None
    with llm.guard(people) as m:
        try:
            v = tools.embed([name], people)[0]
        except Exception as e:
            code = "real_name_leak" if type(e).__name__ == "RealNameLeak" else "llm_failed"
            logger.log("error", what="suggest_axis", code=code, status=type(e).__name__)
    run = {"ms": (time.time() - t0) * 1000, "calls": m.calls, "est_usd": m.usd, "code": code}
    if v and len(v) == len(center):
        return link_domain(name, v, sun_vecs, center), "임베딩", run
    return edit.USER_AREA, "없음", run


##################################################
# 해
##################################################

@router.get("/suns", summary="해 목록(사용자가 추가한 해 · 이어 둔 기준 축) + 고를 수 있는 기준 축")
def list_suns(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return {"suns": edit.suns(s), "axes": edit.AXES}


@router.post("/suns", summary="해 추가: 이름을 받아 새 해, 가까운 기준 축은 AI 가 제안(PATCH 로 바꿈)")
def add_sun(body: SunIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        consent.check(s)   # 기준 축 제안이 외부(Solar 임베딩)로 나갈 수 있다
        if s.rows("suns", name=body.name, custom=True):
            raise ApiError(409, "already_exists", "같은 이름의 해가 이미 있어요.")
        people = diary.people(s)
    axis, basis, run = suggest_axis(body.name, people)   # 트랜잭션 밖에서 부른다
    with repo.session(user["id"]) as s:
        if run:
            diary.add_run(s, None, "suggest_axis", run["ms"], run["calls"], run["est_usd"], run["code"])
        out = edit.add_sun(s, body.name, axis)
    if not out:
        raise ApiError(409, "already_exists", "같은 이름의 해가 이미 있어요.")
    return {**out, "suggested": {"axis": axis, "basis": basis}}


@router.patch("/suns/{sid}", summary="해의 기준 축 바꾸기(AI 제안을 사용자가 고침 → 오답 재료)")
def set_axis(body: AxisIn, sid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        cur = edit.sun(s, sid)
        if not cur:
            raise ApiError(404, "not_found", "이 해를 찾지 못했어요. 화면을 새로 고쳐 주세요.")
        if cur["name"] in edit.BASE:
            raise ApiError(409, "base_axis", "기본 영역 해는 그 자체가 기준이라 바꿀 수 없어요.")
        return edit.set_axis(s, sid, body.axis)


##################################################
# 작은 별
##################################################

@router.patch("/stars/{sid}", summary="작은 별을 다른 해로 옮기기(그 별의 행성 · 다음 글의 같은 주제도 따라감)")
def move_star(body: MoveIn, sid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        if edit.busy(s):
            raise ApiError(409, "already_running", BUSY)
        out = edit.move_star(s, sid, body.sun_id)
    if not out:
        raise ApiError(404, "not_found", "작은 별이나 해를 찾지 못했어요. 화면을 새로 고쳐 주세요.")
    return out


@router.get("/stars/merge", summary="작은 별 합치기 제안(rules.merge_candidates, 사람이 정함). 거절한 짝은 다시 내지 않음")
def merge_suggestions(user=Depends(get_user), repo=Depends(get_repo)):
    vecs = repo.vectors.get(user["id"])
    with repo.session(user["id"]) as s:
        done = [e["id"] for e in diary.entries(s, status="done")]
        ts = diary.thoughts(s, entry_id=done) if done else []
        stars = {x["id"]: x for x in diary.stars(s)}
        sun = {x["id"]: x["name"] for x in diary.suns(s)}
        no = edit.declined(s)
    by_star = {}
    for t in ts:
        if t["star_id"] in stars and stars[t["star_id"]]["name"] != OTHER_TOPIC:   # 모으는 별은 합치기 후보가 아님
            by_star.setdefault(t["star_id"], []).append(vecs.get(t["id"]))
    name_id = {stars[i]["name"]: i for i in by_star}
    topics = {stars[i]["name"]: sun.get(stars[i]["sun_id"]) for i in by_star}
    mean = lambda vs: [sum(c) / len(vs) for c in zip(*vs)]   # noqa: E731
    star_vecs = {stars[i]["name"]: mean([v for v in vs if v]) for i, vs in by_star.items() if any(vs)}
    center = mean(list(vecs.values())) if len(vecs) >= 2 else None   # 이 사용자 생각 벡터의 평균(search_past 와 같음)
    out = []
    for c in merge_candidates(topics, star_vecs, center):
        a, b = name_id[c["a"]], name_id[c["b"]]
        if edit.pair_id(a, b) not in no:
            out.append({"a": {"id": a, "name": c["a"]}, "b": {"id": b, "name": c["b"]}, "sun": c["sun"], "why": c["why"]})
    return {"candidates": out}


@router.post("/stars/merge", summary="작은 별 합치기(사용자 확인): from 의 생각이 into 로 감, from 은 지움")
def merge(body: MergeIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        if edit.busy(s):
            raise ApiError(409, "already_running", BUSY)
        out = edit.merge_stars(s, body.from_id, body.into_id)
    if not out:
        raise ApiError(404, "not_found", "합칠 작은 별을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
    return out


@router.post("/stars/merge/decline", summary="합치기 제안 거절(이 짝은 다시 제안하지 않음)")
def decline(body: MergeIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        if not edit.decline_merge(s, body.from_id, body.into_id):
            raise ApiError(404, "not_found", "이 작은 별을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
    return {"ok": True}


##################################################
# 생각
##################################################

@router.patch("/thoughts/{tid}", summary="생각 종류 · 가치 고치기(고친 값은 오답 재료로 남음)")
def fix_thought(body: ThoughtPatch, tid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    patch = body.model_dump(exclude_unset=True)
    with repo.session(user["id"]) as s:
        if not edit.fix_thought(s, tid, patch):
            raise ApiError(404, "not_found", "이 생각을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
        t = diary.thoughts(s, id=[tid])[0]
        return views.thought_api(t, diary.states(s), diary.relations(s, to_thought=[tid]))


##################################################
# 사람 지우기 + 그 사람이 나온 생각 숨기기
##################################################

@router.delete("/people/{pid}/with-thoughts", summary="사람 지우기 + 그 사람이 나온 생각 · 관계 · 벡터도 지움(글 본문은 이름만 관계 말로)")
def delete_person_with_thoughts(pid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    uid = user["id"]
    with repo.session(uid) as s:
        if not any(p["id"] == pid for p in diary.people(s)):
            raise ApiError(404, "not_found", "이 사람을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
        if edit.busy(s):
            raise ApiError(409, "already_running", BUSY)
        tids = edit.person_thought_ids(s, pid)
    try:   # 벡터 먼저(못 지우면 아무것도 안 지움, DELETE /me 와 같은 순서)
        repo.vectors.delete(uid, ids=tids)
    except Exception as e:
        logger.log("error", what="hide_thoughts", code="vector_delete_failed", user_id=uid, status=type(e).__name__)
        raise ApiError(503, "vector_delete_failed", "지우지 못했어요. 그대로예요. 잠시 뒤 다시 해 주세요.")
    with repo.session(uid) as s:
        hidden = edit.hide_thoughts(s, tids)
        replaced = diary.delete_person(s, pid)
    return {"ok": True, "replaced": replaced or 0, "hidden": hidden}

