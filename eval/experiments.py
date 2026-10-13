"""
eval/experiments.py — PRD §8.4 실험 · §8.5 드리프트를 재는 도구(WS23). 결과는 docs/eval-v8.md 의 절마다 적는다.

    uv run --frozen python eval/experiments.py recall   # 지난 생각 고르기 재현율 + E4 비교 입력 크기(고정 5 · 10 · 20 vs 적응형)
    uv run --frozen python eval/experiments.py e1       # E1 의미적 거리: 벡터 유사도만 vs 관계 판정으로 바뀜 잡기
    uv run --frozen python eval/experiments.py e2 --live   # E2 자르는 단위: 고정 길이 vs 생각(Solar 임베딩, 유료 소량)
    uv run --frozen python eval/experiments.py e5       # E5 비용 · 지연 표(원장 · 실행 기록)
    uv run --frozen python eval/experiments.py drift    # 드리프트: 달마다 영역 분포 변화 + 몇 개 해에 대해 썼나
    uv run --frozen python eval/experiments.py e9 <반응.json>   # E9 다음 걸음 제안(실사용 반응이 쌓이면)

재료: 가상 인물 하늘(data/virtual — 글 · 정답 관계 expected.json)과 1판 결과 output/records.json(생각 61개 · 벡터 ·
관측 Agent 관계, git 제외라 원본 저장소에서 읽음). recall · e1 · e5 · drift 는 외부 호출 없음.
"""

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core import config  # noqa: E402
from app.service.rules import cos, pick_past  # noqa: E402
from app.service.rules.past import LIMIT  # noqa: E402

MAIN = Path("/Users/east_star/Projects/my-universe")   # 1판 결과 · 원장 · 실행 기록은 원본 저장소(git 제외)
V1 = MAIN / "output/records.json"
LEDGER = MAIN / "runs/cost_ledger.jsonl"
EXPECTED = json.loads((ROOT / "data/virtual/expected.json").read_text(encoding="utf-8"))
CHANGE = {"바뀜", "해소"}


def center_of(vecs):
    return [sum(c) / len(vecs) for c in zip(*vecs)] if len(vecs) >= 2 else None


def load_v1(path=V1):
    """1판 결과 → (생각 [{id, record_id, day, topic, domain, text, emb}], 관계, {기록 id: 날})."""
    s = json.loads(Path(path).read_text(encoding="utf-8"))
    hub = {h["id"]: h["name"] for h in s["hubs"].values()}
    ts = [{"id": t["id"], "record_id": t["record_id"], "day": t["day"], "topic": t["topic"], "domain": hub.get(t.get("hub")),
           "text": t["quote"] or t["thought"],
           "emb": json.loads(t["emb"]) if isinstance(t["emb"], str) else t["emb"]} for t in s["thoughts"].values()]
    return ts, s["relations"], {rid: r["day"] for rid, r in s["records"].items()}


##################################################
# 지난 생각 고르기 재현율 · E4 비교 입력 크기
##################################################

def ranked_past(today, past, center):
    """서비스와 같은 잣대(중심 보정 코사인, 오늘 생각 중 최댓값)로 지난 단위를 줄 세운다."""
    sim = {p["id"]: max(cos(t["emb"], p["emb"], center) for t in today) for p in past}
    return sorted(past, key=lambda p: (-sim[p["id"]], p["id"]))


