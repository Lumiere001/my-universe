"""
세부 주제(작은 별)와 삶의 영역(해).

주제는 그 사용자의 기존 작은 별 이름을 다시 쓰고, 해 이름은 주제로 쓰지 않는다(topic_rules).
해는 혼합형: 일기에 나온 영역 + 사용자가 추가한 해, 글 없는 기준 축은 숨김(domain_rules).
임베딩 벡터는 부르는 쪽이 넘긴다(여기서는 네트워크를 쓰지 않는다).
"""

import math
import re

from app.core.ontology import load
from app.service.rules.normalize import key

O = load()
BASE = [d["name"] for d in O["domains"]]   # 기준 축 9개
VALUES = {key(v["name"]) for v in O["values"]}   # 가치 10개(Schwartz): 생각의 가치 칸이지 주제가 아니다


def cos(a, b, center=None):
    """코사인. center 를 주면 중심 보정(평균 방향을 빼고) 비교한다."""
    if center:
        a = [x - m for x, m in zip(a, center)]
        b = [y - m for y, m in zip(b, center)]
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _sun_names(suns):
    return BASE + [s["name"] if isinstance(s, dict) else s for s in suns or ()]


def topic_input(topics):
    """기록 Agent 입력에 넣을 기존 작은 별 안내 두 줄. topics: 이름 목록 또는 {이름: 해}."""
    names = list(dict.fromkeys(topics or []))
    return f"{O['topic_rules'][3]}\n기존 작은 별: {', '.join(names) if names else '없음'}"


MANY = re.compile(r"\s*[,，、]\s*")   # 가운뎃점은 나누지 않는다: '영성·신앙' · '학업·동아리'처럼 이름 하나 안에 쓰임


def one_topic(topic, text=""):
    """주제 칸에 이름을 쉼표로 여럿 쓴 값(예: '독서노트 습관, 진로 선택, 혼자 있는 시간') → 이름 하나.
    생각 · 인용에 낱말이 가장 많이 나오는 이름, 같으면 앞 이름. 여럿을 그대로 두면 없는 작은 별이 생기고,
    앞 이름만 쓰면 기존 별에 잘못 붙는다(품질 3판 측정, 2판 4/5 '내 시간을 지키고 싶다' → 앞 이름 '독서노트 습관')."""
    names = [n for n in MANY.split(topic or "") if n.strip()]
    if len(names) < 2:
        return topic
    t = key(text)
    return max(names, key=lambda n: sum(len(key(w)) >= 2 and key(w) in t for w in n.split()))


def match_topic(topic, topics=None, suns=(), aliases=None):
    """(주제, 문제 또는 None). 기존 이름(띄어쓰기 무시) · 사람이 정한 비슷한 말(aliases {말: 이름})이면 기존 이름으로.
    해 이름이면 그 해의 다른 작은 별이 하나뿐일 때만 그것으로 고치고, 아니면 그대로 두고 "해 이름" 문제를 돌려준다.
    빈 주제는 ("", "빈 주제"), 가치 이름(배려 · 성취 …)은 그대로 두고 "가치 이름" 문제를 돌려준다(고칠 근거가 없음)."""
    topics = topics or {}
    t = " ".join((topic or "").split())
    if not key(t):
        return "", "빈 주제"
    by_key = {key(n): n for n in topics}
    t = by_key.get(key(t)) or {key(a): n for a, n in (aliases or {}).items()}.get(key(t)) or t
    sun_keys = {key(s): s for s in _sun_names(suns)}
    if key(t) not in sun_keys:
        return t, "가치 이름" if key(t) in VALUES else None
    sun = sun_keys[key(t)]
    others = [n for n, s in topics.items() if s == sun and key(n) not in sun_keys]
    return (others[0], None) if len(others) == 1 else (t, "해 이름")


def link_domain(topic, vec=None, sun_vecs=None, center=None, suns=()):
    """세부 주제 → 해 이름. 대표 낱말과 이름이 겹치면 그 해, 아니면 중심 보정 임베딩이 가장 가까운 해, 둘 다 안 되면 None.
    suns: 사용자가 추가한 해 [{name, keywords}] 또는 이름. sun_vecs: {해: [대표 낱말 벡터 …]}."""
    words = [(d["name"], [d["name"], *d["keywords"]]) for d in O["domains"]]
    words += [(s["name"], [s["name"], *s.get("keywords", [])]) if isinstance(s, dict) else (s, [s]) for s in suns or ()]
    k = key(topic)
    if not k:
        return None
    for name, ws in words:
        if any(key(w) == k for w in ws):
            return name
    for name, ws in words:
        if any(len(key(w)) >= 2 and key(w) in k for w in ws):
            return name
    if vec and sun_vecs:
        return max(sun_vecs, key=lambda s: max(cos(vec, v, center) for v in sun_vecs[s]))
    return None


def sun_list(thoughts, suns=()):
    """{"shown": 띄울 해, "hidden": 글 없는 기준 축(질문 재료)}. 9개 밖 영역이 생각에 나오면 해로 띄운다."""
    used = {t.get("domain") for t in thoughts if t.get("domain")}
    user = [s["name"] if isinstance(s, dict) else s for s in suns or ()]
    shown = [d for d in BASE if d in used] + [s for s in user if s not in BASE]
    shown += sorted(used - set(shown))
    return {"shown": shown, "hidden": [d for d in BASE if d not in shown]}


def merge_candidates(topics, vecs=None, center=None):
    """작은 별 합치기 후보(사람이 정함). 띄어쓰기만 다른 이름, 그리고 같은 해 안에서 서로 가장 가까운 두 이름.
    topics: {이름: 해}, vecs: {이름: 벡터}. 숫자 문턱 없이 '서로 가장 가까움'만 본다."""
    out, seen = [], set()
    names = list(topics)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if key(a) == key(b):
                out.append({"a": a, "b": b, "sun": topics[a], "why": "띄어쓰기만 다름", "sim": None})
                seen.add(frozenset((a, b)))
    vecs = vecs or {}
    near = {}
    for a in names:
        mates = [b for b in names if b != a and topics[b] == topics[a] and a in vecs and b in vecs]
        if mates:
            near[a] = max(mates, key=lambda b: cos(vecs[a], vecs[b], center))
    pairs = []
    for a, b in near.items():
        if near.get(b) == a and a < b and frozenset((a, b)) not in seen:
            pairs.append({"a": a, "b": b, "sun": topics[a], "why": "같은 해에서 서로 가장 가까움",
                          "sim": round(cos(vecs[a], vecs[b], center), 4)})
    return out + sorted(pairs, key=lambda p: -p["sim"])
