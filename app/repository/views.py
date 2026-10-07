"""
app/repository/views.py

저장된 행 → docs/api-v8.md 의 응답 모양(EntryResult · Universe · 사람 · 되고 싶은 모습 · /stats).
"""

from collections import Counter

from app.core.ontology import load
from app.repository import diary
from app.service.rules import universe_view
from app.service.safety import care_message

NEXT_KIND = {"weather": "weather", "aspiration": "aspiration", "aspiration_invite": "aspiration", "first": "free",
             "commitment": "free", "open_question": "free", "": "none", None: "none"}
QUESTION = {"동명이인": "'{n}'은(는) 사람 목록의 같은 이름 중 누구인가요?",
            "별명": "'{n}'은(는) 사람 목록에 있는 사람을 부르는 말인가요?",
            "이름인지 낱말인지": "'{n}'은(는) 사람 이름인가요?"}
OPTIONS = {"동명이인": ["같은 사람", "다른 사람", "사람 이름 아님"], "별명": ["같은 사람", "다른 사람", "사람 이름 아님"],
           "이름인지 낱말인지": ["사람 이름", "사람 이름 아님"]}


def thought_state(t, states, relations):
    """생각 하나의 상태: 자기 상태(다짐 · 질문) → 바뀜의 새 쪽 → 긴장 묶음."""
    s = states.get(t["id"])
    if s:
        return {"type": s["kind"], "status": s["state"], "mistake": "실수" in s.get("marks", [])}
    for r in relations:
        if r["to"] == t["id"] and r["id"] in states and states[r["id"]]["kind"] == "바뀜":
            return {"type": "바뀜", "status": states[r["id"]]["state"], "mistake": False}
    for g in states.values():
        if g["kind"] == "긴장" and t["id"] in g.get("thoughts", []):
            return {"type": "긴장", "status": g["state"], "mistake": False}
    return None


def thought_api(t, states, relations):
    return {"id": t["id"], "text": t.get("text", ""), "kind": t["kind"], "grateful": t["grateful"],
            "certainty": t["certainty"], "value": t["value"] or None, "quote": t.get("quote", ""),
            "self_change": t.get("self_change") or None, "topic": t.get("topic", ""), "star_id": t["star_id"],
            "sun_id": t["sun_id"], "people": t["people"], "other": t.get("other") or None,
            "state": thought_state(t, states, relations)}


def relation_api(r):
    return {"id": r["id"], "from": r["from"], "to": r["to"], "from_entry": r["from_record"], "to_entry": r["to_record"],
            "type": r["type"], "group": r["group"], "line": r["line"], "cross_domain": r["cross_domain"],
            "needs_confirm": r["needs_confirm"], "explanation": r.get("explanation") or "", "quote": r.get("quote") or None}


def entry_result(s, eid):
    e = diary.entry(s, eid)
    if not e:
        return None
    d = e["data"]
    settings, _ = diary.profile(s)
    base = {"id": eid, "status": e["status"], "step": e["step"] or "", "written_at": diary.iso(e["written_at"]),
            "title": d.get("title", ""), "weather": e["weather"], "crisis": e["crisis"], "care": None, "info": None,
            "thoughts": [], "relations": [], "past": [], "reached": [], "message": None, "next_question": None,
            "people_questions": []}
    if e["crisis"]:
        return {**base, "care": {"message": care_message(resources=False), "resources": load()["crisis"]["resources"]},
                "message": {"text": "", "tone": settings["tone"], "mode": "care"}}
    if e["status"] != "done":
        return base
    states = diary.states(s)
    ts = diary.thoughts(s, entry_id=eid)
    ids = [t["id"] for t in ts]
    rels = (diary.relations(s, to_thought=ids) + [r for r in diary.relations(s, from_thought=ids) if r["to"] not in ids]) if ids else []
    past_ids = d.get("past") or []
    past = []
    if past_ids:
        pts = {t["id"]: t for t in diary.thoughts(s, id=past_ids)}
        when = {x["id"]: x["written_at"] for x in s.rows("entries", id=list({t["entry_id"] for t in pts.values()}))}
        past = [{"thought_id": i, "entry_id": pts[i]["entry_id"], "text": pts[i].get("text", ""),
                 "written_at": diary.iso(when.get(pts[i]["entry_id"]))} for i in past_ids if i in pts]
    reached = [{"aspiration_id": x["aspiration_id"], **diary.unseal(s, "aspiration_reached", x["id"], x["enc"])}
               for x in s.rows("aspiration_reached", entry_id=eid)]
    m = s.rows("messages", entry_id=eid)
    msg = diary.unseal(s, "messages", m[0]["id"], m[0]["enc"]) if m else {}
    qs = [{"id": q["id"], "name": q["name"], "question": QUESTION[q["reason"]].format(n=q["name"]), "options": OPTIONS[q["reason"]]}
          for q in diary.questions(s, entry_id=eid) if not q["answer"]]
    return {**base,
            "info": {"summary": d.get("summary", ""), "addressee": e["addressee"] or "나",
                     "addressee_person": d.get("addressee_person"), "events": d.get("events", [])},
            "thoughts": [thought_api(t, states, rels) for t in ts],
            "relations": [relation_api(r) for r in rels],
            "past": past,
            "reached": [{"aspiration_id": r["aspiration_id"], "quote": r.get("quote", ""), "message": r.get("note", "")}
                        for r in reached],
            "message": {"text": msg.get("text", ""), "tone": m[0]["tone"], "mode": m[0]["mode"]} if m else None,
            "next_question": {"kind": NEXT_KIND.get(m[0]["next_kind"], "free"), "text": msg.get("next_question", "")} if m else None,
            "people_questions": qs}


