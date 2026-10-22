"""
app/api/people_thoughts.py

사람 하나와 얽힌 생각을 쓴 때 순서로(PRD §7 우주의 기호 '사람'). 우주 · 사람 화면에서 사람을 고르면 부른다.
"""

from fastapi import APIRouter, Depends

from app.api.routes import Id
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.repository import views

router = APIRouter()


@router.get("/people/{pid}/thoughts", tags=["사람"], summary="그 사람과 얽힌 생각(끝난 기록만, 먼저 쓴 것부터)")
def person_thoughts(pid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        out = views.person_thoughts(s, pid)
    if out is None:
        raise ApiError(404, "not_found", "이 사람을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
    return out
