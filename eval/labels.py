"""
eval/labels.py — 사람이 붙이는 정답 · 판정 양식과 채점(WS23, PRD §8.3 · §8.4 E6 · E7 · §8.5 품질 루프). 외부 호출 없음.

    # E7 생각 종류 정답 양식(가치 칸 = E6) — 답하는 사람에게 AI 답을 보이지 않는다
    uv run --frozen python eval/labels.py e7-form  <AI 결과> <양식.csv> [--pred <AI 답.json>]
    uv run --frozen python eval/labels.py e7-score <양식.csv> --pred <설정#1 답.json> [--pred <설정#2 답 · 흔들림 결과>]
    # 설정 #2 거짓 연결 판정(설계 밖 관계를 맞음 · 약함 · 틀림으로)
    uv run --frozen python eval/labels.py links-form  <studio_v2_result.json> <양식.csv>
    uv run --frozen python eval/labels.py links-score <양식.csv>
    # 사람 표본 검토(골든셋 결과에서 실패 · 애매 전부 + 통과 일부)
    uv run --frozen python eval/labels.py review-form  <eval/results/….json> <양식.csv> [-n 20]
    uv run --frozen python eval/labels.py review-score <양식.csv>

AI 결과(<AI 결과>)는 1판 output/records.json, tools/stability_v2.py 결과, 또는 [{id, day, thought, quote, kind, value}] 목록.
가상 정답: eval/golden/e7_haneul.csv(가상 인물 하늘 61개 생각, 정답 A = 가상 작성자, 2026-10-14 Claude 가 AI 답을 보지 않고 붙임)
· eval/golden/e7_haneul_c1.json(설정 #1 답) · eval/golden/links_v2.csv(설정 #2 설계 밖 관계 33개 Claude 판정).
"""

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.service.rules import normalize  # noqa: E402

E7_COLS = ["id", "day", "thought", "quote", "kind_a", "value_a", "kind_b", "value_b", "note"]
LINK_COLS = ["id", "type", "from_day", "to_day", "topic", "same_target", "explanation", "verdict", "note"]
LINK_FALSE = ("약함", "틀림")
REVIEW_COLS = ["id", "category", "gate", "machine", "problems", "shown", "human", "note"]


def squash(s):
    return re.sub(r"[\s\"'“”‘’.,!?…·]", "", s or "")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, cols, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig: 엑셀 · 구글 시트에서 한글이 안 깨지게
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


##################################################
# 공통: 일치도
##################################################

def agreement(a, b):
    """두 사람(또는 사람 · AI)의 이름표 목록 → 일치율 · Cohen κ. 빈 값('')도 하나의 이름표(가치 '드러나지 않음')."""
    n = len(a)
    if not n:
        return {"n": 0, "agree": None, "kappa": None}
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return {"n": n, "agree": round(po, 3), "kappa": round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0}


##################################################
# E7 · E6: 생각 종류 · 가치
##################################################