def entry_list(s, limit=20, before=None):
    sun = {x["id"]: x["name"] for x in diary.suns(s)}
    star = {x["id"]: x["name"] for x in diary.stars(s)}
    return [{"id": e["id"], "written_at": diary.iso(e["written_at"]), "title": e["data"].get("title", ""),
             "summary": e["data"].get("summary", ""), "weather": e["weather"], "status": e["status"],
             "sun": sun.get(e["sun_id"]), "star": star.get(e["star_id"])}
            for e in diary.entries(s, limit=limit, before=before)]


def universe(s):
    entries = {e["id"]: e for e in diary.entries(s, status="done", crisis=False)}
    suns = diary.suns(s)
    sun_name = {x["id"]: x["name"] for x in suns}
    stars = diary.stars(s)
    star_id = {x["name"]: x["id"] for x in stars}
    ts = {t["id"]: {**t, "record_id": t["entry_id"], "domain": sun_name.get(t["sun_id"]),
                    "day": diary.local_day(entries[t["entry_id"]]["written_at"])}
          for t in diary.thoughts(s, entry_id=list(entries)) if t["entry_id"] in entries} if entries else {}
    rels = [r for r in diary.relations(s) if r["from"] in ts and r["to"] in ts]
    states = diary.states(s)
    people = diary.people(s)
    asp = (diary.aspirations(s) or [None])[-1]
    records = {i: {"day": diary.local_day(e["written_at"])} for i, e in entries.items()}
    v = universe_view(records, ts, rels, states, [x["name"] for x in suns if x["custom"]])
    by_entry = {}
    for t in ts.values():
        by_entry.setdefault(t["record_id"], []).append(t)
    planets = []
    for p in v["planets"]:
        if not p["star"]:
            continue   # 생각이 없는 글은 /diary 목록에만
        e, mine = entries[p["id"]], by_entry[p["id"]]
        cert = Counter(t["certainty"] for t in mine)
        planets.append({"id": p["id"], "star_id": star_id.get(p["star"]), "sun_id": next((x["id"] for x in suns if x["name"] == p["sun"]), None),
                        "written_at": diary.iso(e["written_at"]), "title": e["data"].get("title", ""), "order": p["orbit"],
                        "ring": bool(p["ring"]), "ring_state": p["ring"], "people": sorted({i for t in mine for i in t["people"]}),
                        "weather": e["weather"], "thought_count": p["thoughts"],
                        "certainty": max(cert, key=lambda c: (cert[c], c == "단정")) if cert else None,
                        "has_question": p["question"]})
    count = Counter(p["star_id"] for p in planets)
    sun_count = Counter(p["sun_id"] for p in planets)
    shown = {s_["name"] for s_ in v["suns"]}
    rel_by_id = {r["id"]: r for r in rels}
    twins, holes = [], []
    for k, g in states.items():
        if g["kind"] != "긴장" or not g.get("relations"):
            continue
        r = rel_by_id.get(g["relations"][0])
        if not r:
            continue
        planets_of = sorted({ts[t]["record_id"] for t in g["thoughts"] if t in ts})
        if g["state"] in ("열림", "해소"):
            twins.append({"id": k, "a_planet": r["from_record"], "b_planet": r["to_record"],
                          "topic": g.get("axis") or g.get("topic") or "", "status": g["state"]})
        else:
            holes.append({"id": k, "star_id": star_id.get(g.get("topic")) or (ts[r["to"]]["star_id"]),
                          "label": g.get("axis") or g.get("topic") or "", "size": g["size"], "planets": planets_of})
    return {
        "suns": [{"id": x["id"], "name": x["name"], "custom": x["custom"], "planet_count": sun_count[x["id"]]}
                 for x in suns if x["name"] in shown and (sun_count[x["id"]] or x["custom"])],
        "stars": [{"id": x["id"], "sun_id": x["sun_id"], "name": x["name"], "planet_count": count[x["id"]]}
                  for x in stars if count[x["id"]]],
        "planets": planets,
        "links": [{"id": r["id"], "from_planet": r["from_record"], "to_planet": r["to_record"], "type": r["type"],
                   "line": r["line"], "cross_domain": r["cross_domain"], "needs_confirm": r["needs_confirm"],
                   "explanation": r.get("explanation") or ""} for r in rels if r["from_record"] != r["to_record"]],
        "twins": twins,
        "blackholes": holes,
        "north_star": {"text": asp["said"], "values": asp["values"],
                       "reached_planets": sorted({x["entry_id"] for x in asp["reached"] if x["entry_id"] in entries})} if asp else None,
        "people": [{"id": p["id"], "name": p["name"], "relation": p["relation"],
                    "planets": sorted({t["record_id"] for t in ts.values() if p["id"] in t["people"]})} for p in people],
    }


