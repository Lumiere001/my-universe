"""
app/repository/drafts.py

요약 확인(WS20). 대화에서 온 초안은 기록 · 관측 Agent 와 한마디까지 돌고 save 앞에서 멈춘다(entries.confirmed = '확인 전',
단계 저장값 steps_enc 에 정리 결과). 멈춘 기록은 목록 · 우주에 보이지 않고, 확인 화면이 단계 저장값을 읽어 보여 준다.
'확인하고 우주에 저장' → 고친 것을 단계 저장값에 넣고 '확인됨' → 그래프가 끝난 노드를 건너뛰고 save 만 돈다.
확인하지 않고 둔 초안은 따로 도는 작업 없이 다음 요청 때 오래된 것부터 지운다(config.DRAFT_KEEP_HOURS).
"""

from datetime import timedelta

from app.core import config
from app.repository import diary

WAITING = "확인 전"


def pending(e):
    """확인을 기다리는 초안: 확인 전 + 한마디(voice)까지 끝나고 save 전."""
    return e["status"] == "processing" and e.get("confirmed") == WAITING and "voice" in (e.get("steps") or {}).get("done", [])


def _thought(t):
    original = t.get("original") or {}
    return {"id": t["id"], "text": t.get("thought", ""), "kind": t["kind"], "grateful": "감사" in (t.get("flags") or []),
            "certainty": t["certainty"], "value": t.get("value") or None, "quote": t.get("quote", ""),
            "self_change": t.get("self_change") or None, "topic": t.get("topic", ""), "star_id": t.get("star_id"),
            "sun_id": t.get("sun_id"), "people": t.get("people", []), "other": original.get("kind"),
            "original": original or None, "state": None}


def result(e, base):
    """멈춘 초안 → EntryResult 모양(status 'confirm'). 한마디 · 다음 질문은 저장한 뒤에 보인다(대화 안의 별지기 말풍선)."""
    st = e["steps"]
    rec = st.get("record") or {}
    return {**base, "status": "confirm", "crisis": bool(st.get("crisis")),
            "info": {"summary": rec.get("summary", ""), "addressee": rec.get("addressee") or "나", "addressee_person": None,
                     "events": rec.get("events", []), "original": rec.get("original") or None},
            "thoughts": [_thought(t) for t in st.get("today", [])],
            "relations": [{"id": r["id"], "from": r["from"], "to": r["to"], "from_entry": r["from_record"],
                           "to_entry": r["to_record"], "type": r["type"], "group": r["group"], "line": r["line"],
                           "cross_domain": r["cross_domain"], "needs_confirm": r["needs_confirm"],
                           "explanation": r.get("explanation") or "", "quote": r.get("quote")} for r in st.get("relations", [])],
            "past": [{"thought_id": p["id"], "entry_id": p.get("record_id"), "text": p.get("thought", ""),
                      "written_at": p.get("written_at")} for p in st.get("past", [])]}


def _note(s, eid, value, data):
    """확인 화면의 맞아요 · 고침(오답 재료). 대상 문장은 암호문에만, 기록을 지우면 같이 지워지게 target_id = 기록 id."""
    fid = diary.new_id("f")
    s.insert("feedback", {"id": fid, "target": "confirm", "target_id": eid, "value": value,
                          "enc": diary.seal(s, "feedback", fid, data), "studio_config": diary.run_config(s, eid)})


def confirm(s, vectors, e, summary=None, fixes=(), agreed=()):
    """고친 것(요약 문장 · 생각 종류 · 생각 빼기)을 단계 저장값에 넣고 '확인됨'으로 바꾼다. 원문 인용은 고치지 않는다(G1).
    fixes: [{"id", "kind"?, "remove"?}], agreed: 맞아요를 누른 항목('summary' 또는 생각 id).
    모르는 생각 id 면 KeyError(아무것도 안 바꿈)."""
    eid, st = e["id"], dict(e["steps"])
    today = {t["id"]: dict(t) for t in st["today"]}
    unknown = [f["id"] for f in fixes if f["id"] not in today] + [a for a in agreed if a != "summary" and a not in today]
    if unknown:
        raise KeyError(unknown)
    rec = dict(st.get("record") or {})
    if summary is not None and summary != rec.get("summary"):
        _note(s, eid, "확인 고침", {"item": "summary", "before": rec.get("summary", ""), "after": summary})
        rec["summary"] = summary
    removed = set()
    for f in fixes:
        t = today[f["id"]]
        if f.get("remove"):
            removed.add(t["id"])
            _note(s, eid, "확인 고침", {"item": t["id"], "removed": True, "kind": t["kind"], "thought": t.get("thought", "")})
        elif f.get("kind") and f["kind"] != t["kind"]:
            _note(s, eid, "확인 고침", {"item": t["id"], "field": "kind", "before": t["kind"], "after": f["kind"],
                                    "thought": t.get("thought", "")})
            t["kind"] = f["kind"]
            t["original"] = {k: v for k, v in (t.get("original") or {}).items() if k != "kind"}   # 사람이 고른 값이 이긴다
            if t["kind"] != "감정":
                t["flags"] = [x for x in t.get("flags") or [] if x != "감사"]
    for a in agreed:
        _note(s, eid, "확인 맞아요", {"item": a})
    # ponytail: 고친 종류로 관계 규칙 · 한마디를 다시 돌리지 않는다(빠진 생각의 관계만 뺌). 어긋남이 보이면 그때 rules 를 다시 부른다.
    st["record"] = rec
    st["today"] = [today[t["id"]] for t in st["today"] if t["id"] not in removed]
    st["relations"] = [r for r in st.get("relations", []) if r["from"] not in removed and r["to"] not in removed]
    st["reached"] = [r for r in st.get("reached", []) if r.get("thought") not in removed]
    if removed:
        vectors.delete(s.uid, ids=sorted(removed))
    s.update("entries", {"confirmed": "확인됨", "steps_enc": diary.seal(s, "entries.steps", eid, st), "updated_at": diary.now()},
             id=eid)


def expire(s, vectors):
    """확인하지 않고 DRAFT_KEEP_HOURS 넘게 둔 초안(멈춘 것 · 정리하다 멈춘 것)을 오래된 것부터 지운다 → 지운 수."""
    if config.DRAFT_KEEP_HOURS <= 0:
        return 0
    cut = diary.now() - timedelta(hours=config.DRAFT_KEEP_HOURS)
    old = [r for r in s.rows("entries", confirmed=WAITING, lt={"updated_at": cut}, order="updated_at") if not diary.is_locked(r)]
    for r in old:
        diary.delete_entry(s, vectors, r["id"])
    return len(old)
