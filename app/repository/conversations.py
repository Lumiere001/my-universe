"""
app/repository/conversations.py

대화(WS19) 행 읽기 · 쓰기. 턴 · 지금까지 정리 · 초안은 enc 에만(aad 'conversations:<id>').
평문 칸: entry_id(확인 전 초안 기록) · turn_count(사용자 턴 수) · 시각.
"""

from app.repository import diary


def _row(s, r):
    return {"id": r["id"], "entry_id": r["entry_id"], "turn_count": r["turn_count"], "created_at": r["created_at"],
            "updated_at": r["updated_at"], **diary.unseal(s, "conversations", r["id"], r["enc"])}


def create(s, data):
    cid = diary.new_id("c")
    t = diary.now()
    s.insert("conversations", {"id": cid, "entry_id": None, "turn_count": 0, "created_at": t, "updated_at": t,
                               "enc": diary.seal(s, "conversations", cid, data)})
    return get(s, cid)


def get(s, cid):
    r = s.rows("conversations", id=cid)
    return _row(s, r[0]) if r else None


def recent(s, limit=5):
    return [_row(s, r) for r in s.rows("conversations", order="updated_at desc", limit=limit)]


DATA = ("turns", "summary", "summary_at", "from_entry", "sources", "drafted", "crisis")


def save(s, c):
    """c: get() 이 준 모양(고친 것). 원문 칸(DATA)은 enc 로, 나머지는 평문 칸으로."""
    s.update("conversations", {"entry_id": c.get("entry_id"), "updated_at": diary.now(),
                               "turn_count": sum(t["role"] == "user" for t in c.get("turns", [])),
                               "enc": diary.seal(s, "conversations", c["id"], {k: c[k] for k in DATA if k in c})}, id=c["id"])


def delete(s, **eq):
    return s.delete("conversations", **eq)
