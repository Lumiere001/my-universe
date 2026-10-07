"""저장소: 관계형(Supabase Postgres, 사용자별 RLS) + 벡터(ChromaDB). 시험용 메모리 가짜도 같은 모양이다.

    with repo.session(user_id) as s:   # 트랜잭션 하나
        s.rows("entries", order="written_at desc", limit=20)
    repo.vectors.get(user_id)
"""

from contextlib import contextmanager

from app.repository.tables import MemSession, MemStore, pg_session
from app.repository.vectors import ChromaVectors, MemVectors


class PgRepo:
    def __init__(self, database_url, vectors=None):
        self.url, self.vectors = database_url, vectors or ChromaVectors()

    def session(self, uid):
        return pg_session(self.url, uid)


class MemRepo:
    def __init__(self):
        self.store, self.vectors = MemStore(), MemVectors()

    @contextmanager
    def session(self, uid):
        with self.store.lock:   # 메모리 가짜도 트랜잭션처럼 한 번에 한 세션
            yield MemSession(self.store, uid)
