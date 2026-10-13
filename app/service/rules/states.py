"""
상태 모델(states). 숫자가 아니라 '아직 열려 있는가'로 판정한다.

- 다짐(생각 id): 열림 → 지켜짐 · 그만둠. 반성(어긋남)이 와도 닫지 않고 "실수" 표시. 기한 지난 다짐은 안부 재료.
- 질문(생각 id): 열림 → 해소(같은 주제의 단정으로 정리된 해소 관계).
- 긴장(묶음 "긴장:<관계 id>"): 열림 → 해소, 풀리지 않은 채 다른 날 다시 나오면 블랙홀(다시 나올수록 size 증가).
- 바뀜(관계 id): 스스로 쓴 변화면 확정, 아니면 후보 → 같은 새 입장이 다른 날 다시 나오거나 '맞아요'면 확정.
상태 변화마다 history 에 근거(생각 · 관계 · 버튼)를 남긴다. 함수는 받은 dict 를 고치지 않고 새 dict 를 돌려준다.
"""

import calendar
import copy
import re
from datetime import date, timedelta

from app.core.ontology import load
from app.service.rules.normalize import key
from app.service.rules.relations import is_question

O = load()
BUTTONS = {b["name"]: b for b in O["state_buttons"]}
NO = "아니에요"   # feedback: 점선 관계를 지운다(state_buttons 에는 없음)
WEEKDAYS = "월화수목금토일"


