"""흔들림 측정 (Ops): 같은 글을 여러 번 돌려 결과가 얼마나 같은지 잰다.

    python tools/stability.py           # 기록 Agent: 글 3편 × 3번 → data/ops/stability.json

Studio가 같은 파일을 캐시할 수 있어서, 실행마다 보이지 않는 표시(meta 태그)를 달아 파일을 다르게 만든다.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import importer  # noqa: E402
from agent_client import record_agent  # noqa: E402

PICK = ["9/20", "4/12", "6/14"]   # 변화 서술 · 긴장 · 이어진 게시물
RUNS = 3

recs = importer.from_instagram_zip(config.VIRTUAL_ZIP.read_bytes())
targets = [next(r for r in recs if r["title"].startswith(p)) for p in PICK]
squash = lambda s: re.sub(r"\s+", "", s or "")

results = []
for rec in targets:
    html = importer.to_html(rec)
    runs = []
    for n in range(RUNS):
        h = html.replace("<head>", f'<head><meta name="run" content="stability-{n}">')
        label, data, meta = record_agent.run_html(h, use_cache=False)
        th = data.get("thoughts") or []
        runs.append({"type": label, "n": len(th), "kinds": sorted(t.get("kind", "") for t in th),
                     "quotes": {squash(t.get("quote")) for t in th}, "seconds": meta["seconds"], "studio_cached": meta.get("studio_cached")})
    base = runs[0]
    jacc = [len(base["quotes"] & r["quotes"]) / max(len(base["quotes"] | r["quotes"]), 1) for r in runs[1:]]
    results.append({
        "record": rec["title"],
        "type_same": len({r["type"] for r in runs}) == 1,
        "thought_counts": [r["n"] for r in runs],
        "kinds_same": len({tuple(r["kinds"]) for r in runs}) == 1,
        "kind_counts": [dict(Counter(r["kinds"])) for r in runs],
        "quote_overlap_vs_first": [round(j, 2) for j in jacc],
        "seconds": [r["seconds"] for r in runs],
        "studio_cached": [r["studio_cached"] for r in runs],
    })
    print(results[-1])

summary = {
    "agent": "기록 Agent", "config_id": config.RECORD_CONFIG_ID, "records": len(results), "runs_each": RUNS,
    "type_agreement": f"{sum(r['type_same'] for r in results)}/{len(results)}",
    "thought_count_agreement": f"{sum(len(set(r['thought_counts'])) == 1 for r in results)}/{len(results)}",
    "kind_agreement": f"{sum(r['kinds_same'] for r in results)}/{len(results)}",
    "mean_quote_overlap": round(sum(sum(r["quote_overlap_vs_first"]) for r in results) / (len(results) * (RUNS - 1)), 2),
    "detail": results,
}
(config.DATA_DIR / "ops").mkdir(parents=True, exist_ok=True)
(config.DATA_DIR / "ops" / "stability.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in summary.items() if k != "detail"}, ensure_ascii=False, indent=2))