def load_pred(path):
    """AI 결과 파일 → [{id, day, thought, quote, kind, value}] (v8 이름으로 바로잡음)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(d, dict) and "thoughts" in d and "records" in d:            # 1판 output/records.json
        rows = list(d["thoughts"].values())
    elif isinstance(d, dict) and "detail" in d:                               # tools/stability_v2.py 결과: 첫 실행
        rows = [{**t, "id": f"{r['day']}-S{i}", "day": r["day"]}
                for r in d["detail"] if r["runs"] for i, t in enumerate(r["runs"][0]["thoughts"], 1)]
    else:
        rows = d
    return [{"id": t["id"], "day": t["day"], "thought": t.get("thought", ""), "quote": t.get("quote", ""),
             "kind": normalize("kind", t.get("kind", ""))[0], "value": normalize("value", t.get("value") or "")[0]}
            for t in rows]


def match(gold, pred):
    """같은 날 글 안에서 인용으로 짝을 짓는다(설정마다 생각을 나누는 방식이 달라 id 로 못 맞춤).
    한쪽 인용이 다른 쪽을 품거나 글자 두 개 묶음 겹침이 0.5 이상이면 같은 생각. → {gold id: pred}"""
    def bigrams(s):
        return {s[i:i + 2] for i in range(len(s) - 1)} or {s}

    def score(g, p):
        a, b = squash(g["quote"] or g["thought"]), squash(p["quote"] or p["thought"])
        if not a or not b:
            return 0.0
        if a in b or b in a:
            return 1.0
        x, y = bigrams(a), bigrams(b)
        return len(x & y) / len(x | y)

    pairs = sorted(((score(g, p), g["id"], i) for g in gold for i, p in enumerate(pred) if g["day"] == p["day"]), reverse=True)
    out, used = {}, set()
    for s, gid, i in pairs:
        if s >= 0.5 and gid not in out and i not in used:
            out[gid] = pred[i]
            used.add(i)
    return out


def e7_gold(rows):
    """양식 → (정답 줄, 정답 출처). 두 사람이 모두 붙였으면 같은 줄만 정답(합의), 한 사람만이면 그 사람 답."""
    both = [r for r in rows if r["kind_a"] and r["kind_b"]]
    if both:
        return [{**r, "kind": r["kind_a"], "value": r["value_a"]} for r in both
                if r["kind_a"] == r["kind_b"] and r["value_a"] == r["value_b"]], "A · B 합의"
    return [{**r, "kind": r["kind_a"], "value": r["value_a"]} for r in rows if r["kind_a"]], "A 한 벌"


def e7_score(rows, preds):
    """rows: 양식 줄, preds: {이름: AI 답 목록}. AI 답이 있는 날의 정답만 그 설정 채점에 쓴다."""
    both = [r for r in rows if r["kind_a"] and r["kind_b"]]
    out = {"annotators": {"kind": agreement([r["kind_a"] for r in both], [r["kind_b"] for r in both]),
                          "value": agreement([r["value_a"] for r in both], [r["value_b"] for r in both])}}
    gold, source = e7_gold(rows)
    out["gold"], out["gold_source"] = len(gold), source
    for name, pred in preds.items():
        days = {p["day"] for p in pred}
        g = [r for r in gold if r["day"] in days]
        m = match(g, pred)
        hit = [(r, m[r["id"]]) for r in g if r["id"] in m]
        kind = agreement([r["kind"] for r, _ in hit], [p["kind"] for _, p in hit])
        value = agreement([r["value"] for r, _ in hit], [p["value"] for _, p in hit])
        shown = [(r, p) for r, p in hit if r["value"]]
        out[name] = {"gold": len(g), "pred": len(pred), "matched": len(hit),
                     "missed": [r["id"] for r in g if r["id"] not in m],   # 놓친 생각(정답에 있는데 AI 가 안 냄)
                     "extra": len(pred) - len(hit),                         # 정답에 없는 AI 생각(섞이거나 새로 나눔)
                     "kind_accuracy": kind["agree"], "kind_kappa": kind["kappa"],
                     "value_agreement": value["agree"], "value_kappa": value["kappa"],                   # E6
                     "value_agreement_when_shown": round(sum(r["value"] == p["value"] for r, p in shown) / len(shown), 3)
                     if shown else None,
                     "kind_confusion": Counter(f"{r['kind']} → {p['kind']}" for r, p in hit
                                               if r["kind"] != p["kind"]).most_common(8)}
    return out


##################################################
# 설정 #2 거짓 연결 판정
##################################################

def links_form_rows(result, days):
    """studio_v2_result.json 의 다른 글끼리 관계 중 설계(expected.json) 밖 것 → 판정 양식 줄."""
    exp = json.loads((ROOT / "data/virtual/expected.json").read_text(encoding="utf-8"))
    designed = {(e["past"], e["today"]) for e in exp["relations"]}
    rows = []
    for i, r in enumerate(result["relations_detail"], 1):
        a, b = days[r["from"].split("-")[0]], days[r["to"].split("-")[0]]
        if a != b and (a, b) not in designed:
            rows.append({"id": f"L{i}", "type": r["type"], "from_day": a, "to_day": b, "topic": r["topic"],
                         "same_target": r["same_target"], "explanation": r["explanation"], "verdict": "", "note": ""})
    return rows


def links_score(rows):
    judged = [r for r in rows if r["verdict"]]
    c = Counter(r["verdict"] for r in judged)
    false = sum(c[v] for v in LINK_FALSE)
    return {"off_design": len(rows), "judged": len(judged), "verdicts": dict(c),
            "false_rate": round(false / len(judged), 3) if judged else None,
            "false_by_type": dict(Counter(r["type"] for r in judged if r["verdict"] in LINK_FALSE))}


##################################################
# 사람 표본 검토
##################################################

def review_rows(result, n=20, seed=7):
    """골든셋 결과 → 실패 · 애매 전부 + 통과에서 무작위로 채워 n 줄(seed 고정, 같은 결과면 같은 표본)."""
    cases = [c for c in result["cases"] if c["status"] != "skip"]
    must = [c for c in cases if c["status"] == "fail" or c["ambiguous"]]
    rest = [c for c in cases if c not in must]
    pick = must + random.Random(seed).sample(rest, max(0, min(len(rest), n - len(must))))
    return [{"id": c["id"], "category": c["category"], "gate": c["gate"],
             "machine": c["status"] + (" (애매)" if c["ambiguous"] else ""), "problems": "; ".join(c["problems"])[:300],
             "shown": (c["detail"].get("message") or c["detail"].get("masked") or "")[:300], "human": "", "note": ""}
            for c in pick]


def review_score(rows):
    """human: 맞음(기계 판정이 맞다) · 틀림 · 애매 → 기계 판정 신뢰도."""
    done = [r for r in rows if r["human"]]
    c = Counter(r["human"] for r in done)
    return {"rows": len(rows), "reviewed": len(done), "verdicts": dict(c),
            "machine_right": round(c["맞음"] / len(done), 3) if done else None,
            "disputed": [r["id"] for r in done if r["human"] == "틀림"]}


##################################################
# 실행
##################################################

def main(argv=None):
    ap = argparse.ArgumentParser(description="정답 · 판정 양식과 채점")
    ap.add_argument("cmd", choices=["e7-form", "e7-score", "links-form", "links-score", "review-form", "review-score"])
    ap.add_argument("src")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--pred", action="append", default=[], help="AI 답 파일(여러 번 → 설정끼리 비교)")
    ap.add_argument("-n", type=int, default=20)
    a = ap.parse_args(argv)
    if a.cmd == "e7-form":
        pred = load_pred(a.src)
        write_csv(a.out, E7_COLS, [{k: t[k] for k in ("id", "day", "thought", "quote")} for t in pred])
        if a.pred:
            Path(a.pred[0]).write_text(json.dumps(pred, ensure_ascii=False, indent=1), encoding="utf-8")
        res = {"form": a.out, "rows": len(pred)}
    elif a.cmd == "e7-score":
        res = e7_score(read_csv(a.src), {Path(p).stem: load_pred(p) for p in a.pred})
    elif a.cmd == "links-form":
        import importer
        recs = importer.from_instagram_zip((ROOT / "data/virtual/instagram-virtual-haneul.zip").read_bytes())
        rows = links_form_rows(json.loads(Path(a.src).read_text(encoding="utf-8")), {r["id"]: r["day"] for r in recs})
        write_csv(a.out, LINK_COLS, rows)
        res = {"form": a.out, "rows": len(rows)}
    elif a.cmd == "links-score":
        res = links_score(read_csv(a.src))
    elif a.cmd == "review-form":
        rows = review_rows(json.loads(Path(a.src).read_text(encoding="utf-8")), a.n)
        write_csv(a.out, REVIEW_COLS, rows)
        res = {"form": a.out, "rows": len(rows)}
    else:
        res = review_score(read_csv(a.src))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    main()
