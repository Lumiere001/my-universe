"""
우주 배치용 요약(universe_symbols). 좌표는 화면이 정하고, 여기서는 무엇이 어디에 속하는지만 정한다.
"""

from collections import Counter

from app.service.rules.topics import sun_list


def universe_view(records, thoughts, relations, states, suns=()):
    """records: {id: {day, …}}, thoughts: {id: 생각}, relations: 남은 관계들, states: 상태 모델, suns: 사용자가 추가한 해.
    돌려줌: suns · hidden_axes · stars · planets · lines · binaries · black_holes · people."""
    by_rec = {}
    for t in sorted(thoughts.values(), key=lambda t: t["id"]):
        by_rec.setdefault(t["record_id"], []).append(t)
    planets, stars = [], {}
    for rid in sorted(records, key=lambda r: (records[r]["day"], r)):
        ts = by_rec.get(rid, [])
        topics = Counter(t["topic"] for t in ts)
        star = max(topics, key=lambda k: (topics[k], -[t["topic"] for t in ts].index(k))) if ts else None
        sun = next((t.get("domain") for t in ts if t["topic"] == star), None)
        vows = [states.get(t["id"], {}).get("state") for t in ts if t["kind"] == "다짐"]
        ring = "열림" if "열림" in vows else "채워짐" if "지켜짐" in vows else None
        if star:
            stars.setdefault((sun, star), []).append(rid)
        planets.append({
            "id": rid, "day": records[rid]["day"], "star": star, "sun": sun,
            "orbit": len(stars[(sun, star)]) - 1 if star else None,   # 0 = 작은 별에 가장 가까움(먼저 쓴 기록)
            "thoughts": len(ts), "decided": sum(t.get("certainty") == "단정" for t in ts),
            "question": any(states.get(t["id"], {}).get("state") == "열림" and states[t["id"]]["kind"] == "질문"
                            for t in ts),
            "ring": ring, "people": sorted({p for t in ts for p in t.get("people") or []}),
        })
    vow_open = {k for k, s in states.items() if s["kind"] == "다짐" and s["state"] == "열림"}
    lines = [{"id": r["id"], "type": r["type"], "color": r.get("color"), "line": r["line"],
              "from": r["from"], "to": r["to"], "from_record": r["from_record"], "to_record": r["to_record"],
              "cross_domain": r.get("cross_domain", False), "show": "on_tap" if r.get("cross_domain") else "always",
              "needs_confirm": r.get("needs_confirm", False),
              "ended": r["type"] == "목표 충돌" and not {r["from"], r["to"]} <= vow_open}
             for r in relations]
    rel_by_id = {r["id"]: r for r in relations}
    groups = [(k, s) for k, s in states.items() if s["kind"] == "긴장"]
    people = {}
    for p in planets:
        for n in p["people"]:
            people.setdefault(n, []).append(p["id"])
    shown = sun_list(thoughts.values(), suns)
    return {
        "suns": [{"name": s, "records": len({p["id"] for p in planets if p["sun"] == s}),
                  "stars": [st for (su, st) in stars if su == s]} for s in shown["shown"]],
        "hidden_axes": shown["hidden"],
        "stars": [{"name": st, "sun": su, "planets": rids} for (su, st), rids in stars.items()],
        "planets": planets,
        "lines": lines,
        "binaries": [{"key": k, "axis": s.get("axis", ""), "pairs": [[rel_by_id[i]["from_record"], rel_by_id[i]["to_record"]]
                                                                     for i in s["relations"] if i in rel_by_id]}
                     for k, s in groups if s["state"] == "열림"],
        "black_holes": [{"key": k, "topic": s.get("topic"), "axis": s.get("axis", ""), "size": s["size"],
                         "thoughts": s["thoughts"]} for k, s in groups if s["state"] == "블랙홀"],
        "people": people,
    }
