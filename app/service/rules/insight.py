"""
나에 대해 알게 된 것(insight). 기록이 쌓였을 때 시스템이 나에 대해 무엇을 알게 됐는지 해 → 작은 별 → 생각 순으로 묶는다
(강의 보충 PE-07 RAPTOR 의 계층 묶음을 AI 요약 없이 코드로, PE-07 지식 충돌: 시점이 다른 두 생각은 모순이 아니라 변화).
사람을 판정하지 않는다(tone_rules): '당신은 ~한 사람'이 아니라 날짜와 원문 인용만 보여 준다.
"""

from collections import Counter

from app.service.rules.topics import sun_list


def _end(t):
    return {"day": t["day"], "quote": t.get("quote", ""), "record_id": t["record_id"], "thought_id": t["id"]}


def _no_shortcuts(rs):
    """바뀜이 A → B → C 로 이어지면 A → C 는 빼고 보인다(같은 변화가 세 장으로 겹쳐 보였다, 가상 인물 A 2026-10-30).
    관계는 늘 앞 날짜 → 뒤 날짜라 돌지 않는다."""
    nxt = {}
    for r in rs:
        nxt.setdefault(r["a"]["id"], set()).add(r["b"]["id"])

    def reach(x, goal):
        return any(n == goal or reach(n, goal) for n in nxt.get(x, ()))
    return [r for r in rs if not any(reach(m, r["b"]["id"]) for m in nxt[r["a"]["id"]] - {r["b"]["id"]})]


def _one_per_pair(rs):
    """같은 작은 별에서 같은 두 기록 사이 관계는 카드 하나만(실선 먼저). 앞 글의 생각 둘이 뒤 글의 같은 생각과 이어져
    '지금' 인용이 두 번 보였다(가상 인물 E 7/4 → 8/20, 2026-10-31)."""
    key = lambda r: (r["b"]["topic"], r["a"]["record_id"], r["b"]["record_id"])   # noqa: E731
    keep = {}
    for r in rs:
        if key(r) not in keep or (r.get("line") == "실선" and keep[key(r)].get("line") != "실선"):
            keep[key(r)] = r
    return [r for r in rs if keep[key(r)] is r]


def insight(thoughts, relations, suns=()):
    """thoughts: {id: {id, record_id, day, topic, domain, kind, quote}}, relations: 남은 관계 [{type, from, to, line, axis}].
    suns: 사용자가 추가한 해. 돌려줌: {period, suns: [{name, records, stars, kept, changed, open, settled}], across}.
    kept = 이어짐(작은 별마다 처음 · 마지막), changed = 바뀜, open = 아직 풀리지 않은 긴장, settled = 해소,
    across = 해를 넘는 관계. 우주에 띄우지 않는 해('그 밖')는 빠진다."""
    if not thoughts:
        return {"period": None, "suns": [], "across": []}
    days = sorted(t["day"] for t in thoughts.values())
    shown = sun_list(thoughts.values(), suns)["shown"]
    rels = []
    for r in relations:
        if r["from"] in thoughts and r["to"] in thoughts:
            a, b = sorted((thoughts[r["from"]], thoughts[r["to"]]), key=lambda t: (t["day"], t["id"]))
            rels.append({**r, "a": a, "b": b})
    rels.sort(key=lambda r: (r["b"]["day"], r["b"]["id"]))
    resolved = {r["a"]["id"] for r in rels if r["type"] == "해소"}   # 풀린 쪽은 먼저 쓴 생각(결론은 나중에 또 맞설 수 있다)
    out = []
    for sun in shown:
        ts = [t for t in thoughts.values() if t.get("domain") == sun]
        by_star = {}
        for t in ts:
            by_star.setdefault(t["topic"], []).append(t)
        stars = sorted(({"name": n, "records": len({t["record_id"] for t in v}), "first": min(t["day"] for t in v),
                         "last": max(t["day"] for t in v), "kinds": dict(Counter(t["kind"] for t in v).most_common(3))}
                        for n, v in by_star.items()), key=lambda s: (-s["records"], s["first"], s["name"]))
        mine = [r for r in rels if r["b"].get("domain") == sun and r["a"].get("domain") == sun]
        pair = lambda r: {"star": r["b"]["topic"], "line": r.get("line"), "from": _end(r["a"]), "to": _end(r["b"]),   # noqa: E731
                          "rid": r.get("id"), **({"axis": r["axis"]} if r.get("axis") else {})}
        kept = {}
        for r in mine:
            if r["type"] == "이어짐":
                k = kept.setdefault(r["b"]["topic"], {"star": r["b"]["topic"], "times": 0, "from": _end(r["a"]), "to": None})
                k["times"] += 1
                k["to"] = _end(r["b"])
                if r["a"]["day"] < k["from"]["day"]:
                    k["from"] = _end(r["a"])
        out.append({"name": sun, "records": len({t["record_id"] for t in ts}), "stars": stars,
                    "kept": sorted(kept.values(), key=lambda k: -k["times"]),
                    "changed": [pair(r) for r in _one_per_pair(_no_shortcuts([r for r in mine if r["type"] == "바뀜"]))],
                    "open": [pair(r) for r in _one_per_pair([r for r in mine if r["type"] == "긴장"
                                                             and not {r["a"]["id"], r["b"]["id"]} & resolved])],
                    "settled": [pair(r) for r in _one_per_pair([r for r in mine if r["type"] == "해소"])]})
    across = [{"type": r["type"], "suns": [r["a"]["domain"], r["b"]["domain"]], "from": _end(r["a"]), "to": _end(r["b"]),
               "rid": r.get("id"), "line": r.get("line")}
              for r in rels if r["a"].get("domain") != r["b"].get("domain")
              and {r["a"].get("domain"), r["b"].get("domain")} <= set(shown)]
    return {"period": {"from": days[0], "to": days[-1], "records": len({t["record_id"] for t in thoughts.values()})},
            "suns": out, "across": across}
