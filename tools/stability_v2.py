"""흔들림 측정 2판(WS23, PRD §8.5 F): 서비스와 같은 길(app/agents/studio.py, 설정 V8_RECORD_CONFIG_ID)로
같은 글을 여러 번 돌려 기록 Agent 결과가 얼마나 같은지 잰다. 1판 도구(tools/stability.py)는 그대로 둔다.

    uv run --frozen python tools/stability_v2.py          # 유료: 하늘 3편 × 3번 = Studio 9번(약 $0.45), 설정 V8_RECORD_CONFIG_ID
    uv run --frozen python tools/stability_v2.py --record-config 3   # 품질 3판: 설정 번호를 정해 같은 측정(원장 갈래 Q3-흔들림)
    uv run --frozen python tools/stability_v2.py --dry    # 네트워크 없이 입력만 확인

가상 인물 하늘의 글만, 서비스처럼 가명 처리(tools.mask_obj) 뒤 보낸다(llm.guard 가 보내기 직전 실명 검사).
Studio 가 같은 파일을 캐시할 수 있어 실행마다 보이지 않는 meta 표시를 단다.
실행마다 runs/cost_ledger.jsonl(원본 저장소)에 한 줄, 결과는 eval/results/<날짜>-stability-v2.json
(--record-config N 이면 <날짜>-stability-cN.json).
"""
import json
import re
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.agents import studio, tools  # noqa: E402
from app.core import config, llm  # noqa: E402
from app.service import studio_format as sf  # noqa: E402

MAIN = Path("/Users/east_star/Projects/my-universe")       # 원장은 본 저장소(git 제외)
LEDGER = MAIN / "runs" / "cost_ledger.jsonl"
PICK = ["9/20", "4/12", "6/14"]   # 1판 기준선과 같은 3편: 변화 서술 · 긴장 · 이어진 게시물
RUNS, CAP_USD = 3, 1.0
WS, OUT_NAME = "WS23", "stability-v2"   # --record-config 를 주면 Q3-흔들림 · stability-c<번호>(상한도 그 갈래에 따로)
PEOPLE = [{"id": f"P{i}", "name": n, "nicknames": [], "relation": "친구"}
          for i, n in enumerate(json.loads((ROOT / "data/virtual/expected.json").read_text(encoding="utf-8"))["names"], 1)]
squash = lambda s: re.sub(r"\s+", "", s or "")   # noqa: E731


def targets():
    import importer
    recs = importer.from_instagram_zip((ROOT / "data/virtual/instagram-virtual-haneul.zip").read_bytes())
    return [next(r for r in recs if r["title"].startswith(p)) for p in PICK]


def once(rec, n):
    """서비스 run_record_agent 와 같은 길 + meta 표시. → (parse_record 결과 | None, 호출 수, 추정 $, 오류 코드).
    Studio 가 실패해도(시간 초과 등) 부른 횟수 · 비용은 돌려줘 원장에 남긴다."""
    m_obj, table = tools.mask_obj({"title": rec["title"], "text": rec["body"]}, PEOPLE)
    html = sf.record_html(m_obj["title"], m_obj["text"]).replace("<head>", f'<head><meta name="run" content="stability-c{config.V8_RECORD_CONFIG_ID}-{date.today()}-{n}">')
    with llm.guard(PEOPLE) as m:
        try:
            return sf.parse_record(tools.unmask_obj(studio.run("record", html), table)), m.calls, m.usd, None
        except studio.StudioError as e:
            return None, m.calls, m.usd, e.code


def spent_so_far():
    """원장에서 이 갈래(WS)가 이미 쓴 돈. 상한은 갈래 전체에 건다(다시 돌려도 넘지 않게)."""
    if not LEDGER.exists():
        return 0.0
    lines = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
    return sum(d.get("est_usd") or 0 for d in lines if d.get("ws") == WS)


def ledger(what, calls, usd):
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "ws": WS, "what": what,
                            "calls": calls, "est_usd": round(usd, 3)}, ensure_ascii=False) + "\n")


