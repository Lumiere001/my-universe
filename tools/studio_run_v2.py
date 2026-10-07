"""하늘 가상 데이터로 Studio 설정 2판을 돌리고 1판과 같은 잣대로 잰다(WS2 비교표 재료).

    uv run --frozen python tools/studio_run_v2.py v1                  # 1판 결과(output/records.json, 읽기만)를 잰다
    uv run --frozen python tools/studio_run_v2.py dry                 # 네트워크 없이 입력 HTML 만 만들어 본다
    RECORD_CONFIG_ID=2 OBSERVE_CONFIG_ID=2 uv run --frozen python tools/studio_run_v2.py run --limit 2   # 유료

run 은 호출 묶음마다 runs/cost_ledger.jsonl 에 한 줄을 덧붙이고, 결과를 runs/studio_v2_result.json 에 쓴다.
.env 는 고치지 않는다. 설정 번호는 실행할 때 환경변수로 덮어쓴다.
"""
import collections
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.core.ontology import choices, load  # noqa: E402
from app.service import studio_format as sf  # noqa: E402

MAIN = Path("/Users/east_star/Projects/my-universe")       # 1판 결과 · 원장은 본 저장소에 있다(읽기 · 덧붙이기만)
LEDGER = MAIN / "runs" / "cost_ledger.jsonl"
EXPECTED = json.loads((ROOT / "data" / "virtual" / "expected.json").read_text(encoding="utf-8"))
PER_RUN_USD = 0.05   # HTML 1쪽 = Parse $0.01 + Extract $0.04 (PRD §5.7)


def records():
    import importer
    # 1판 기준선과 같은 29편(인스타 ZIP). 하늘-2026-10-03.txt 은 1판 평가에 없어 넣지 않는다.
    recs = importer.from_instagram_zip((ROOT / "data" / "virtual" / "instagram-virtual-haneul.zip").read_bytes())
    return sorted(recs, key=lambda r: (r["day"], r["written_at"]))


def pseudonymize(text):
    # ponytail: 가상 인물 이름만 바꾼다. 실제 가명 처리는 WS4(app/service/safety)가 맡는다.
    for i, n in enumerate(EXPECTED["names"], 1):
        text = text.replace(n, f"사람{i}")
    return text


def pick_past(past, today, limit):
    # ponytail: 같은 세부 주제 먼저, 그다음 최근 순. 1판은 유사도 순이었으니 비교 때 차이로 적는다. WS3 고르기로 바꿀 것.
    topics = {t["topic"] for t in today}
    recent = past[::-1]
    return ([p for p in recent if p["topic"] in topics] + [p for p in recent if p["topic"] not in topics])[:limit]


def metrics(days, thoughts, relations):
    """days {기록 id: 날짜}, thoughts [{topic, kind}], relations [{type, from_record, to_record, (same_target)}] → 비교표 숫자."""
    domains = set(choices("domains"))
    cross = [r for r in relations if r["from_record"] != r["to_record"]]
    designed = {(e["past"], e["today"]) for e in EXPECTED["relations"]}

    def between(past, today):
        return [r for r in cross if days[r["from_record"]] == past and days[r["to_record"]] == today]

    hits = [(bool(between(e["past"], e["today"])), any(r["type"] == e["type"] for r in between(e["past"], e["today"])))
            for e in EXPECTED["relations"]]
    return {
        "thoughts": len(thoughts),
        "kinds": dict(collections.Counter(t["kind"] for t in thoughts).most_common()),
        "kinds_out_of_list": sum(t["kind"] not in choices("kinds") for t in thoughts),
        "topics": len({t["topic"] for t in thoughts}),
        "topics_domain_name": sorted({t["topic"] for t in thoughts if t["topic"] in domains}),
        "relations_all": len(relations), "relations_cross_record": len(cross),
        "relations_off_design": sum((days[r["from_record"]], days[r["to_record"]]) not in designed for r in cross),
        "relations_without_same_target": sum(not r.get("same_target") for r in cross) if relations and "same_target" in relations[0] else None,
        "expected_pair": f"{sum(p for p, _ in hits)}/{len(hits)}", "expected_type": f"{sum(t for _, t in hits)}/{len(hits)}",
        "negatives_violated": sum(any(r["type"] == n["type"] for r in between(n["past"], n["today"])) for n in EXPECTED["not_relations"]),
    }