def recall_e4(units, relations=None, ks=(5, 10, 20)):
    """정답 관계(지난 날 → 오늘)마다 오늘 글의 단위로 지난 단위를 골라, 정답 지난 글의 단위가 들었는지 본다.
    단위 = 생각(또는 E2 의 고정 길이 조각) {id, record_id, day, topic, emb}. 전략: 고정 k(유사도 순) · 적응형(서비스 pick_past)."""
    relations = relations or EXPECTED["relations"]
    names = [f"fixed{k}" for k in ks] + ["adaptive", "adaptive_nolimit"]
    rows = []
    for e in relations:
        today = [u for u in units if u["day"] == e["today"]]
        past = [u for u in units if u["day"] < e["today"]]
        center = center_of([u["emb"] for u in today + past])
        order = ranked_past(today, past, center)
        picks = {f"fixed{k}": order[:k] for k in ks}
        picks["adaptive"] = pick_past(today, past, center=center)
        picks["adaptive_nolimit"] = pick_past(today, past, center=center, limit=10 ** 6)
        rank = next((i for i, p in enumerate(order, 1) if p["day"] == e["past"]), None)
        rows.append({"past": e["past"], "today": e["today"], "type": e["type"], "past_units": len(past), "sim_rank": rank,
                     **{n: {"hit": any(p["day"] == e["past"] for p in picks[n]), "size": len(picks[n])} for n in names}})
    summary = {n: {"recall": f"{sum(r[n]['hit'] for r in rows)}/{len(rows)}",
                   "mean_size": round(statistics.mean(r[n]["size"] for r in rows), 1)} for n in names}
    return rows, summary


##################################################
# E1 의미적 거리
##################################################

def e1(thoughts, relations, days):
    """기록 쌍(지난 → 오늘)마다 생각 벡터 최대 유사도. 정답 바뀜 · 해소 쌍이 유사도 순위 어디에 있고, 감정만 달라진 쌍
    (not_relations)이 그보다 위에 오는지 본다. 같은 쌍을 관측 Agent(관계 판정)가 바뀜 · 해소로 잡았는지와 견준다."""
    center = center_of([t["emb"] for t in thoughts])
    by_day = defaultdict(list)
    for t in thoughts:
        by_day[t["day"]].append(t)
    ds = sorted(by_day)
    pairs = {(a, b): max(cos(x["emb"], y["emb"], center) for x in by_day[a] for y in by_day[b])
             for i, a in enumerate(ds) for b in ds[i + 1:]}
    order = sorted(pairs, key=lambda p: -pairs[p])
    rank = {p: i for i, p in enumerate(order, 1)}
    gold = [(e["past"], e["today"]) for e in EXPECTED["relations"] if e["type"] in CHANGE]
    decoy = [(e["past"], e["today"]) for e in EXPECTED["not_relations"]]
    judged = {(days[r["from_record"]], days[r["to_record"]]) for r in relations
              if r["type"] in CHANGE and r["from_record"] != r["to_record"]}
    # 벡터만: 정답 쌍 수만큼 위에서 자르면 몇 개가 정답인가(precision@k), 순위 평균(AUC 꼴: 정답이 아닌 쌍보다 위에 있는 비율)
    k = len(gold)
    auc = statistics.mean(sum(pairs[g] > pairs[p] for p in pairs if p not in gold) / (len(pairs) - k) for g in gold)
    return {"pairs": len(pairs), "gold_change": [{"pair": g, "rank": rank[g], "sim": round(pairs[g], 3)} for g in gold],
            "decoy": [{"pair": d, "rank": rank[d], "sim": round(pairs[d], 3)} for d in decoy],
            "vector_precision_at_k": f"{sum(p in gold for p in order[:k])}/{k}", "vector_auc": round(auc, 3),
            "judge_recall": f"{sum(g in judged for g in gold)}/{k}",
            "judge_false": len(judged - set(gold)), "judge_decoy": sum(d in judged for d in decoy)}


##################################################
# E2 자르는 단위
##################################################

def chunks(rec, size):
    text = f"{rec['title']}\n{rec['body']}"
    return [text[i:i + size] for i in range(0, len(text), size)]


def e2(records, thoughts, embed, size=120):
    """고정 길이 조각 vs 생각 단위로 recall_e4 를 돌린다. embed(글 목록) → 벡터 목록(가명 처리 · 비용은 부르는 쪽)."""
    # 주제 없이 벡터만 견준다(단위만 다르게). 주제 칸을 단위마다 다르게 둬야 pick_past 가 '같은 주제'로 묶지 않는다.
    units = {"chunk": [{"id": f"{r['id']}-C{i}", "record_id": r["id"], "day": r["day"], "text": c}
                       for r in records for i, c in enumerate(chunks(r, size))],
             "thought": [dict(t) for t in thoughts]}
    for us in units.values():
        for u in us:
            u["topic"] = u["id"]
    out = {}
    for name, us in units.items():
        for u, v in zip(us, embed([u["text"] for u in us])):
            u["emb"] = v
        rows, s = recall_e4(us)
        out[name] = {"units": len(us), **{k: v for k, v in s.items() if k in ("fixed5", "fixed10", "adaptive_nolimit")},
                     "mean_sim_rank": round(statistics.mean(r["sim_rank"] or 99 for r in rows), 1)}
    return out


