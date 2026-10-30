"""품질 3판 측정(서비스 길): 가상 인물 하늘 29편을 app/agents/graph(safety → names → 기록 → 지난 생각 → 관측 → 규칙 →
한마디 → 저장)로, 로컬 Supabase 시험 계정(e2e@my-universe.test)에서 정한 Studio 설정 번호로 돌린다.

    scripts/dev_up.sh                                                                   # 먼저(로컬 Supabase · ChromaDB · 계정)
    uv run --frozen python tools/quality_v3.py dry                                      # 네트워크 · DB 없이 글 수 · 예상 비용
    uv run --frozen python tools/quality_v3.py run --record-config 3 --observe-config 3 --tag v3a   # 유료(판당 약 $3)
    uv run --frozen python tools/quality_v3.py run --record-config 2 --observe-config 2 --tag v2    # 2판 기준선(같은 길)
    uv run --frozen python tools/stability_v2.py --record-config 3                     # 흔들림(약 $0.45)
    # 판정: eval/results/<날짜>-links-<tag>.csv 의 verdict 칸(맞음 · 약함 · 틀림)을 채운 뒤
    uv run --frozen python eval/labels.py links-score eval/results/<날짜>-links-<tag>.csv

내는 것(eval/results/<날짜>-quality-<tag>.json, -links-<tag>.csv):
① 관계: 관측 Agent 가 낸 것(날것)과 서비스 규칙을 지나 화면에 나가는 것, 설계(expected.json) 짝 · 금지 관계,
   거짓 연결 판정 양식(eval/labels.py links-form 과 같은 칸 + service 칸 = 남음 → 종류 / 버림: 이유)
② 생각 수 · 종류 · 글 유형 분포, '기타 생각'(가치 이름 · 빈 주제) 수
③ 실패(첫 실행 실패 · 이어 하기 한 번 뒤에도 실패 · 오류 코드) · 시간(글 한 편 · 기록 · 관측 단계) · 비용(runs 표)
글마다 runs/cost_ledger.jsonl 에 한 줄(갈래 Q3). 운영 DB · Chroma Cloud 를 가리키면 멈춘다. 실제 일기는 쓰지 않는다.
"""
import argparse
import importlib.util
import json
import statistics
import sys
import time
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.agents import graph  # noqa: E402
from app.agents import tools as agent_tools  # noqa: E402
from app.core import config  # noqa: E402
from app.repository import diary  # noqa: E402
from app.service import studio_format as sf  # noqa: E402


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


labels = _load("eval_labels", "eval/labels.py")
v2 = _load("studio_run_v2", "tools/studio_run_v2.py")   # records() · metrics(): WS2 비교표와 같은 잣대

LEDGER = Path("/Users/east_star/Projects/my-universe/runs/cost_ledger.jsonl")   # 원장은 본 저장소(git 제외)
PER_POST_USD = 0.10              # 기록 + 관측 Studio 1쪽씩(PRD §5.7) + Solar 위기 · 한마디(≈ $0.002)
CAP_USD, TOTAL_STOP_USD = 4.0, 300.0   # 판 하나(29편 ≈ $2.9 + 다시 시도 여유). 2026-10-30 동규 「요금 상관없이, 크레딧 다 쓰기 — 막히면 알려 주면 더 받아 옴」: 누적 멈춤은 사고 방지용으로만
STOP_STREAK = 3                  # 연달아 이만큼 글이 실패하면 Studio 가 막힌 것으로 보고 멈춘다
NAMES = json.loads((ROOT / "data/virtual/expected.json").read_text(encoding="utf-8"))["names"]


def ledger_total():
    return sum(json.loads(x).get("est_usd") or 0 for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()) \
        if LEDGER.exists() else 0.0


def ledger_line(what, calls, usd):
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "ws": "Q3", "what": what,
                            "calls": calls, "est_usd": round(usd, 4)}, ensure_ascii=False) + "\n")


class Spy:
    """서비스 코드를 바꾸지 않고 관측 Agent 날것과 규칙 판정을 엿본다(측정 전용). 기록 입력에는 Studio 캐시를 피하는
    보이지 않는 표시를 단다(stability_v2 와 같은 까닭)."""

    def __init__(self, mark):
        self.mark, self.observed, self.judged = mark, [], []

    def __enter__(self):
        self.saved = obs, filt, html = agent_tools.run_observe_agent, graph.filter_relations, sf.record_html

        def observe(*a, **k):
            out = obs(*a, **k)
            self.observed.append(out)
            return out

        def judge(cands, ts, states=None):
            kept, dropped = filt(cands, ts, states)
            self.judged.append((cands, kept, dropped))
            return kept, dropped

        def record_html(*a, **k):
            return html(*a, **k).replace("<head>", f'<head><meta name="run" content="{self.mark}">', 1)

        agent_tools.run_observe_agent, graph.filter_relations, sf.record_html = observe, judge, record_html
        return self

    def __exit__(self, *exc):
        agent_tools.run_observe_agent, graph.filter_relations, sf.record_html = self.saved


