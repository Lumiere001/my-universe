"""가상 데이터 평가: 글을 쓸 때 심어 둔 관계(expected.json)를 우주가 얼마나 찾았는지 잰다.

    python tools/eval_virtual.py      # output/records.json 을 읽어 data/ops/eval_virtual.json 에 쓴다

설계해 둔 관계 목록은 정답의 전부가 아니다. 그래서 정밀도는 재지 않고 재현율과 종류 일치, 금지 관계만 본다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import runlog  # noqa: E402

state = json.loads((config.OUTPUT_DIR / "records.json").read_text(encoding="utf-8"))
expected = json.loads((config.DATA_DIR / "virtual" / "expected.json").read_text(encoding="utf-8"))
day = {rid: r["day"] for rid, r in state["records"].items()}
rels = [r for r in state["relations"] if r["from_record"] != r["to_record"]]


def between(past, today):
    return [r for r in rels if day[r["from_record"]] == past and day[r["to_record"]] == today]


rows = []
for e in expected["relations"]:
    found = between(e["past"], e["today"])
    same = [r for r in found if r["type"] == e["type"]]
    rows.append({**e, "found_pair": bool(found), "found_type": bool(same),
                 "got": [f"{r['type']}·{r['line']}" for r in found],
                 "line_ok": bool(same) and any(r["line"] == e["line"] for r in same)})
negatives = [{**n, "violated": any(r["type"] == n["type"] for r in between(n["past"], n["today"]))} for n in expected["not_relations"]]

logs = [l for l in runlog.read(5000) if l["step"] in ("record", "observe") and not l.get("cached")]
reports = state["reports"].values()
out = {
    "designed_relations": len(rows),
    "pair_recall": round(sum(r["found_pair"] for r in rows) / len(rows), 3),
    "type_recall": round(sum(r["found_type"] for r in rows) / len(rows), 3),
    "line_agreement_on_found": round(sum(r["line_ok"] for r in rows) / max(sum(r["found_type"] for r in rows), 1), 3),
    "by_type": {t: f"{sum(r['found_type'] for r in rows if r['type'] == t)}/{sum(1 for r in rows if r['type'] == t)}"
                for t in dict.fromkeys(r["type"] for r in rows)},
    "negatives_violated": sum(n["violated"] for n in negatives),
    "all_relations_found": len(rels),
    "gates": {
        "G1_dropped_quotes": sum(r["gates"]["G1_dropped_quotes"] for r in reports),
        "G2_date_problems": sum(not r["gates"]["G2_date_ok"] for r in reports),
        "G3_rewritten": sum(r["gates"].get("G3_rewritten", 0) for r in reports),
        "G4_names_masked_in_output": len(state["names"]),
        "G4_names_leaked_in_report": 0,
    },
    "cost_latency": {
        "studio_jobs": len(logs),
        "avg_seconds_record_agent": round(sum(l["seconds"] for l in logs if l["step"] == "record") / max(sum(l["step"] == "record" for l in logs), 1), 1),
        "avg_seconds_observe_agent": round(sum(l["seconds"] for l in logs if l["step"] == "observe") / max(sum(l["step"] == "observe" for l in logs), 1), 1),
        "est_cost_usd": round(sum(l["est_cost"] for l in logs), 2),
        "est_cost_per_record_usd": round(sum(l["est_cost"] for l in logs) / max(len(state["records"]), 1), 3),
    },
    "detail": rows, "negative_detail": negatives,
}

# G4: 화면 · 보고서용 결과에 이름이 남았는지 직접 확인
import service  # noqa: E402
leaks = 0
for rid in state["reports"]:
    text = json.dumps(service.view_report(state, rid), ensure_ascii=False)
    leaks += sum(text.count(n) for n in expected["names"])
out["gates"]["G4_names_leaked_in_report"] = leaks

(config.DATA_DIR / "ops").mkdir(parents=True, exist_ok=True)
(config.DATA_DIR / "ops" / "eval_virtual.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k not in ("detail", "negative_detail")}, ensure_ascii=False, indent=2))
for r in rows:
    print(("✓" if r["found_type"] else ("~" if r["found_pair"] else "✗")), r["type"], r["past"], "→", r["today"], r["got"])
for n in negatives:
    print("금지", "✗ 위반" if n["violated"] else "✓ 지킴", n["type"], n["past"], "→", n["today"])
