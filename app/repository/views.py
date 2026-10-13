"""
app/repository/views.py

저장된 행 → docs/api-v8.md 의 응답 모양(EntryResult · Universe · 사람 · 되고 싶은 모습 · /stats).
"""

from collections import Counter

from app.core.ontology import load
from app.repository import diary, drafts
from app.service.rules import universe_view

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
            "original": t.get("original") or ({"kind": t["other"]} if t.get("other") else None),   # 목록 밖 원래 말
            "state": thought_state(t, states, relations)}


def relation_api(r):
    return {"id": r["id"], "from": r["from"], "to": r["to"], "from_entry": r["from_record"], "to_entry": r["to_record"],
            "type": r["type"], "group": r["group"], "line": r["line"], "cross_domain": r["cross_domain"],
            "needs_confirm": r["needs_confirm"], "explanation": r.get("explanation") or "", "quote": r.get("quote") or None}


def record_fields(e):
    """기록 칸(PRD §4.1 · §4.4). 이 칸이 생기기 전의 행은 출처 텍스트 · 쓴 날(추정)."""
    return {"source": e.get("source") or "텍스트", "day": str(e["day"]) if e.get("day") else diary.local_day(e["written_at"]),
            "day_basis": e.get("day_basis") or "추정", "day_check": bool(e["data"].get("day_check")),
            "confirmed": e.get("confirmed"), "record_type": e.get("record_type")}


OBS_ORDER = load()["observation_states"]["priority"]   # 해소 > 바뀜 > 긴장 > 어긋남 > 이어짐 > 처음 쓰는 주제


def observation(r, ts, rels, past_ids, pts):
    """관측 보고서의 관측 상태 · 한계(PRD §7 474, WS15). 관측 Agent 의 Classify 는 저장하지 않으므로
    규칙이 거른 뒤 저장된 관계로 다시 센다. r: 기록 칸이 붙은 EntryResult 앞부분, ts: 이 기록의 생각,
    rels: 이 기록의 관계, past_ids: 정리할 때 비교한 지난 생각 id, pts: 그중 아직 남은 생각 {id: 생각}."""
    ids = {t["id"] for t in ts}
    found = [x["type"] for x in rels if x["to"] in ids and x["from_record"] != r["id"]]   # 이 글이 새 쪽인 지난 글과의 관계
    if not ts:
        state = "생각이 없는 글"
    elif not past_ids:
        state = "비교할 지난 글 없음"
    elif found:
        state = min(found, key=lambda k: OBS_ORDER.index(k) if k in OBS_ORDER else len(OBS_ORDER))
    elif {p["star_id"] for p in pts.values()} & {t["star_id"] for t in ts}:
        state = "이어진 지난 생각 없음"   # 같은 세부 주제의 지난 생각은 있었지만 이어지지 않음
    else:
        state = "처음 쓰는 주제"
    limits = ["생각 나누기와 이어진 선은 AI 가 원문 인용을 근거로 한 추정이라 틀릴 수 있어요."] if ts else []
    if past_ids:
        limits.append(f"지난 생각 {len(past_ids)}개와만 비교했어요. 같은 세부 주제와 뜻이 가까운 것을 골랐고, "
                      "이 글을 정리할 때 이미 있던 기록만 봤어요.")
    if any(x["line"] == "점선" and x["to"] in ids for x in rels):
        limits.append("점선은 글에 직접 쓰지 않은 연결이에요. 맞는지 알려 주세요.")
    if r["day_check"]:
        limits.append("글 속 날짜를 하나로 읽지 못했어요. 글이 다루는 날을 확인해 주세요.")
    elif r["day_basis"] == "추정":
        limits.append("글이 다루는 날을 쓴 날로 추정했어요.")
    return {"state": state, "limits": limits}