def _raw_relations(spy):
    """마지막 관측 결과의 관계마다 서비스 규칙 판정을 붙인다. rules 노드는 관측 관계 순서대로 후보를 만든다."""
    if not spy.observed or not spy.judged:
        return []
    cands, kept, dropped = spy.judged[-1]
    why = {id(d["cand"]): d["reason"] for d in dropped}
    shown = {frozenset((k["from"], k["to"])): k["type"] for k in kept}
    out = []
    for r, c in zip(spy.observed[-1]["relations"], cands):
        pair = frozenset((c["a"], c["b"]))
        # ponytail: 같은 두 생각에 관계가 둘 오면 우선순위에서 진 쪽도 '남음'으로 적힌다(화면엔 하나). 판정 양식에는 그대로 둠
        service = f"버림: {why[id(c)]}" if id(c) in why else f"남음 → {shown[pair]}" if pair in shown else "버림"
        out.append({**{k: r.get(k, "") for k in ("type", "from", "to", "same_target", "topic", "explanation")},
                    "service": service})
    return out


def _entry(repo, uid, rec, spy):
    """글 한 편을 서비스 길로. 실패하면 사용자가 '이어서 하기'를 한 번 누른 것처럼 다시 돌린다."""
    eid = diary.new_id("e")
    with repo.session(uid) as s:
        diary.create_entry(s, eid, diary.parse_dt(rec["written_at"]), None, rec["title"], rec["body"])
    spy.observed.clear()
    spy.judged.clear()
    errors, t0 = [], time.time()
    for _ in range(2):
        try:
            graph.run(repo, uid, eid)
            break
        except Exception as e:   # Studio 시간 초과 · 실패 · 실명 막힘 등 — 오류 코드만 남긴다
            errors.append(graph.error_code(e))
    secs = round(time.time() - t0, 1)
    with repo.session(uid) as s:
        e = diary.entry(s, eid)
        runs = s.rows("runs", entry_id=eid)
        ts = diary.thoughts(s, entry_id=eid) if e["status"] == "done" else []
    return {"entry_id": eid, "day": rec["day"], "title": rec["title"], "status": e["status"], "record_type": e.get("record_type"),
            "errors": errors, "seconds": secs, "calls": sum(r["calls"] or 0 for r in runs),
            "usd": round(sum(float(r["est_usd"] or 0) for r in runs), 4),
            "step_ms": {r["step"]: r["ms"] for r in runs if not r["error_code"]},
            "thoughts": [{"id": t["id"], "kind": t["kind"], "value": t["value"] or "", "topic": t.get("topic", ""),
                          "thought": t.get("text", ""), "quote": t.get("quote", "")} for t in ts],
            "relations_raw": _raw_relations(spy) if e["status"] == "done" else []}


def _median(xs):
    return round(statistics.median(xs), 1) if xs else None


def _p90(xs):
    return round(sorted(xs)[max(0, int(len(xs) * 0.9 + 0.5) - 1)], 1) if xs else None


def summarize(tag, out, shown_rel):
    done = [r for r in out if r["status"] == "done"]
    days = {r["entry_id"]: r["day"] for r in out}
    thoughts = [t for r in done for t in r["thoughts"]]
    rec_of = lambda tid: tid.rsplit("-", 1)[0]   # noqa: E731  생각 id = 기록 id + '-t00'(diary.thought_id)
    raw = [{**x, "from_record": rec_of(x["from"]), "to_record": rec_of(x["to"])} for r in done for x in r["relations_raw"]]
    ms = lambda step: [r["step_ms"][step] / 1000 for r in done if step in r["step_ms"]]   # noqa: E731
    secs = [r["seconds"] for r in done]
    return {
        "tag": tag, "config": {"record": config.V8_RECORD_CONFIG_ID, "observe": config.V8_OBSERVE_CONFIG_ID},
        "records": len(out), "done": len(done),
        # ③ 실패 · 시간 · 비용
        "failed_first_run": sum(bool(r["errors"]) for r in out), "failed_after_resume": len(out) - len(done),
        "error_codes": dict(Counter(c for r in out for c in r["errors"])),
        "seconds_per_post": {"median": _median(secs), "p90": _p90(secs)},
        "record_agent_s_median": _median(ms("record_agent")), "observe_s_median": _median(ms("observe")),
        "calls": sum(r["calls"] for r in out), "est_usd": round(sum(r["usd"] for r in out), 3),
        # ② 생각
        "thoughts": len(thoughts), "kinds": dict(Counter(t["kind"] for t in thoughts).most_common()),
        "record_types": dict(Counter(r["record_type"] for r in done).most_common()),
        "other_topic": sum(t["topic"] == graph.OTHER_TOPIC for t in thoughts),
        "topics": len({t["topic"] for t in thoughts}),
        # ① 관계(날것 = 관측 Agent 가 낸 그대로, 화면 = 서비스 규칙을 지나 저장된 것)
        "relations_raw": v2.metrics(days, thoughts, raw), "relations_shown": v2.metrics(days, thoughts, shown_rel),
        "dropped_reasons": dict(Counter(x["service"].split(": ", 1)[1] for x in raw if x["service"].startswith("버림: "))),
    }, days, raw


