"""FastAPI 의존성: 로그인한 사용자, 저장소(Supabase Postgres + ChromaDB). 시험은 app.dependency_overrides 로 바꾼다."""

from functools import lru_cache

from app.core import config
from app.core.auth import get_user  # noqa: F401  (다시 내보냄)
from app.exceptions import ApiError


@lru_cache(maxsize=1)
def _repo():
    from app.repository import PgRepo
    return PgRepo(config.DATABASE_URL)


def get_repo():
    if not config.DATABASE_URL:
        raise ApiError(503, "db_unconfigured", "지금은 기록을 저장할 수 없어요. 운영자에게 알려 주세요.")
    return _repo()
