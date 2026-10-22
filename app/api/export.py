"""
app/api/export.py

JSON 내려받기(PRD §5.6 · §7 474, 1차 필수 요건 '결과 JSON 내려받기'): 기록 하나 · 전체. 모양은 docs/api-v8.md §2.1.
"""

from fastapi import APIRouter, Depends

from app.api.routes import Id
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.repository import views

router = APIRouter(tags=["내려받기"])


@router.get("/export", summary="전체 기록 JSON(먼저 쓴 것부터)")
def export_all(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.export(s)


@router.get("/export/{eid}", summary="기록 하나 JSON")
def export_one(eid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        out = views.export(s, eid)
    if out is None:
        raise ApiError(404, "not_found", "이 기록을 찾지 못했어요. 지워졌을 수 있어요.")
    return out