def measure(repo, uid, recs, tag, ledger=ledger_line, cap=CAP_USD):
    """recs: [{id, day, written_at, title, body}] 순서대로(지난 생각이 쌓이게). → (결과 dict, 판정 양식 줄)."""
    out, spent, streak = [], 0.0, 0
    with Spy(f"q3-{tag}-{datetime.now():%Y%m%d%H%M%S}") as spy:
        for rec in recs:
            if spent + 2 * PER_POST_USD > cap or streak >= STOP_STREAK:
                print(f"멈춤: 이번 ${spent:.2f} / 상한 ${cap}, 연달아 실패 {streak}", flush=True)
                break
            r = _entry(repo, uid, rec, spy)
            out.append(r)
            spent += r["usd"]
            streak = streak + 1 if r["status"] != "done" else 0
            ledger(f"품질 3판 {tag} 하늘 {rec['day']}(서비스 길, 가상 인물, 설정 {config.V8_RECORD_CONFIG_ID}/"
                   f"{config.V8_OBSERVE_CONFIG_ID})" + (f" — 실패 {','.join(r['errors'])}" if r["errors"] else ""), r["calls"], r["usd"])
            print(r["day"], r["status"], r["record_type"], f"생각 {len(r['thoughts'])}", f"관계(날것) {len(r['relations_raw'])}",
                  f"{r['seconds']}초", f"${r['usd']}", r["errors"] or "", flush=True)
    with repo.session(uid) as s:
        shown_rel = diary.relations(s)
    summary, days, raw = summarize(tag, out, shown_rel)
    rows = labels.links_form_rows({"relations_detail": raw}, days)   # 생각 id 앞부분 = 기록 id → 날
    return {**summary, "links_form_rows": len(rows), "detail": out,
            "relations_shown_detail": [{k: x.get(k) for k in ("type", "from", "to", "line", "topic", "explanation")}
                                       for x in shown_rel]}, rows


def local_repo():
    """로컬 Supabase · ChromaDB 의 시험 계정만. 운영을 가리키면 멈춘다. → (repo, uid) — 계정은 비우고 사람만 등록."""
    from app.core import seed
    from app.repository import PgRepo
    if urlparse(config.DATABASE_URL).hostname not in ("127.0.0.1", "localhost") or config.CHROMA_API_KEY:
        sys.exit("로컬 Supabase · ChromaDB 가 아니라서 멈춥니다(.env.local 확인, scripts/dev_up.sh).")
    _, uid = seed.token(seed.ACCOUNTS["e2e"])   # 로컬 Supabase 가 아니면 seed 가 멈춘다
    repo = PgRepo(config.DATABASE_URL)
    seed.wipe(repo, uid)
    seed.agree(repo, uid)
    with repo.session(uid) as s:   # 하늘의 사람(가상)을 미리 등록해 가명으로 보낸다(stability_v2 와 같음)
        for n in NAMES:
            diary.add_person(s, n, relation="친구")
    return repo, uid


def main(argv=None):
    ap = argparse.ArgumentParser(description="품질 3판 측정(서비스 길, 유료)")
    ap.add_argument("cmd", choices=["run", "dry"])
    ap.add_argument("--record-config")
    ap.add_argument("--observe-config")
    ap.add_argument("--tag", default="")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(argv)
    recs = v2.records()[:a.limit]
    if a.cmd == "dry":
        print(f"하늘 {len(recs)}편, 판당 약 ${len(recs) * PER_POST_USD:.2f}(상한 ${CAP_USD}), 원장 합계 ${ledger_total():.2f}")
        return None
    if not (a.record_config and a.observe_config and a.tag):
        ap.error("run 은 --record-config · --observe-config · --tag 가 필요합니다")
    if ledger_total() > TOTAL_STOP_USD:
        sys.exit(f"원장 누적이 ${TOTAL_STOP_USD} 를 넘어 멈춥니다.")
    config.V8_RECORD_CONFIG_ID, config.V8_OBSERVE_CONFIG_ID = a.record_config, a.observe_config
    repo, uid = local_repo()
    res, rows = measure(repo, uid, recs, a.tag)
    stem = ROOT / "eval/results" / f"{date.today().isoformat()}"
    Path(f"{stem}-quality-{a.tag}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    labels.write_csv(f"{stem}-links-{a.tag}.csv", labels.LINK_COLS, rows)
    print(json.dumps({k: v for k, v in res.items() if k not in ("detail", "relations_shown_detail")}, ensure_ascii=False, indent=1))
    print("→", f"{stem.name}-quality-{a.tag}.json", f"{stem.name}-links-{a.tag}.csv", f"원장 합계 ${ledger_total():.2f}")
    return res


if __name__ == "__main__":
    main()
