"""
가상 인물 하늘 데이터를 v8 규칙으로 다시 돌려 v7 결과와 비교한다(WS3). 외부 호출 없음(저장된 벡터만 씀).

읽기만: data/demo/universe-haneul.json(v7 결과 · 생각 벡터), data/virtual/expected.json(심어 둔 관계),
        runs/cache/*.json 중 하늘 보고서의 job_id 와 맞는 관측 Agent 출력(원래 관계 후보).
쓰기: docs/ws3-haneul-reprocess.md

    uv run --frozen python scripts/reprocess_haneul.py
"""

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.service.rules import (advance, clean_record, filter_relations, pick_past,  # noqa: E402
                               universe_view)
from app.service.rules.topics import cos  # noqa: E402

CACHE = Path("/Users/east_star/Projects/my-universe/runs/cache")
OUT = ROOT / "docs" / "ws3-haneul-reprocess.md"
V7 = {"theta": 0.75, "limit": 10}   # v7 pick_past 숫자(비교용으로 그때 입력을 되살리는 데만 씀)


def load():
    demo = json.loads((ROOT / "data/demo/universe-haneul.json").read_text())
    expected = json.loads((ROOT / "data/virtual/expected.json").read_text())
    jobs = {rep["run"]["observe_agent"]["job_id"]: rid for rid, rep in demo["reports"].items()
            if "observe_agent" in rep.get("run", {})}
    observe = {}
    for f in sorted(CACHE.glob("*.json")) if CACHE.exists() else []:
        d = json.loads(f.read_text())
        if d.get("meta", {}).get("job_id") in jobs:   # 하늘 보고서와 맞는 것만
            observe[jobs[d["meta"]["job_id"]]] = d["data"]
    return demo, expected, observe


def v7_past(seen, today):
    """v7 pick_past 를 그대로 되살려 관측 입력의 P 번호를 복원한다(유사도 0.75 · 가산점 · 날짜순)."""
    hubs, topics = {t["hub"] for t in today}, {t["topic"] for t in today}
    scored = []
    for p in seen:
        sim = max(cos(t["emb"], p["emb"]) for t in today)
        if p["hub"] in hubs or sim >= V7["theta"]:
            scored.append((sim + (0.15 if p["topic"] in topics else 0) + (0.05 if p["hub"] in hubs else 0), p))
    scored.sort(key=lambda x: -x[0])
    return sorted([p for _, p in scored[:V7["limit"]]], key=lambda p: p["day"])


def _squash(s):
    return re.sub(r"[\s.,!?'\"“”‘’…]", "", s or "")


def quoted(expl, a, b):
    """관측 설정 #1에는 '원문 인용' 칸이 없어, 설명에 두 생각 중 하나의 원문 조각(6자 이상)이 있으면 인용으로 본다."""
    e = _squash(expl)
    return any(len(q) >= 6 and any(q[i:i + 6] in e for i in range(len(q) - 5)) for q in (_squash(a["quote"]), _squash(b["quote"])))


