"""
app/service/rules/drift.py

되고 싶은 모습과 멀어짐 · 가까워지지 못함(PRD v9 Q4 · Q5-2, 규칙만 · LLM 없음).
- 멀어짐: 내 안의 걸림(4번)이 일기에 되풀이해 나온다 — 최근 WINDOW 일 안에 걸림 근거(hit)가 NEED 번 이상.
  hit 는 graph 가 만든다(걸림 벡터와 비슷한 생각 → Solar 로 같은 이야기인지 확인, 또는 이미 어긋났던 다짐이 또 어긋남).
- 가까워지지 못함: 일기는 계속 쓰는데 장면에 닿은 날이 한동안 없다 — 마지막 닿은 날(없으면 말한 날) 뒤로 일기 ENTRIES 편 · DAYS 일.
- 한 번 건네면 COOL 일 쉰다. '그때 해 볼 것'이 없으면 건넬 말이 없어 쉰다(Q3-2).
ponytail: 문턱값은 고정(짐작). 되돌림 · '이 말은 그만' 비율이 쌓이면 개인 맞춤 Ops 다이얼로.
"""

from datetime import date

WINDOW, NEED = 14, 2
ENTRIES, DAYS = 5, 7
COOL = 7
KEEP = 10   # 남겨 둘 걸림 근거 수(오래된 것부터 버림)


def _d(x):
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def merge_hits(hits, hit, entry_id):
    """이번 글의 근거로 바꿔 넣는다(같은 글을 다시 정리해도 한 번만)."""
    out = [h for h in hits or [] if h.get("entry_id") != entry_id] + ([hit] if hit else [])
    return out[-KEEP:]


def kind(hits, today, since, entries_after, said=None):
    """→ "멀어짐" | "가까워지지 못함" | None. since: 마지막 닿은 날(없으면 되고 싶은 모습을 말한 날).
    entries_after: since 뒤로 쓴 일기 수. said: 마지막으로 '어디로 가자'를 건넨 날."""
    today = _d(today)
    if said and (today - _d(said)).days < COOL:
        return None
    if sum((today - _d(h["day"])).days <= WINDOW for h in hits or []) >= NEED:
        return "멀어짐"
    if since and entries_after >= ENTRIES and (today - _d(since)).days >= DAYS:
        return "가까워지지 못함"
    return None


if __name__ == "__main__":
    h = [{"day": "2026-10-20", "entry_id": "e1"}, {"day": "2026-10-28", "entry_id": "e2"}]
    assert kind(h, "2026-10-30", None, 0) == "멀어짐"
    assert kind(h[:1], "2026-10-30", None, 0) is None
    assert kind(h, "2026-10-30", None, 0, said="2026-10-27") is None                 # 쉬는 중
    assert kind([], "2026-10-30", "2026-10-20", 5) == "가까워지지 못함"
    assert kind([], "2026-10-30", "2026-10-26", 5) is None                           # 아직 7일 안
    assert merge_hits(h, {"day": "2026-10-30", "entry_id": "e2"}, "e2")[-1]["day"] == "2026-10-30"
    print("ok")
