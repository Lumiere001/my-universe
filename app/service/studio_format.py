"""
app/service/studio_format.py

Studio 기록 · 관측 Agent 설정 2판의 입력 HTML 만들기와 출력 JSON 읽기(순수 함수, 네트워크 · DB 없음).
여기로 들어오는 글 · 이름은 이미 가명 처리된 것이어야 한다(app/service/safety).
목록 밖 값을 바로잡는 규칙은 app/service/rules 가 한다. 여기서는 Studio 의 모양만 v8 dict 로 바꾼다.
"""

import html
import re

from app.core.ontology import choices, load

_PAGE = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{t}</title></head><body>{b}</body></html>'
_TAGGED = re.compile(r"^(.+?)\s*\((.+)\)$")   # '기타(성장)' · '감정(감사)'
_CLOSED = ("kind", "certainty", "value", "addressee")


def _e(s):
    return html.escape(str(s))


def _first(v):
    # Studio 는 값 하나도 길이 1 목록으로 돌려준다.
    if isinstance(v, list):
        v = v[0] if v else ""
    return (v or "").strip() if isinstance(v, str) else ""


def _closed(key, raw):
    """닫힌 목록 칸 하나 → {key: 값, (key_original | flags)}. 목록 밖 값은 그대로 두어 rules 가 고친다."""
    raw = (raw or "").strip()
    m = _TAGGED.match(raw)
    if raw in choices(key) or not m:
        return {key: raw}
    name, tag = m.group(1), m.group(2).strip()
    if name == "기타":   # 목록 밖 공통 규칙: 기타 + AI가 쓴 원래 말
        return {key: "기타", f"{key}_original": tag}
    if key == "kind" and tag in next(k.get("flags", []) for k in load()["kinds"] if k["name"] == name):
        return {key: name, "flags": [tag]}
    return {key: raw}


# ---------------- 기록 Agent ----------------

def record_html(title, body, known_topics=()):
    """일기 한 편 + 그 사용자의 기존 작은 별 이름 목록 → 기록 Agent 입력 HTML."""
    parts = [f"<h1>{_e(title)}</h1>"] + [f"<p>{_e(line)}</p>" for line in body.splitlines() if line.strip()]
    if known_topics:
        parts.append("<h2>참고: 기존 작은 별(일기 내용 아님)</h2><ul>"
                     + "".join(f"<li>{_e(t)}</li>" for t in known_topics) + "</ul>")
    return _PAGE.format(t=_e(title), b="".join(parts))


def parse_record(data):
    """기록 Agent 추출 JSON → {"summary", "addressee", "events", "thoughts": [생각 dict]}."""
    out = {"summary": " ".join(s.strip() for s in data.get("summary") or [] if isinstance(s, str)),
           **_closed("addressee", _first(data.get("addressee"))),
           "events": [e.strip() for e in data.get("events") or [] if isinstance(e, str) and e.strip()],
           "thoughts": []}
    for t in data.get("thoughts") or []:
        row = {"thought": _first(t.get("thought")), "quote": _first(t.get("quote")),
               "self_change": _first(t.get("self_change")), "topic": _first(t.get("topic")),
               "people": [p.strip() for p in _first(t.get("people")).split(",") if p.strip()]}
        for k in ("kind", "certainty", "value"):
            row.update(_closed(k, _first(t.get(k))))
        if row["thought"] or row["quote"]:
            out["thoughts"].append(row)
    return out


# ---------------- 관측 Agent ----------------

def _line(local_id, t, with_day):
    bits = [local_id] + ([t["day"]] if with_day else [])
    bits += [f"주제: {t['topic']}"] + ([f"해: {t['domain']}"] if t.get("domain") else [])
    bits += [t["kind"], t["certainty"], f"원문: \"{t['quote']}\""]
    if t.get("self_change"):
        bits.append(f"스스로 쓴 변화: {t['self_change']}")
    return f"<li>{_e(' · '.join(bits))}</li>"


def observe_html(today_day, today, past, aspiration=None):
    """오늘 생각 · 고른 지난 생각(관련 높은 것이 앞) · 되고 싶은 모습 → (HTML, {로컬 ID: 생각 id}).
    생각 dict: id, topic, kind, certainty, quote, (day, domain, self_change). aspiration: {"said", "value"} 또는 None."""
    ids = {f"T{i}": t["id"] for i, t in enumerate(today, 1)} | {f"P{i}": p["id"] for i, p in enumerate(past, 1)}
    rows_t = "".join(_line(f"T{i}", t, False) for i, t in enumerate(today, 1))
    rows_p = "".join(_line(f"P{i}", p, True) for i, p in enumerate(past, 1)) or "<li>없음</li>"
    asp = "<li>없음</li>"
    if aspiration and aspiration.get("said"):
        asp = f"<li>{_e(aspiration['said'])}" + (f" · 가치: {_e(aspiration['value'])}" if aspiration.get("value") else "") + "</li>"
    body = (f"<h1>관측 입력</h1><h2>오늘 글의 생각 ({_e(today_day)})</h2><ul>{rows_t}</ul>"
            f"<h2>관련 과거 생각</h2><ul>{rows_p}</ul><h2>되고 싶은 모습</h2><ul>{asp}</ul>")
    return _PAGE.format(t="관측 입력", b=body), ids


def parse_observe(data, ids):
    """관측 Agent 추출 JSON + observe_html 의 ids → v8 dict. 입력에 없는 ID 를 쓴 줄은 버리고 센다."""
    out = {"state": _first(data.get("state")), "summary": " ".join(s.strip() for s in data.get("summary") or [] if isinstance(s, str)),
           "question": _first(data.get("question")), "relations": [], "reached": [], "dropped_unknown_id": 0}
    for r in data.get("relations") or []:
        a, b = ids.get(_first(r.get("past_id"))), ids.get(_first(r.get("today_id")))
        if not a or not b or a == b:
            out["dropped_unknown_id"] += 1
            continue
        out["relations"].append({"type": _first(r.get("type")), "from": a, "to": b,
                                 **{k: _first(r.get(k)) for k in ("same_target", "topic", "evidence", "explanation", "axis")},
                                 "author_stated": _first(r.get("author_stated")) == "예"})
    for r in data.get("reached") or []:
        local = _first(r.get("thought_id"))
        if not local.startswith("T") or local not in ids:   # 닿은 순간은 오늘 생각에만
            out["dropped_unknown_id"] += 1
            continue
        out["reached"].append({"thought": ids[local], "evidence": _first(r.get("quote")), "explanation": _first(r.get("note"))})
    return out