def main():
    demo, expected, observe = load()
    th7, rec7 = demo["thoughts"], demo["records"]
    names = sorted(set(demo.get("names", [])) | set(expected.get("names", [])))
    center = [sum(c) / len(th7) for c in zip(*(t["emb"] for t in th7.values()))]   # 이 사용자 생각 벡터의 평균

    th8, topics, rels8, states, records = {}, {}, [], {}, {}
    cand_all, dropped_all, past_cmp, fidelity = [], [], [], [0, 0]
    kinds_fixed, problems = Counter(), Counter()
    seen7 = []
    for rid in demo["order"]:
        r = rec7[rid]
        records[rid] = {"id": rid, "day": r["day"]}
        today7 = [th7[i] for i in r.get("thought_ids", [])]
        # 1) 생각 표 정리(v7 생각 → v8 칸)
        raw = {"summary": r.get("summary", ""), "addressee": r.get("meta", {}).get("addressee", []),
               "events": r.get("meta", {}).get("events", []),
               "thoughts": [{**t, "people": [n for n in names if n in t["thought"] + t["quote"]]} for t in today7]}
        clean = clean_record(raw, topics=topics)
        for t7, t in zip(today7, clean["thoughts"]):
            if t7["kind"] != t["kind"] or t7["certainty"] != t["certainty"]:
                kinds_fixed[f"{t7['kind']}/{t7['certainty']} → {t['kind']}/{t['certainty']}"] += 1
            for p in t["problems"]:
                problems[f"{p}: {t['topic']}"] += 1
            th8[t7["id"]] = {**t, "id": t7["id"], "record_id": rid, "day": r["day"], "emb": t7["emb"]}
            if not t["problems"]:
                topics.setdefault(t["topic"], t["domain"])
        today8 = [th8[t["id"]] for t in today7]
        # 2) 지난 생각 고르기: v7(복원) vs v8
        if today7 and seen7:
            p7 = v7_past(seen7, today7)
            p8 = pick_past(today8, [th8[p["id"]] for p in seen7], center=center)
            lim = re.search(r"과거 생각 (\d+)개", " ".join(demo["reports"][rid].get("limits", [])))
            fidelity[0] += 1
            fidelity[1] += bool(lim and int(lim[1]) == len(p7))
            past_cmp.append((rid, r["day"], len(p7), len(p8), len({p["id"] for p in p7} & {p["id"] for p in p8})))
            # 3) 관측 Agent 관계 후보(v7 입력 번호로 복원) → v8 규칙
            ids = {f"T{i}": t["id"] for i, t in enumerate(today7, 1)} | {f"P{i}": p["id"] for i, p in enumerate(p7, 1)}
            cands = []
            for c in (observe.get(rid) or {}).get("relations", []):
                a, b = ids.get((c.get("past_id") or "").strip()), ids.get((c.get("today_id") or "").strip())
                q = bool(a and b) and quoted(c.get("explanation", ""), th8[a], th8[b])
                cands.append({**c, "a": a, "b": b, "quoted": q, "record": rid})
            cand_all += cands
            kept, dropped = filter_relations(cands, th8, states)
            rels8 += kept
            dropped_all += [{**d, "record": rid} for d in dropped]
            states = advance(states, th8, kept, rid)
        else:
            states = advance(states, th8, [], rid)
        seen7 += today7
    view = universe_view(records, th8, rels8, states)
    write(demo, expected, observe, th8, rels8, dropped_all, cand_all, states, view, past_cmp, fidelity,
          kinds_fixed, problems)


def states_of(states, d1, d2, th):
    """두 날짜 사이 바뀜 관계의 상태."""
    return ", ".join(s["state"] for s in states.values() if s["kind"] == "바뀜"
                     and th[s["from"]]["day"] == d1 and th[s["to"]]["day"] == d2) or "없음"


def _rel_key(rel, th):
    return rel["type"], th[rel["from"]]["day"], th[rel["to"]]["day"]