def people_list(s):
    entry_of = {t["id"]: t["entry_id"] for t in s.rows("thoughts")}
    planets = {}
    for tp in s.rows("thought_people"):
        planets.setdefault(tp["person_id"], set()).add(entry_of.get(tp["thought_id"]))
    return [{"id": p["id"], "name": p["name"], "nickname": ", ".join(p.get("nicknames") or []), "relation": p["relation"],
             "auto": p["auto"], "planets": sorted(planets.get(p["id"], []))} for p in diary.people(s)]


def person_api(p):
    return {"id": p["id"], "name": p["name"], "nickname": ", ".join(p.get("nicknames") or []), "relation": p["relation"],
            "auto": p["auto"], "planets": []}


def aspiration_api(a):
    return {"id": a["id"], "said": a["said"], "values": a["values"], "obstacle": a.get("obstacle", ""),
            "if_then": a.get("if_then", ""), "said_at": diary.iso(a["said_at"]),
            "reached": [{"entry_id": x["entry_id"], "quote": x.get("quote", ""), "at": diary.iso(x["at"])} for x in a["reached"]]}


ASK_AFTER_DAYS = 3   # voice.ASPIRATION_AFTER_DAYS 와 같은 값(며칠 쓴 뒤 허락을 구함)


def aspiration_state(s):
    all_ = diary.aspirations(s)
    _, ob = diary.profile(s)
    days = len({diary.local_day(e["written_at"]) for e in diary.entries(s, status="done")})
    should = not all_ and ob["aspiration"] not in ("skip", "stop") and days >= ASK_AFTER_DAYS
    return {"current": aspiration_api(all_[-1]) if all_ else None,
            "history": [aspiration_api(a) for a in reversed(all_[:-1])],
            "ask": {"should_ask": should, "step": (ob.get("aspiration_step") or 0) + 1}}


def stats(s):
    entries = diary.entries(s)
    fb = Counter(r["value"] for r in s.rows("feedback"))
    yes, no = fb.get("맞아요", 0), fb.get("아니에요", 0)
    return {"entries": len(entries), "entries_done": sum(e["status"] == "done" for e in entries),
            "days_written": len({diary.local_day(e["written_at"]) for e in entries}),
            "suns_with_entries": len({e["sun_id"] for e in entries if e["sun_id"]}),
            "feedback": dict(fb), "yes_ratio": round(yes / (yes + no), 3) if yes + no else None,
            "month_cost_usd": round(diary.month_cost(s), 4)}