def compare(runs):
    """한 글의 실행 결과 목록 → 같은 정도. 첫 실행을 기준으로 인용 겹침(Jaccard)을 잰다."""
    q = [{squash(t["quote"]) for t in r["thoughts"]} for r in runs]
    sig = lambda r, k: tuple(sorted(t[k] for t in r["thoughts"]))   # noqa: E731
    return {"type_same": len({r["record_type"] for r in runs}) == 1,
            "thought_counts": [len(r["thoughts"]) for r in runs],
            "kinds_same": len({sig(r, "kind") for r in runs}) == 1,
            "values_same": len({sig(r, "value") for r in runs}) == 1,
            "topics_same": len({sig(r, "topic") for r in runs}) == 1,
            "kind_counts": [dict(Counter(t["kind"] for t in r["thoughts"])) for r in runs],
            "quote_overlap_vs_first": [round(len(q[0] & x) / max(len(q[0] | x), 1), 2) for x in q[1:]]}


def summarize(results):
    n = len(results)
    overlaps = [x for r in results for x in r["quote_overlap_vs_first"]]
    return {"agent": "기록 Agent", "path": "app/agents/studio.py", "config_id": config.V8_RECORD_CONFIG_ID,
            "records": n, "runs_each": RUNS,
            **{k: f"{sum(r[f] for r in results)}/{n}" for k, f in
               (("type_agreement", "type_same"), ("kind_agreement", "kinds_same"),
                ("value_agreement", "values_same"), ("topic_agreement", "topics_same"))},
            "thought_count_agreement": f"{sum(len(set(r['thought_counts'])) == 1 for r in results)}/{n}",
            "mean_quote_overlap": round(sum(overlaps) / max(len(overlaps), 1), 2)}


def main(dry=False):
    recs, results, spent, calls, start = targets(), [], spent_so_far(), 0, spent_so_far()
    streak = 0   # 연달아 실패한 수. 2번이면 Studio 가 막힌 것으로 보고 멈춘다(시간 초과는 다시 시도까지 2번 값이 든다)
    for rec in recs:
        if streak >= 2:
            break
        if dry:
            print(rec["day"], rec["title"], len(rec["body"]), "자")
            continue
        runs, secs, failed = [], [], []
        for n in range(RUNS):
            if streak >= 2:
                print("Studio 가 연달아 실패해 멈춤", flush=True)
                break
            if spent + 2 * config.PRICE_STUDIO_PAGE > CAP_USD:   # 다시 시도까지 2번 값이 남아야 보낸다
                raise SystemExit(f"비용 상한 ${CAP_USD} — 멈춤({WS} 지금까지 ${spent:.2f})")
            t0 = time.time()
            r, c, usd, err = once(rec, n)
            secs.append(round(time.time() - t0, 1))
            spent, calls = spent + usd, calls + c
            ledger(f"흔들림 설정 #{config.V8_RECORD_CONFIG_ID} 하늘 {rec['day']} {n + 1}/{RUNS}번째(가상 인물, 기록 Agent)" + (f" — 실패 {err}" if err else ""), c, usd)
            streak = streak + 1 if r is None else 0
            if r is None:
                failed.append(err)
            else:
                runs.append(r)
        if len(runs) < 2:
            results.append({"record": rec["title"], "day": rec["day"], "failed_runs": failed, "seconds": secs, "runs": []})
            continue
        results.append({"record": rec["title"], "day": rec["day"], **compare(runs), "failed_runs": failed, "seconds": secs,
                        "runs": [{"record_type": r["record_type"],
                                  "thoughts": [{k: t[k] for k in ("thought", "quote", "kind", "certainty", "value", "topic")}
                                               for t in r["thoughts"]]} for r in runs]})
        print({k: v for k, v in results[-1].items() if k != "runs"}, flush=True)
    if dry:
        return None
    ok = [r for r in results if r["runs"]]
    out = {**summarize(ok), "records_failed": len(results) - len(ok), "failed_runs": sum(len(r["failed_runs"]) for r in results),
           "studio_calls": calls, "est_usd": round(spent - start, 3), "detail": results}
    path = ROOT / "eval/results" / f"{date.today().isoformat()}-{OUT_NAME}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "detail"}, ensure_ascii=False, indent=1), "→", path.name)
    return out


if __name__ == "__main__":
    if "--record-config" in sys.argv:
        config.V8_RECORD_CONFIG_ID = sys.argv[sys.argv.index("--record-config") + 1]
        WS, OUT_NAME = "Q3-흔들림", f"stability-c{config.V8_RECORD_CONFIG_ID}"
    main(dry="--dry" in sys.argv)