def parse_due(text, day):
    """다짐 문장의 기한('금요일까지 · 다음 주까지 · 10월 3일까지 …') → ISO 날짜 또는 None."""
    d = date.fromisoformat(day)
    if m := re.search(r"(\d{1,2})월\s*(\d{1,2})일\s*까지", text):
        due = date(d.year, int(m[1]), int(m[2]))
        return (due if due >= d else due.replace(year=d.year + 1)).isoformat()
    if m := re.search(r"([월화수목금토일])요일\s*까지", text):
        return (d + timedelta(days=(WEEKDAYS.index(m[1]) - d.weekday() - 1) % 7 + 1)).isoformat()
    if re.search(r"내일\s*까지", text):
        return (d + timedelta(days=1)).isoformat()
    if m := re.search(r"(이번|다음)\s*주(말)?\s*까지", text):
        return (d + timedelta(days=6 - d.weekday() + (7 if m[1] == "다음" else 0))).isoformat()
    if m := re.search(r"(이번|다음)\s*달\s*까지", text):
        y, mo = (d.year, d.month) if m[1] == "이번" else (d.year + d.month // 12, d.month % 12 + 1)
        return date(y, mo, calendar.monthrange(y, mo)[1]).isoformat()
    return None


def _ev(s, to, why, day=None, **by):
    s["history"].append({"to": to, "why": why, "day": day, **by})
    if to in ("열림", "지켜짐", "그만둠", "해소", "블랙홀", "후보", "확정"):
        s["state"] = to


def advance(states, thoughts, relations, record_id):
    """글 한 편을 저장한 뒤 상태를 앞으로 민다. thoughts: 전체 {id: 생각}, relations: 이번 글에서 남은 관계들."""
    st = copy.deepcopy(states or {})
    mine = sorted((t for t in thoughts.values() if t["record_id"] == record_id), key=lambda t: t["id"])
    for t in mine:
        if t["kind"] == "다짐":
            st[t["id"]] = {"kind": "다짐", "state": None, "topic": t.get("topic"), "marks": [], "history": [],
                           "due": parse_due(f"{t.get('thought', '')} {t.get('quote', '')}", t["day"])}
            _ev(st[t["id"]], "열림", "다짐이 나옴", t["day"], thought=t["id"])
        elif is_question(t):
            st[t["id"]] = {"kind": "질문", "state": None, "topic": t.get("topic"), "history": []}
            _ev(st[t["id"]], "열림", "답을 못 낸 물음이 나옴", t["day"], thought=t["id"])
    for r in relations:
        new_day = thoughts[r["to"]]["day"]
        ev = {"thought": r["to"], "relation": r["id"]}
        src = st.get(r["from"])
        if r["type"] == "어긋남" and src and src["kind"] == "다짐" and src["state"] == "열림":
            if "실수" not in src["marks"]:
                src["marks"].append("실수")
            _ev(src, "실수", "열린 다짐 뒤 같은 주제의 반성(다짐은 닫지 않음)", new_day, **ev)
        if r["type"] == "이어짐" and r.get("vow_kept") and src and src["kind"] == "다짐" and src["state"] == "열림":
            _ev(src, "지켜짐", "다짐을 지켰다는 글", new_day, **ev)
        if r.get("vow_quit") and src and src["kind"] == "다짐" and src["state"] == "열림":
            _ev(src, "그만둠", "그만둔다는 글", new_day, **ev)
        if r["type"] == "해소":
            if src and src["kind"] == "질문" and src["state"] == "열림":
                _ev(src, "해소", "같은 주제의 단정한 생각으로 정리됨", new_day, **ev)
            for g in st.values():
                if g["kind"] == "긴장" and g["state"] in ("열림", "블랙홀") and {r["from"], r["to"]} & set(g["thoughts"]):
                    _ev(g, "해소", "긴장에 결론이 나옴", new_day, **ev)
        if r["type"] == "바뀜":
            # 스스로 쓴 변화라도 새 생각이 아직 열린 질문이면 새 입장이 아니다 → 후보(PRD 4/5 → 4/12 예)
            new = thoughts[r["to"]]
            direct = (bool(new.get("self_change")) or r["line"] == "실선") and not is_question(new)
            st[r["id"]] = {"kind": "바뀜", "state": None, "from": r["from"], "to": r["to"], "history": []}
            _ev(st[r["id"]], "확정" if direct else "후보", "스스로 쓴 변화" if direct else "직접 쓴 변화가 아니거나 새 입장이 열린 질문", new_day, **ev)
        if r["type"] == "이어짐" and thoughts[r["from"]]["day"] != new_day:
            for s in st.values():
                if s["kind"] == "바뀜" and s["state"] == "후보" and s["to"] == r["from"]:
                    _ev(s, "확정", "같은 새 입장이 다른 날 다시 나옴", new_day, **ev)
        if r["type"] == "긴장":
            ends, ax = {r["from"], r["to"]}, key(r.get("axis"))
            g = next((g for g in st.values() if g["kind"] == "긴장" and g["state"] in ("열림", "블랙홀")
                      and (ends & set(g["thoughts"]) or (ax and ax == key(g["axis"])))), None)
            if g is None:
                st[f"긴장:{r['id']}"] = {"kind": "긴장", "state": None, "topic": r.get("topic"), "axis": r.get("axis", ""),
                                        "relations": [r["id"]], "thoughts": sorted(ends), "size": 0,
                                        "last_day": new_day, "history": []}
                _ev(st[f"긴장:{r['id']}"], "열림", "맞서는 두 생각", new_day, **ev)
                continue
            g["relations"].append(r["id"])
            g["thoughts"] = sorted(set(g["thoughts"]) | ends)
            if new_day != g["last_day"]:   # 풀리지 않은 채 다른 날 다시 나옴
                g["size"] += 1
                g["last_day"] = new_day
                _ev(g, "블랙홀", f"풀리지 않은 채 다시 나옴({g['size']}번째)", new_day, **ev)
    return st


def press(states, relations, target, button, day=None):
    """사용자 버튼. 지켰어요 · 그만둘래요(다짐 생각 id), 맞아요 · 아니에요(관계 id). (새 상태, 새 관계 목록).
    맞지 않는 대상(닫힌 다짐 · 없는 관계 …)이면 ValueError."""
    st = copy.deepcopy(states or {})
    rels = [dict(r) for r in relations]
    if button == NO:
        if not any(r["id"] == target for r in rels):
            raise ValueError(f"관계 없음: {target}")
        rels = [r for r in rels if r["id"] != target]
        st.pop(target, None)
        for k, g in list(st.items()):
            if g["kind"] == "긴장" and target in g["relations"]:
                g["relations"].remove(target)
                if not g["relations"]:
                    del st[k]
        return st, rels
    b = BUTTONS.get(button)
    if b is None:
        raise ValueError(f"모르는 버튼: {button}")
    if b["target"] == "다짐":
        s = st.get(target)
        if not s or s["kind"] != "다짐" or s["state"] != "열림":
            raise ValueError(f"열린 다짐이 아님: {target}")
        _ev(s, b["to"], f"사용자가 '{button}'", day, button=button)
        return st, rels
    rel = next((r for r in rels if r["id"] == target), None)   # 맞아요: 점선 → 실선, 바뀜 후보 → 확정
    s = st.get(target)
    if rel is None and not s:
        raise ValueError(f"관계 없음: {target}")
    if rel:
        rel["line"], rel["needs_confirm"] = "실선", False
    if s and s["kind"] == b["target"] and s["state"] == "후보":
        _ev(s, b["to"], f"사용자가 '{button}'", day, button=button)
    return st, rels


def due_vows(states, today):
    """기한이 지났는데 열려 있는 다짐(별지기 안부 재료). 저절로 닫지 않는다."""
    return [{"thought": k, "due": s["due"], "topic": s.get("topic"), "marks": s["marks"]}
            for k, s in states.items() if s["kind"] == "다짐" and s["state"] == "열림" and s.get("due")
            and s["due"] < today]


def reask_trigger(relations, states):
    """되고 싶은 모습 '이번엔 넘어가기' 뒤 다시 물을 계기(PRD §8.0): 이번 글의 바뀜(관련 생각의 바뀜),
    또는 이미 '실수'가 있는 주제에 또 어긋남(같은 걸림돌 · 어긋남의 반복). states 는 이번 글 전 상태."""
    missed = {key(g.get("topic")) for g in (states or {}).values() if g["kind"] == "다짐" and "실수" in g.get("marks", [])}
    return any(r["type"] == "바뀜" or (r["type"] == "어긋남" and missed & {
        key(r.get("topic")), key(((states or {}).get(r["from"]) or {}).get("topic"))} - {key(None)}) for r in relations)
