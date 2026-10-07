"""
app/repository/tables.py

표 하나하나에 대한 아주 작은 읽기 · 쓰기. 모든 호출에 그 사용자의 user_id 가 붙는다.
- PgSession: Supabase Postgres. 연결 하나 = 트랜잭션 하나, 시작할 때 `authenticated` 역할 + 그 사용자의 JWT claim 을 걸어
  RLS(user_id = auth.uid())가 백엔드 쿼리에도 걸린다(코드가 user_id 를 빠뜨려도 다른 사람 행은 안 보임).
- MemSession: 시험용 메모리 가짜(같은 모양).
"""

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

IDENTITY = {"runs"}


def _where(uid, eq, lt):
    parts, args = [sql.SQL("user_id = %s")], [uid]
    for k, v in eq.items():
        if isinstance(v, (list, tuple, set)):
            parts.append(sql.SQL("{} = any(%s)").format(sql.Identifier(k)))
            args.append(list(v))
        elif v is None:
            parts.append(sql.SQL("{} is null").format(sql.Identifier(k)))
        else:
            parts.append(sql.SQL("{} = %s").format(sql.Identifier(k)))
            args.append(v)
    for k, v in (lt or {}).items():
        parts.append(sql.SQL("{} < %s").format(sql.Identifier(k)))
        args.append(v)
    return sql.SQL(" and ").join(parts), args


def _adapt(row):
    return {k: Jsonb(v) if isinstance(v, dict) else v for k, v in row.items()}   # dict → jsonb, list → text[]


class PgSession:
    def __init__(self, conn, uid):
        self.conn, self.uid = conn, str(uid)

    def insert(self, table, row):
        row = _adapt({**row, "user_id": self.uid})
        q = sql.SQL("insert into {} ({}) values ({})").format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, row)), sql.SQL(", ").join(sql.Placeholder() * len(row)))
        self.conn.execute(q, list(row.values()))

    def upsert(self, table, row, key=("id",)):
        row = _adapt({**row, "user_id": self.uid})
        rest = [k for k in row if k not in key and k != "user_id"]
        q = sql.SQL("insert into {} ({}) values ({}) on conflict ({}) do update set {}").format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, row)), sql.SQL(", ").join(sql.Placeholder() * len(row)),
            sql.SQL(", ").join(map(sql.Identifier, key)),
            sql.SQL(", ").join(sql.SQL("{0} = excluded.{0}").format(sql.Identifier(k)) for k in rest))
        self.conn.execute(q, list(row.values()))

    def rows(self, table, order=None, limit=None, lt=None, **eq):
        w, args = _where(self.uid, eq, lt)
        q = sql.SQL("select * from {} where ").format(sql.Identifier(table)) + w
        if order:
            col, *desc = order.split()
            q += sql.SQL(" order by {} {}").format(sql.Identifier(col), sql.SQL("desc" if desc else "asc"))
        if limit:
            q += sql.SQL(" limit %s")
            args.append(int(limit))
        return self.conn.execute(q, args).fetchall()

    def update(self, table, values, **eq):
        values = _adapt(values)
        w, args = _where(self.uid, eq, None)
        q = sql.SQL("update {} set {} where ").format(
            sql.Identifier(table), sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(k)) for k in values)) + w
        return self.conn.execute(q, list(values.values()) + args).rowcount

    def delete(self, table, **eq):
        w, args = _where(self.uid, eq, None)
        return self.conn.execute(sql.SQL("delete from {} where ").format(sql.Identifier(table)) + w, args).rowcount


@contextmanager
def pg_session(database_url, uid):
    """그 사용자로 RLS 를 건 트랜잭션 하나. 끝나면 커밋, 예외면 되돌림."""
    # ponytail: 요청마다 연결을 새로 연다(로컬 수 ms). 동시 사용자가 늘면 psycopg_pool 로 바꾼다.
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        conn.execute("set local role authenticated")
        conn.execute("select set_config('request.jwt.claims', %s, true)",
                     [json.dumps({"sub": str(uid), "role": "authenticated"})])
        yield PgSession(conn, uid)


class MemStore:
    """시험용: 표 이름 → 행 목록. 여러 사용자가 한 저장소를 나눠 쓴다(사용자 분리 시험용)."""

    def __init__(self):
        self.tables, self.lock, self.seq = {}, threading.RLock(), 0


class MemSession:
    def __init__(self, store, uid):
        self.store, self.uid = store, str(uid)

    def _t(self, table):
        return self.store.tables.setdefault(table, [])

    def _match(self, r, eq, lt=None):
        if r.get("user_id") != self.uid:
            return False
        for k, v in eq.items():
            if isinstance(v, (list, tuple, set)):
                if r.get(k) not in v:
                    return False
            elif r.get(k) != v:
                return False
        return all(r.get(k) is not None and r[k] < v for k, v in (lt or {}).items())

    def insert(self, table, row):
        with self.store.lock:
            row = {"created_at": datetime.now(timezone.utc), **row, "user_id": self.uid}
            if table in IDENTITY:
                self.store.seq += 1
                row["id"] = self.store.seq
            if "id" in row and any(r.get("id") == row["id"] for r in self._t(table) if table not in IDENTITY):
                raise ValueError(f"duplicate key {table}")
            self._t(table).append(row)

    def upsert(self, table, row, key=("id",)):
        with self.store.lock:
            row = {**row, "user_id": self.uid}
            for r in self._t(table):
                if all(r.get(k) == row[k] for k in key) and r.get("user_id") == self.uid:
                    r.update(row)
                    return
            self.insert(table, row)

    def rows(self, table, order=None, limit=None, lt=None, **eq):
        with self.store.lock:
            out = [dict(r) for r in self._t(table) if self._match(r, eq, lt)]
        if order:
            col, *desc = order.split()
            out.sort(key=lambda r: r.get(col), reverse=bool(desc))
        return out[:limit] if limit else out

    def update(self, table, values, **eq):
        with self.store.lock:
            hit = [r for r in self._t(table) if self._match(r, eq)]
            for r in hit:
                r.update(values)
            return len(hit)

    def delete(self, table, **eq):
        with self.store.lock:
            keep = [r for r in self._t(table) if not self._match(r, eq)]
            n = len(self._t(table)) - len(keep)
            self.store.tables[table] = keep
            return n