def entry_result(s, eid):
    e = diary.entry(s, eid)
    if not e:
        return None
    d = e["data"]
    base = {"id": eid, "status": e["status"], "step": e["step"] or "", "written_at": diary.iso(e["written_at"]),
            **record_fields(e),
            "title": d.get("title", ""), "weather": e["weather"], "crisis": e["crisis"], "info": None,
            "thoughts": [], "relations": [], "past": [], "reached": [], "message": None, "next_question": None,
            "people_questions": [], "observation": None}
    if e["status"] != "done":
        return drafts.result(e, base) if drafts.pending(e) else base   # 확인을 기다리는 대화 초안(WS20)
    states = diary.states(s)
    ts = diary.thoughts(s, entry_id=eid)
    ids = [t["id"] for t in ts]
    rels = (diary.relations(s, to_thought=ids) + [r for r in diary.relations(s, from_thought=ids) if r["to"] not in ids]) if ids else []
    past_ids = d.get("past") or []
    past, pts = [], {}
    if past_ids:
        pts = {t["id"]: t for t in diary.thoughts(s, id=past_ids)}
        when = {x["id"]: x["written_at"] for x in s.rows("entries", id=list({t["entry_id"] for t in pts.values()}))}
        past = [{"thought_id": i, "entry_id": pts[i]["entry_id"], "text": pts[i].get("text", ""),
                 "written_at": diary.iso(when.get(pts[i]["entry_id"]))} for i in past_ids if i in pts]
    reached = [{"aspiration_id": x["aspiration_id"], **diary.unseal(s, "aspiration_reached", x["id"], x["enc"])}
               for x in s.rows("aspiration_reached", entry_id=eid)]
    m = s.rows("messages", entry_id=eid)
    msg = diary.message(s, m[0]) if m else {}
    qs = [{"id": q["id"], "name": q["name"], "question": QUESTION[q["reason"]].format(n=q["name"]), "options": OPTIONS[q["reason"]]}
          for q in diary.questions(s, entry_id=eid) if not q["answer"]]
    return {**base,
            "info": {"summary": d.get("summary", ""), "addressee": e["addressee"] or "나",
                     "addressee_person": d.get("addressee_person"), "events": d.get("events", []),
                     "original": d.get("original") or None},
            "thoughts": [thought_api(t, states, rels) for t in ts],
            "relations": [relation_api(r) for r in rels],
            "past": past,
            "reached": [{"aspiration_id": r["aspiration_id"], "quote": r.get("quote", ""), "message": r.get("note", "")}
                        for r in reached],
            "message": {"text": msg.get("text", ""), "tone": m[0]["tone"], "mode": msg["mode"],
                        "check_in": msg.get("check_in") or None} if m else None,
            "next_question": {"kind": NEXT_KIND.get(m[0]["next_kind"], "free"), "text": msg.get("next_question", "")} if m else None,
            "people_questions": qs,
            "observation": observation(base, ts, rels, past_ids, pts)}


def entry_list(s, limit=20, before=None):
    sun = {x["id"]: x["name"] for x in diary.suns(s)}
    star = {x["id"]: x["name"] for x in diary.stars(s)}
    waiting = len(s.rows("entries", confirmed=drafts.WAITING))   # 확인 전 초안은 안 보임: 그만큼 더 가져와 거른 뒤에도 한 쪽이 limit 개
    shown = [e for e in diary.entries(s, limit=limit + waiting, before=before) if e.get("confirmed") != drafts.WAITING][:limit]
    return [{"id": e["id"], "written_at": diary.iso(e["written_at"]), "title": e["data"].get("title", ""),
             "summary": e["data"].get("summary", ""), "weather": e["weather"], "status": e["status"],
             "sun": sun.get(e["sun_id"]), "star": star.get(e["star_id"]), **record_fields(e)}
            for e in shown]


EXPORT_SCHEMA = "my-universe-export/1"


