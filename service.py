"""
service.py

글 한 편이 들어와서 관측 보고서가 나오기까지 (PRD §5):

1. 기록 Agent (Parse → Classify → 유형별 Extract)
2. 관문 G1 · G2 · G4 (원문 인용 대조, 날짜, 실명)
3. 주제 → 성운 연결 (임베딩)
4. 관련 과거 생각 고르기 → 비교 입력 HTML
5. 관측 Agent (Parse → Classify(관측 상태) → Extract(관측 보고서))
6. 관계 규칙 · 관문 G3 → 관측 보고서
"""

import time
import uuid

import config
import embedder
import gates
import importer
import observe_builder
import runlog
import universe
from agent_client import observe_agent, record_agent


class Budget:
    """세션당 Studio 실행 횟수 상한 (공개 배포에서 크레딧 보호)."""

    def __init__(self, jobs=config.MAX_JOBS_PER_SESSION):
        self.left = jobs

    def spend(self, meta):
        if not meta.get("cached"):
            self.left -= 1

    def check(self, need=2):
        if self.left < need:
            raise RuntimeError(f"이번 세션의 실행 한도({config.MAX_JOBS_PER_SESSION}회)를 다 썼습니다.")


def _first(v, default=""):
    if isinstance(v, list):
        return v[0] if v else default
    return v if v is not None else default


def process_record(state, rec, budget=None, progress=lambda step: None, extra_names=(), use_cache=True):
    """공통 기록 한 편을 우주에 더하고 관측 보고서를 돌려준다."""
    budget = budget or Budget(10 ** 6)
    run_id = uuid.uuid4().hex[:8]
    rid = rec["id"]
    t_start = time.time()
    source = rec["title"] + "\n" + rec["body"]

    # 1. 기록 Agent
    progress("기록 Agent: 글을 읽고 생각을 나누는 중")
    budget.check()
    label, data, m1 = record_agent.run_html(importer.to_html(rec), use_cache=use_cache)
    budget.spend(m1)

    # 2. 관문 G1 · G2 · G4
    progress("관문: 원문 인용 · 날짜 · 실명 확인")
    names = gates.find_names(source, extra_names)
    state["names"] = sorted(set(state["names"]) | set(names), key=lambda n: (-len(n), n))
    thoughts, dropped = [], 0
    for i, t in enumerate(data.get("thoughts") or [], 1):
        if not gates.quote_in_source(t.get("quote"), source):
            dropped += 1
            continue
        kind = (t.get("kind") or "").strip()
        thoughts.append({
            "id": f"{rid}-T{i}", "record_id": rid, "day": rec["day"],
            "topic": (t.get("topic") or "기타").strip(), "thought": (t.get("thought") or "").strip(),
            "kind": kind if kind in universe.KINDS else "해석",
            "certainty": (t.get("certainty") or "고민 중").strip(),
            "quote": t["quote"].strip(), "self_change": (t.get("self_change") or "").strip(),
            "value": (t.get("value") or "").strip(),
        })
    g = {"G1_dropped_quotes": dropped, "G2_date_ok": gates.date_ok(rec), "G4_names_masked": len(names)}

    meta = {k: data.get(k) or [] for k in ("period", "triggers", "addressee", "roles", "references", "events")}
    meta["roles"] = [r for r in meta["roles"] if not gates.find_names(r, state["names"])]
    state["records"][rid] = {**rec, "type": label, "summary": " ".join(data.get("summary") or []),
                             "meta": meta, "thought_ids": [t["id"] for t in thoughts], "gates": g}
    if rid not in state["order"]:
        state["order"].append(rid)
    runlog.write(run_id, "record", record_id=rid, **{k: m1[k] for k in ("agent", "config_id", "seconds", "pages", "est_cost", "cached")},
                 type=label, thoughts=len(thoughts), **g)

    # 3. 주제 → 성운
    progress("주제를 성운에 연결하는 중")
    texts = [t["topic"] for t in thoughts] + [t["thought"] for t in thoughts] + [state["records"][rid]["summary"]]
    embs = embedder.embed(texts)
    n = len(thoughts)
    for i, t in enumerate(thoughts):
        t["hub"] = universe.link_hub(state, t["topic"], embs[i])
        t["emb"] = embs[n + i]
    summary_emb = embs[-1]

    # 4 · 5. 관측
    report = {"record_id": rid, "day": rec["day"], "day_basis": rec["day_basis"], "title": rec["title"],
              "type": label, "summary": state["records"][rid]["summary"], "question": "",
              "observation_state": "관측 없음(생각이 없는 글)", "relations": [], "rule_notes": [],
              "limits": [], "run": {"record_agent": m1}}
    past = universe.pick_past(state, thoughts, rid) if thoughts else []
    for t in thoughts:
        state["thoughts"][t["id"]] = t
    if thoughts:
        progress(f"관측 Agent: 과거 생각 {len(past)}개와 비교하는 중")
        html, ids = observe_builder.build(rec["day"], thoughts, past)
        budget.check(1)
        state_label, obs, m2 = observe_agent.run_html(html, use_cache=use_cache)
        budget.spend(m2)
        kept, notes = universe.apply_rules(state, obs.get("relations") or [], ids, rid)
        state["relations"] += kept
        report.update(observation_state=state_label, question=_first(obs.get("question")),
                      summary=" ".join(obs.get("summary") or []) or report["summary"],
                      relations=[r["id"] for r in kept], rule_notes=notes)
        report["run"]["observe_agent"] = m2
        report["limits"].append(f"과거 생각 {len(past)}개와만 비교했습니다 (같은 성운이거나 유사도 {config.SAME_STORY_THETA} 이상, 최대 {config.PAST_LIMIT}개).")
        runlog.write(run_id, "observe", record_id=rid, **{k: m2[k] for k in ("agent", "config_id", "seconds", "pages", "est_cost", "cached")},
                     state=state_label, past=len(past), relations=len(kept), rule_changes=len(notes))
    if rec["day_basis"] == "추정":
        report["limits"].append("글이 다루는 날을 작성일로 추정했습니다.")

    # 6. 관문 G3 (사람 단정) — AI가 쓴 문장만 검사
    rewritten = 0
    for key in ("summary", "question"):
        if gates.judged(report[key]):
            report[key], rewritten = gates.NEUTRAL, rewritten + 1
    for r in state["relations"]:
        if r["observed_in"] == rid and gates.judged(r["explanation"]):
            r["explanation"], rewritten = gates.NEUTRAL, rewritten + 1
    g["G3_rewritten"] = rewritten

    universe.place(state, rid, summary_emb)
    report["gates"] = g
    agent_secs = sum(m.get("seconds", 0) for k, m in report["run"].items() if k.endswith("_agent"))
    report["run"]["seconds"] = round(max(time.time() - t_start, agent_secs), 2)   # 캐시면 원래 실행 시간
    report["run"]["est_cost"] = round(sum(m.get("est_cost", 0) for m in (report["run"].get("record_agent", {}), report["run"].get("observe_agent", {}))), 4)
    state["reports"][rid] = report
    runlog.write(run_id, "report", record_id=rid, seconds=report["run"]["seconds"], est_cost=report["run"]["est_cost"], **g)
    return report


