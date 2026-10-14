"""
지난 생각 고르기(past_selection). 고정 문턱 · 가산점 없이 순위로 고른다.

1. 같은 세부 주제의 지난 생각은 모두 후보로 둔다.
2. 나머지는 중심 보정 유사도 순으로 줄 세워 가장 크게 떨어지는 지점에서 자른다.
3. 주제 순위(같은 주제 먼저, 그 안은 유사도 순)와 유사도 순위를 순위 합으로 합쳐 관련 높은 것을 앞에 둔다.
4. 개수 상한은 운영 한도(limits.past_thoughts_max)로만.
5. 오늘 생각마다 다른 주제에서 가장 가까운 지난 생각 하나는 낙폭 자르기 · 한도와 상관없이 남긴다(품질 4b).
"""

from app.core.ontology import load
from app.service.rules.topics import cos

LIMIT = load()["limits"]["past_thoughts_max"]
# ponytail: 오늘 생각 하나에 다른 주제 자리 1개(상수). 작은 별이 잘게 나뉘면(4판 25개) '같은 주제 먼저 + 낙폭 자르기'만으로는
# 다른 별에 있는 옛 생각을 못 받는다 — 4판 9/20 은 '마음이 무겁다'끼리(7/30, 0.91) 뒤 낙폭에서 잘려 3/14('안정이 제일',
# 9/20 의 변화 서술에 다른 주제 중 가장 가까움)를 놓쳐 대표 바뀜이 사라졌다. 늘리면 관측 입력(비용 · 거짓 연결 후보)이 커진다.
NEAREST_OTHER_TOPIC = 1


def cut_at_drop(sims):
    """내림차순 유사도 목록에서 가장 크게 떨어지는 곳 앞까지의 개수. 떨어짐이 없으면 전부."""
    if len(sims) < 2:
        return len(sims)
    gaps = [sims[i] - sims[i + 1] for i in range(len(sims) - 1)]
    i = max(range(len(gaps)), key=lambda j: gaps[j])
    return i + 1 if gaps[i] > 0 else len(sims)


def pick_past(today, past, center=None, limit=LIMIT):
    """today: 오늘 생각들 [{id, record_id, topic, emb}], past: 지난 생각들 [{id, record_id, topic, day, emb, …}].
    돌려줌: 고른 지난 생각(관련 높은 순)에 sim · same_topic · rank 를 붙인 사본."""
    vecs = [t["emb"] for t in today if t.get("emb")]
    mine = {t["record_id"] for t in today}
    past = [p for p in past if p["record_id"] not in mine and p.get("emb")]
    if not vecs or not past:
        return []
    topics = {t.get("topic") for t in today}
    sim = {p["id"]: max(cos(v, p["emb"], center) for v in vecs) for p in past}
    by_sim = sorted(past, key=lambda p: (-sim[p["id"]], p["id"]))
    same = [p for p in by_sim if p.get("topic") in topics]
    rest = [p for p in by_sim if p.get("topic") not in topics]
    near = {q["id"] for t in today if t.get("emb") for q in
            sorted(rest, key=lambda p: (-cos(t["emb"], p["emb"], center), p["id"]))[:NEAREST_OTHER_TOPIC]}
    cut = {p["id"] for p in rest[:cut_at_drop([sim[p["id"]] for p in rest])]}
    rest = [p for p in rest if p["id"] in cut | near]
    by_topic = same + rest                                       # 주제 순위
    keep = {p["id"] for p in by_topic}
    by_sim = [p for p in by_sim if p["id"] in keep]              # 유사도 순위
    r_topic = {p["id"]: i for i, p in enumerate(by_topic, 1)}
    r_sim = {p["id"]: i for i, p in enumerate(by_sim, 1)}
    fused = sorted(by_topic, key=lambda p: (r_topic[p["id"]] + r_sim[p["id"]], r_topic[p["id"]]))   # 순위 합
    keep = near | {p["id"] for p in [p for p in fused if p["id"] not in near][:max(0, limit - len(near))]}
    fused = [p for p in fused if p["id"] in keep][:limit]   # 가까운 다른 주제 자리를 먼저 잡고 나머지는 순위 합 순으로
    return [{**p, "sim": round(sim[p["id"]], 4), "same_topic": p.get("topic") in topics, "rank": i}
            for i, p in enumerate(fused, 1)]
