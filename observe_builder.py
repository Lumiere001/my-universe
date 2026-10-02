"""
observe_builder.py

관측 Agent에 보낼 비교 입력 HTML을 만든다 (HR 예시의 matching_builder에 해당).
오늘 글의 생각은 T1, T2 …, 관련 과거 생각은 P1, P2 … 로 번호를 붙인다.
"""

import html


def _line(local_id, t, with_day):
    bits = [local_id]
    if with_day:
        bits.append(t["day"])
    bits += [t["topic"], t["kind"], t["certainty"], f"원문: \"{t['quote']}\""]
    if t.get("self_change"):
        bits.append(f"스스로 쓴 변화: {t['self_change']}")
    return f"<li>{html.escape(' · '.join(bits))}</li>"


def build(today_day, today, past):
    """today, past: 생각 dict 목록. (HTML, {로컬 ID: 생각 ID}) 를 돌려준다."""
    ids = {}
    rows_t, rows_p = [], []
    for i, t in enumerate(today, 1):
        ids[f"T{i}"] = t["id"]
        rows_t.append(_line(f"T{i}", t, False))
    for i, p in enumerate(past, 1):
        ids[f"P{i}"] = p["id"]
        rows_p.append(_line(f"P{i}", p, True))
    body = (f"<h1>관측 입력</h1><h2>오늘 글의 생각 ({today_day})</h2><ul>{''.join(rows_t)}</ul>"
            f"<h2>관련 과거 생각</h2><ul>{''.join(rows_p) or '<li>없음</li>'}</ul>")
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>관측 입력</title></head>'
            f"<body>{body}</body></html>"), ids