def export(s, eid=None):
    """JSON 내려받기(PRD §5.6 · §7 474, WS15): 기록 하나(eid) 또는 전체(먼저 쓴 것부터). 없는 기록이면 None.
    records[] = EntryResult(people_questions · step 뺌) + 원문 text, 생각에 영역 이름. 보고서 = observation · relations ·
    past · reached · message · next_question. 다른 사람 이름은 실명 그대로(2026-10-13 동규 결정 12) — 사람은 id 대신
    이름으로 적고, 사람 목록(외부 AI 로 보낼 때의 가명 표)은 넣지 않는다."""
    es = ([e for e in [diary.entry(s, eid)] if e] if eid
          else [e for e in diary.entries(s)[::-1] if e.get("confirmed") != drafts.WAITING])   # 확인 전 대화 초안은 목록처럼 뺌(WS20)
    if eid and not es:
        return None
    name = {p["id"]: p["name"] for p in diary.people(s)}
    suns = diary.suns(s)
    sun = {x["id"]: x["name"] for x in suns}
    records = []
    for e in es:
        # ponytail: 기록마다 entry_result 를 따로 읽어 쿼리 수가 기록 수에 비례한다. 수천 편이 되면 한 번에 읽어 묶기.
        r = {k: v for k, v in entry_result(s, e["id"]).items() if k not in ("people_questions", "step")}
        r["text"] = e["data"].get("text", "")
        for t in r["thoughts"]:
            t["people"] = [name[i] for i in t["people"] if i in name]
            t["domain"] = sun.get(t["sun_id"])
        if r["info"]:
            r["info"]["addressee_person"] = name.get(r["info"]["addressee_person"])
        records.append(r)
    used_sun = {t["sun_id"] for r in records for t in r["thoughts"]}
    used_star = {t["star_id"] for r in records for t in r["thoughts"]}
    stars = [x for x in diary.stars(s) if x["id"] in used_star]
    return {"schema": EXPORT_SCHEMA, "exported_at": diary.iso(diary.now()), "scope": "entry" if eid else "all",
            "records": records,
            "domains": [{"id": x["id"], "name": x["name"], "custom": x["custom"],
                         "topics": [{"id": st["id"], "name": st["name"]} for st in stars if st["sun_id"] == x["id"]]}
                        for x in suns if x["id"] in used_sun or (x["custom"] and not eid)]}


def universe(s):
    entries = {e["id"]: e for e in diary.entries(s, status="done")}   # 위기 글도 평소처럼 행성(시험 단계)
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
                   "explanation": r.get("explanation") or "",
                   # 원문 인용: 그때(옛 생각) → 지금(새 생각). 행성 카드가 쓴다(PRD §7 474)
                   "from_quote": ts[r["from"]].get("quote", ""), "to_quote": ts[r["to"]].get("quote", ""),
                   # 목표 충돌은 두 다짐 중 하나가 닫히면(지켜짐 · 그만둠) 끝난다(PRD §4.3)
                   "ended": r["type"] == "목표 충돌" and any((states.get(i) or {}).get("state") in ("지켜짐", "그만둠")
                                                         for i in (r["from"], r["to"]))}
                  for r in rels if r["from_record"] != r["to_record"]],
        "twins": twins,
        "blackholes": holes,
        "north_star": {"text": asp["said"], "values": asp["values"],
                       "reached_planets": sorted({x["entry_id"] for x in asp["reached"] if x["entry_id"] in entries}),
                       "reached": [{"entry_id": x["entry_id"], "quote": x.get("quote", ""), "at": diary.iso(x["at"])}
                                   for x in asp["reached"] if x["entry_id"] in entries]} if asp else None,
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


def person_thoughts(s, pid):
    """사람 하나와 얽힌 생각(끝난 기록만), 쓴 때 순서. 없는 사람이면 None(PRD §7 우주의 기호 '사람')."""
    p = next((p for p in diary.people(s) if p["id"] == pid), None)
    if not p:
        return None
    out = {"person": {"id": p["id"], "name": p["name"], "relation": p["relation"]}, "thoughts": []}
    tids = [x["thought_id"] for x in s.rows("thought_people", person_id=pid)]
    ts = diary.thoughts(s, id=tids) if tids else []
    entries = {e["id"]: e for e in diary.entries(s, status="done", id=list({t["entry_id"] for t in ts}))} if ts else {}
    ts = sorted((t for t in ts if t["entry_id"] in entries), key=lambda t: (entries[t["entry_id"]]["written_at"], t["position"]))
    if not ts:
        return out
    states, rels = diary.states(s), diary.relations(s, to_thought=[t["id"] for t in ts])
    return {**out, "thoughts": [{**thought_api(t, states, rels), "entry_id": t["entry_id"],
                                 "written_at": diary.iso(entries[t["entry_id"]]["written_at"]),
                                 "title": entries[t["entry_id"]]["data"].get("title", "")} for t in ts]}


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
    fb = diary.feedback_counts(s)
    yes, no = fb.get("맞아요", 0), fb.get("아니에요", 0)
    return {"entries": len(entries), "entries_done": sum(e["status"] == "done" for e in entries),
            "days_written": len({diary.local_day(e["written_at"]) for e in entries}),
            "suns_with_entries": len({e["sun_id"] for e in entries if e["sun_id"]}),
            "feedback": dict(fb), "yes_ratio": round(yes / (yes + no), 3) if yes + no else None,
            "month_cost_usd": round(diary.month_cost(s), 4)}