def write(demo, expected, observe, th8, rels8, dropped, cands, states, view, past_cmp, fidelity, kinds_fixed, problems):
    rels7, th7 = demo["relations"], demo["thoughts"]
    c7 = Counter((r["type"], r["line"]) for r in rels7)
    c8 = Counter((r["type"], r["line"]) for r in rels8)
    types = ["이어짐", "바뀜", "긴장", "해소", "어긋남", "목표 충돌"]
    L = ["# WS3 하늘 데이터 v8 재처리 결과", "",
         f"만든 날 {date.today().isoformat()} · `uv run --frozen python scripts/reprocess_haneul.py` 로 다시 만든다. "
         "외부 호출 0회(저장된 생각 벡터만 씀).", "",
         "## 무엇을 했나", "",
         f"- 입력: 가상 인물 하늘의 v7 결과(`data/demo/universe-haneul.json`, 글 {len(demo['records'])}편 · 생각 {len(th7)}개 · "
         f"관계 {len(rels7)}개)와, 하늘 보고서의 job_id 와 맞는 관측 Agent 1차 출력 {len(observe)}개(`runs/cache`, 읽기만).",
         f"- 관측 입력 번호(P1 …)는 v7 pick_past 를 되살려 복원했다. 보고서에 적힌 비교 개수와 맞은 글: {fidelity[1]}/{fidelity[0]}.",
         f"- 관계 후보 {len(cands)}개(관측 Agent가 낸 그대로)를 v8 규칙(`app/service/rules`)으로 다시 걸렀다. "
         "생각은 v8 칸으로 정리(clean_record)하고 상태 모델을 글 순서대로 밀었다(advance).",
         "- 관측 설정 #1에는 '원문 인용' 칸이 없어서, 설명에 두 생각의 원문 조각(6자 이상)이 들어 있으면 인용으로 보았다"
         "(영역을 넘는 관계의 근거 판정에만 쓰임). 설정 #2(WS2)부터는 관측 Agent가 직접 낸다.", "",
         "## 읽는 법", "",
         "- 관계가 늘어난 주된 까닭: v7은 같은 두 **글** 사이 관계를 하나만 남기고 기간(7 · 14 · 30일)으로 버렸고, "
         "v8은 같은 두 **생각** 사이 하나만 남기고 기간 조건이 없다(2026-10-03 결정).",
         "- v7에서 남았지만 v8에서 버린 것은 v8 정의로 맞지 않는 것이다(감정 → 감정 어긋남, 다짐 → 신념 어긋남, 단정 아닌 해소, "
         "다른 주제의 해소, 근거 없는 영역 넘는 긴장).",
         "- PRD 예시 4/5 '혼자가 편하다' → 4/12 '어느 쪽이 진짜 나일까'는 v7에서 바뀜(실선)으로 바로 굳었지만, "
         f"v8에서는 새 생각이 열린 질문이라 바뀜 **{states_of(states, '2026-04-05', '2026-04-12', th8)}**로 남는다.", "",
         "## 관계 종류별 개수 (v7 → v8)", "", "| 관계 | v7 실선 | v7 점선 | v8 실선 | v8 점선 |", "| --- | --- | --- | --- | --- |"]
    for t in types:
        L.append(f"| {t} | {c7[(t, '실선')]} | {c7[(t, '점선')]} | {c8[(t, '실선')]} | {c8[(t, '점선')]} |")
    L.append(f"| 합계 | {sum(v for (_, l), v in c7.items() if l == '실선')} | {sum(v for (_, l), v in c7.items() if l == '점선')} "
             f"| {sum(v for (_, l), v in c8.items() if l == '실선')} | {sum(v for (_, l), v in c8.items() if l == '점선')} |")
    cross = [r for r in rels8 if r["cross_domain"]]
    L += ["", f"- v8 영역을 넘는 선: {len(cross)}개(행성을 눌렀을 때만 보임), 그중 사용자 확인 필요(다른 날 점선) "
              f"{sum(r['needs_confirm'] for r in cross)}개.",
          f"- v8에서 규칙이 종류를 바꾼 관계: {sum(bool(r['notes']) for r in rels8)}개 — "
          + ", ".join(f"{n} {k}" for k, n in Counter(x.split('(')[0] for r in rels8 for x in r['notes']).most_common()), ""]
    L += ["## 걸러진 관계와 이유 (v8)", "", "| 이유 | 개수 |", "| --- | --- |"]
    for reason, n in Counter(d["reason"] for d in dropped).most_common():
        L.append(f"| {reason} | {n} |")
    k7 = Counter(_rel_key(r, th7) for r in rels7)
    k8 = Counter(_rel_key(r, th8) for r in rels8)
    pair7 = {(r["from"], r["to"]): r["type"] for r in rels7}
    pair8 = {(r["from"], r["to"]): r["type"] for r in rels8}
    L += ["", "## v7과 달라진 관계", "", "| 두 생각(날짜) | 주제 | v7 | v8 | 이유 |", "| --- | --- | --- | --- | --- |"]
    why = {}
    for d in dropped:
        c = d["cand"]
        a, b = c.get("from") or c.get("a"), c.get("to") or c.get("b")
        if a and b:
            why.setdefault(tuple(sorted([a, b], key=lambda i: (th8[i]["day"], i))), d["reason"])
    for pair in sorted(set(pair7) | set(pair8), key=lambda p: (th8[p[0]]["day"], th8[p[1]]["day"], p)):
        if pair7.get(pair) != pair8.get(pair):
            a, b = th8[pair[0]], th8[pair[1]]
            note = "; ".join(next((r["notes"] for r in rels8 if (r["from"], r["to"]) == pair), [])) or why.get(pair, "v7 규칙에서 버림(기간 · 같은 글 쌍 하나)")
            L.append(f"| {a['day']} {a['id'].split('-')[-1]} → {b['day']} {b['id'].split('-')[-1]} | {b['topic']} | {pair7.get(pair, '-')} | {pair8.get(pair, '-')} | {note} |")
    L += ["", "## 심어 둔 관계(expected.json) 대조", "", "| 관계 | 날짜 | 주제 | v7 | v8 |", "| --- | --- | --- | --- | --- |"]
    for e in expected["relations"]:
        k = (e["type"], e["past"], e["today"])
        L.append(f"| {e['type']} | {e['past']} → {e['today']} | {e['topic']} | {'있음' if k7[k] else '없음'} | {'있음' if k8[k] else '없음'} |")
    for e in expected.get("not_relations", []):
        k = (e["type"], e["past"], e["today"])
        L.append(f"| (아니어야 함) {e['type']} | {e['past']} → {e['today']} | {e['topic']} | {'잘못 있음' if k7[k] else '없음(맞음)'} | {'잘못 있음' if k8[k] else '없음(맞음)'} |")
    sc = Counter((s["kind"], s["state"]) for s in states.values())
    marks = sum("실수" in s.get("marks", []) for s in states.values())
    L += ["", "## 상태 · 블랙홀 · 고리 (v8, v7에는 상태가 없음)", "", "| 대상 | 상태 | 개수 |", "| --- | --- | --- |"]
    for (k, s), n in sorted(sc.items()):
        L.append(f"| {k} | {s} | {n} |")
    L += [f"| 다짐 | '실수' 표시 | {marks} |", "",
          f"- 블랙홀(오래 머문 고민): {len(view['black_holes'])}개, 크기 " + (", ".join(f"{b['axis'] or b['topic']} {b['size']}" for b in view["black_holes"]) or "-"),
          f"- 쌍행성(열린 긴장 묶음): {len(view['binaries'])}개",
          f"- 금빛 고리: 열림 {sum(p['ring'] == '열림' for p in view['planets'])}개 행성, 채워짐 {sum(p['ring'] == '채워짐' for p in view['planets'])}개 행성",
          f"- 해: {', '.join(s['name'] for s in view['suns'])} / 숨긴 기준 축: {', '.join(view['hidden_axes'])}",
          f"- 작은 별 {len(view['stars'])}개, 사람별 행성: " + (", ".join(f"{n} {len(v)}개" for n, v in view["people"].items()) or "없음"), "",
          "## 생각 표 정리 (v7 → v8 칸)", "", "| 바뀐 것 | 개수 |", "| --- | --- |"]
    for k, n in kinds_fixed.most_common():
        L.append(f"| {k} | {n} |")
    L += ["", "| 주제 문제(해 이름 금지, 고치지 못해 표시) | 개수 |", "| --- | --- |"]
    for k, n in problems.most_common():
        L.append(f"| {k} | {n} |")
    L += ["", "v7 기록 Agent(설정 #1)는 기존 작은 별 목록을 입력으로 받지 않아 해 이름(관계 · 건강 · 공동체)을 주제로 썼다. "
              "v8에서는 표시만 하고 그대로 두었다(같은 해에 다른 작은 별이 하나뿐일 때만 그 이름으로 고침). "
              "판단형 관계가 '같은 주제' 조건을 쓰므로, 설정 #2에서 주제가 구체적이 되면 결과가 다시 달라진다.", "",
          "## 지난 생각 고르기 (v7 복원 vs v8)", "",
          "| 글 날짜 | v7 개수 | v8 개수 | 겹침 |", "| --- | --- | --- | --- |"]
    for _, day, n7, n8, both in past_cmp:
        L.append(f"| {day} | {n7} | {n8} | {both} |")
    if past_cmp:
        L.append(f"| 평균 | {sum(x[2] for x in past_cmp) / len(past_cmp):.1f} | {sum(x[3] for x in past_cmp) / len(past_cmp):.1f} | "
                 f"{sum(x[4] for x in past_cmp) / len(past_cmp):.1f} |")
    L += ["", "관측 Agent 후보는 v7 입력으로 만든 것이라, v8 입력으로 고른 지난 생각과의 관계는 다시 돌려야 알 수 있다(WS2 · WS5에서 설정 #2로).", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: v7 {len(rels7)} → v8 {len(rels8)} relations, dropped {len(dropped)}")


if __name__ == "__main__":
    main()
