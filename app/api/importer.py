"""
app/api/importer.py

인스타그램 ZIP 가져오기 미리 보기(WS17). 화면이 ZIP 에서 꺼낸 게시물을 받아 가져올 글 목록 · 어림값을 돌려준다.
아무것도 저장하지 않고 밖으로 보내지 않는다(그래서 동의 확인은 /diary/stream 이 한다). 이미 가져와 정리가 끝난 글은 imported.
상한 없음(결정 12): IMPORT_MAX_POSTS 가 비면 무제한. 값이 있으면 화면이 고를 수 있는 편수를 그만큼으로 묶는다
(서버 쪽 지킴은 DAILY_ENTRY_LIMIT · MONTHLY_COST_CAP_USD — /diary/stream 이 그대로 건다).
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import ConfigDict, Field

from app.core import config
from app.deps import get_repo, get_user
from app.models import In
from app.repository import diary
from app.service import importer

router = APIRouter(tags=["가져오기"])
CAPTION_MAX = 20000   # 입력 검사(상한 아님): 인스타 캡션 2,200자가 깨진 한글(글자당 3자)이어도 들어감
# 깨진 한글은 앞뒤 공백을 떼면 안 된다: '날'(EB 82 A0)의 A0 · 85 같은 바이트가 latin-1 공백 글자라 strip 이 지움 → 복원 실패
RAW = ConfigDict(str_strip_whitespace=False)


class Media(In):
    model_config = RAW
    title: str = Field(default="", max_length=CAPTION_MAX)
    creation_timestamp: Optional[int] = None


class Post(In):
    model_config = RAW
    title: str = Field(default="", max_length=CAPTION_MAX)
    creation_timestamp: Optional[int] = None
    media: list[Media] = Field(default_factory=list, max_length=1)   # 첫 사진의 캡션 · 시각만 씀


class InstagramIn(In):
    posts: list[Post]


@router.post("/import/instagram/preview", summary="인스타그램 게시물 → 가져올 글 목록(저장 안 함)")
def preview(body: InstagramIn, user=Depends(get_user), repo=Depends(get_repo)):
    recs = importer.records([p.model_dump() for p in body.posts])
    with repo.session(user["id"]) as s:
        refs = {diary.ref_hash(s, importer.SOURCE, r["ref"]): r for r in recs}
        done = {x["source_ref"] for x in s.rows("entries", source_ref=list(refs), status="done")} if refs else set()
    for h, r in refs.items():
        r["imported"] = h in done
    return {"posts": recs, "max_posts": config.IMPORT_MAX_POSTS or None,
            "est_seconds_per_post": importer.EST_SECONDS_PER_POST, "est_usd_per_post": importer.EST_USD_PER_POST}