##################################################
# 화면 · JSON으로 내보낼 보고서 (실명은 가린다)
##################################################

def view_report(state, rid):
    rep = state["reports"][rid]
    th, names = state["thoughts"], state["names"]
    mk = lambda s: gates.mask(s, names)
    rels = [r for r in state["relations"] if r["id"] in rep["relations"]]

    def side(tid):
        t = th[tid]
        return {"day": t["day"], "record_id": t["record_id"], "kind": t["kind"], "quote": mk(t["quote"])}

    items = [{"type": r["type"], "line": r["line"], "topic": r["topic"], "past": side(r["from"]), "today": side(r["to"]),
              "explanation": mk(r["explanation"]), "axis": r["axis"]} for r in rels if r["status"] != "rejected"]
    mine = [th[t] for t in state["records"][rid]["thought_ids"]]
    by_kind = {k: sum(1 for t in mine if t["kind"] == k) for k in universe.KINDS}
    vows = [i for i in items if i["past"]["kind"] == "다짐" and i["type"] in ("이어짐", "어긋남")]
    return {
        "관측 보고서": f"{rep['day']} 글 · 관측 상태: {rep['observation_state']}",
        "record_id": rid, "day": rep["day"], "day_basis": rep["day_basis"], "title": mk(rep["title"]),
        "type": rep["type"], "observation_state": rep["observation_state"],
        "summary": mk(rep["summary"]), "question": mk(rep["question"]),
        "counts": {"thoughts": len(mine), "by_kind": {k: v for k, v in by_kind.items() if v}},
        "thoughts": [{"topic": t["topic"], "thought": mk(t["thought"]), "kind": t["kind"], "certainty": t["certainty"],
                      "value": t["value"], "quote": mk(t["quote"]), "self_change": mk(t["self_change"])} for t in mine],
        "continued": [i for i in items if i["type"] == "이어짐"],
        "changed": [i for i in items if i["type"] == "바뀜"],
        "tension": [i for i in items if i["type"] == "긴장"],
        "resolved": [i for i in items if i["type"] == "해소"],
        "vows": {"kept": [i for i in vows if i["type"] == "이어짐"], "missed": [i for i in vows if i["type"] == "어긋남"]},
        "missed_vows": [i for i in items if i["type"] == "어긋남"],
        "goal_conflicts": [i for i in items if i["type"] == "목표 충돌"],
        "limits": rep["limits"], "gates": rep["gates"],
        "run": {"seconds": rep["run"]["seconds"], "est_cost_usd": rep["run"]["est_cost"],
                "record_agent_config": rep["run"].get("record_agent", {}).get("config_id"),
                "observe_agent_config": rep["run"].get("observe_agent", {}).get("config_id")},
    }