##################################################
# E5 비용 · 지연
##################################################

def read_jsonl(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def e5(log_lines, ledger_lines):
    """실행 기록(app/core/logger 'step' · 'external' 줄)과 원장 → 단계별 지연 · 비용, 글 한 편 합계, 외부 호출 실패율, 원장 합계."""
    steps = defaultdict(list)
    per_entry = defaultdict(lambda: {"ms": 0, "usd": 0.0})
    for d in log_lines:
        if d.get("event") == "step" and "ms" in d:
            steps[d["step"]].append(d)
            per_entry[d.get("entry_id")]["ms"] += d["ms"]
            per_entry[d.get("entry_id")]["usd"] += d.get("est_usd", 0)
    ext = defaultdict(lambda: [0, 0])
    for d in log_lines:
        if d.get("event") == "external" and "ok" in d:
            ext[d["what"]][0] += 1
            ext[d["what"]][1] += not d["ok"]

    def p90(xs):
        return sorted(xs)[max(0, int(len(xs) * 0.9) - 1)]

    by_ws = defaultdict(lambda: {"lines": 0, "calls": 0, "usd": 0.0})
    for d in ledger_lines:
        w = by_ws[d.get("ws", "?")]
        w["lines"] += 1
        w["calls"] += d.get("calls") or 0
        w["usd"] += d.get("est_usd") or 0
    entries = [v for k, v in per_entry.items() if k]
    return {"steps": {k: {"n": len(v), "median_ms": statistics.median(x["ms"] for x in v), "p90_ms": p90([x["ms"] for x in v]),
                          "mean_usd": round(statistics.mean(x.get("est_usd", 0) for x in v), 4)} for k, v in steps.items()},
            "entry": {"n": len(entries), "median_s": round(statistics.median(e["ms"] for e in entries) / 1000, 1) if entries else None,
                      "mean_usd": round(statistics.mean(e["usd"] for e in entries), 4) if entries else None},
            "external_fail": {k: f"{v[1]}/{v[0]}" for k, v in ext.items()},
            "ledger": {k: {**v, "usd": round(v["usd"], 4)} for k, v in sorted(by_ws.items(), key=lambda x: -x[1]["usd"])},
            "ledger_total_usd": round(sum(d.get("est_usd") or 0 for d in ledger_lines), 4)}


##################################################
# 드리프트(영역 분포 변화) · 여러 해에 대해 쓰는지
##################################################

def drift(items, key=lambda d: d[:7]):
    """items [{day, domain}] → 기간(기본 달)마다 글 수 · 영역 수 · 앞 기간과의 분포 거리(총변동거리 0~1, 1 = 완전히 다름)
    · 가장 많이 움직인 영역. 사용자 한 명이면 '여러 해에 대해 쓰는지'(지향 지표), 전체 사용자면 설정 · 모델 드리프트 신호."""
    buckets = defaultdict(Counter)
    for it in items:
        if it.get("domain"):
            buckets[key(it["day"])][it["domain"]] += 1
    out, prev = [], None
    for w in sorted(buckets):
        c, n = buckets[w], sum(buckets[w].values())
        p = {d: v / n for d, v in c.items()}
        row = {"window": w, "n": n, "domains": len(c), "tv_prev": None, "moved": []}
        if prev:
            keys = set(p) | set(prev)
            row["tv_prev"] = round(sum(abs(p.get(d, 0) - prev.get(d, 0)) for d in keys) / 2, 3)
            row["moved"] = sorted(((d, round(p.get(d, 0) - prev.get(d, 0), 2)) for d in keys), key=lambda x: -abs(x[1]))[:2]
        out.append(row)
        prev = p
    return out


##################################################
# E9 다음 걸음 제안
##################################################

def e9(rows):
    """rows [{suggest_setting('자주'|'가끔'|'안 함'), suggested(bool), reaction('좋아요'|'별로'|None), reason(str|None),
    wrote_next_day(bool)}] → 묶음(설정 · 제안 있음/없음)마다 다음 날 다시 쓴 비율 · 별로 비율 · '설교 같음' 비율."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r.get("suggest_setting") or "가끔", "제안 있음" if r["suggested"] else "제안 없음")].append(r)

    def rate(rs, f):
        return round(sum(map(f, rs)) / len(rs), 3)

    return [{"setting": s, "suggested": g, "n": len(rs), "next_day": rate(rs, lambda r: bool(r.get("wrote_next_day"))),
             "dislike": rate(rs, lambda r: r.get("reaction") == "별로"),
             "preachy": rate(rs, lambda r: "설교" in (r.get("reason") or ""))} for (s, g), rs in sorted(groups.items())]


##################################################
# 실행
##################################################

def ledger(what, calls, usd):
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().isoformat(timespec="seconds"), "ws": "WS23", "what": what,
                            "calls": calls, "est_usd": round(usd, 4)}, ensure_ascii=False) + "\n")


def live_embed():
    """가상 인물 이름을 가명으로 바꾼 뒤 Solar 임베딩. → (embed 함수, 계량기)."""
    from app.core import llm
    from app.service.safety import mask
    people = [{"id": f"P{i}", "name": n, "nicknames": [], "relation": "친구"} for i, n in enumerate(EXPECTED["names"], 1)]
    meter = llm.Meter(people)

    def embed(texts):
        token = llm._guard.set(meter)   # guard 안처럼: 보내기 직전 실명 검사 + 비용 세기
        try:
            return llm.embed([mask(t, people)[0] for t in texts])
        finally:
            llm._guard.reset(token)
    return embed, meter


def main(argv=None):
    ap = argparse.ArgumentParser(description="§8.4 실험 · 드리프트")
    ap.add_argument("cmd", choices=["recall", "e1", "e2", "e5", "drift", "e9"])
    ap.add_argument("src", nargs="?")
    ap.add_argument("--live", action="store_true", help="e2: Solar 임베딩(유료 소량)")
    ap.add_argument("--size", type=int, default=120, help="e2: 조각 길이(글자)")
    a = ap.parse_args(argv)
    if a.cmd in ("recall", "e1", "drift", "e2"):
        thoughts, relations, days = load_v1()
    if a.cmd == "recall":
        rows, res = recall_e4(thoughts)
        res = {"strategies": res, "rows": rows, "limit": LIMIT}
    elif a.cmd == "e1":
        res = e1(thoughts, relations, days)
    elif a.cmd == "e2":
        if not a.live:
            ap.error("e2 는 임베딩을 새로 만들어야 해서 --live 가 필요(Solar 임베딩, 약 $0.001)")
        import importer
        recs = importer.from_instagram_zip((ROOT / "data/virtual/instagram-virtual-haneul.zip").read_bytes())
        embed, meter = live_embed()
        res = e2(recs, thoughts, embed, a.size)
        res["cost"] = {"calls": meter.calls, "est_usd": round(meter.usd, 5), "model": config.EMBED_PASSAGE_MODEL}
        ledger(f"E2 자르는 단위: 가상 인물 하늘 29편 조각({a.size}자) · 생각 61개 Solar 임베딩", meter.calls, meter.usd)
    elif a.cmd == "e5":
        log_dir = config.LOG_DIR if config.LOG_DIR.exists() else MAIN / "logs"   # worktree 에는 logs/ 가 없다
        logs = [d for f in sorted(log_dir.glob("agent_flow_*.log")) for d in read_jsonl(f)]
        res = e5(logs, read_jsonl(LEDGER) if LEDGER.exists() else [])
    elif a.cmd == "drift":
        res = drift(thoughts)
    else:
        res = e9(json.loads(Path(a.src).read_text(encoding="utf-8")) if a.src else [])
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    return res


if __name__ == "__main__":
    main()