def v1():
    s = json.loads((MAIN / "output" / "records.json").read_text(encoding="utf-8"))
    days = {rid: r["day"] for rid, r in s["records"].items()}
    out = metrics(days, list(s["thoughts"].values()), s["relations"])
    out["G1_dropped_quotes"] = sum(r["gates"]["G1_dropped_quotes"] for r in s["reports"].values())
    return out


def ledger(what, calls):
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "ws": "WS2", "what": what,
                            "calls": calls, "est_usd": round(calls * PER_RUN_USD, 3)}, ensure_ascii=False) + "\n")


def run(limit=None, dry=False):
    import gates
    if not dry:
        from agent_client import AgentClient
        rec_agent = AgentClient(os.environ["RECORD_AGENT_ID"], os.environ["RECORD_CONFIG_ID"], "기록 Agent v2")
        obs_agent = AgentClient(os.environ["OBSERVE_AGENT_ID"], os.environ["OBSERVE_CONFIG_ID"], "관측 Agent v2")
    recs = records()[:limit]
    days, thoughts, relations, metas, g1, known = {}, [], [], [], 0, []
    for rec in recs:
        rid, source = rec["id"], pseudonymize(rec["title"] + "\n" + rec["body"])
        days[rid] = rec["day"]
        html = sf.record_html(pseudonymize(rec["title"]), pseudonymize(rec["body"]), known)
        if dry:
            print(rid, rec["day"], len(html), "자", f"기존 작은 별 {len(known)}개")
            continue
        _, data, m1 = rec_agent.run_html(html, use_cache=False)
        metas.append(m1)
        r = sf.parse_record(data)
        today = []
        for i, t in enumerate(r["thoughts"], 1):
            if not gates.quote_in_source(t["quote"], source):
                g1 += 1
                continue
            today.append({**t, "id": f"{rid}-T{i}", "record_id": rid, "day": rec["day"]})
        known += [t["topic"] for t in today if t["topic"] not in known]
        if today:
            ohtml, ids = sf.observe_html(rec["day"], today, pick_past(thoughts, today, load()["limits"]["past_thoughts_max"]))
            _, odata, m2 = obs_agent.run_html(ohtml, use_cache=False)
            metas.append(m2)
            rec_of = {t["id"]: t["record_id"] for t in thoughts + today}
            for rel in sf.parse_observe(odata, ids)["relations"]:
                relations.append({**rel, "from_record": rec_of[rel["from"]], "to_record": rec_of[rel["to"]]})
        thoughts += today
        ledger(f"Studio 2판 하늘 {rec['day']} 기록{'+관측' if today else ''}", 2 if today else 1)
        print(rid, rec["day"], f"생각 {len(today)}", f"관계 누적 {len(relations)}", flush=True)
    if dry:
        return None
    out = metrics(days, thoughts, relations)
    out.update(G1_dropped_quotes=g1, records=len(recs), studio_jobs=len(metas),
               avg_seconds={a: round(sum(m["seconds"] for m in metas if m["agent"] == a) / max(sum(m["agent"] == a for m in metas), 1), 1)
                            for a in ("기록 Agent v2", "관측 Agent v2")},
               est_cost_usd=round(len(metas) * PER_RUN_USD, 2),
               config={"record": os.environ["RECORD_CONFIG_ID"], "observe": os.environ["OBSERVE_CONFIG_ID"]},
               relations_detail=[{k: r[k] for k in ("type", "from", "to", "same_target", "topic", "explanation")} for r in relations],
               topics_list=sorted({t["topic"] for t in thoughts}))
    (MAIN / "runs" / "studio_v2_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dry"
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    t0 = time.time()
    res = v1() if cmd == "v1" else run(lim, dry=(cmd == "dry"))
    if res:
        print(json.dumps({k: v for k, v in res.items() if k not in ("relations_detail",)}, ensure_ascii=False, indent=2))
    print(f"{time.time() - t0:.1f}s")
