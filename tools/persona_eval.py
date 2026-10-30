"""
가상 인물 시험(2026-10-28 멘토링): 글을 여러 편 넣었을 때 시스템이 그 사람을 알아보는가.
인물 A · B · C(eval/personas/p*.json — Codex gpt-6-astra 가 지은 가상 일기 20편 + 심어 둔 정답: 주제 5 · 관계 9~10 · 알게 될 것 5)를
서비스 길(app/agents/graph)로 로컬 Supabase · ChromaDB 시험 계정에서 돌리고 정답과 맞춘다.
강의: 6강 Golden Set(기대 궤적까지) · 6강 페르소나 합성 데이터 · 4강 3계층 평가 · 4강 pass^k · AW-09 궤적 매칭(정밀도 · 재현율).

    uv run --frozen python tools/persona_eval.py check                                     # 정답 파일 검사(무료)
    ONTOLOGY_PROFILE=two uv run --frozen python tools/persona_eval.py run --persona A B --tag two-off --repeat 4
    uv run --frozen python tools/persona_eval.py tune eval/results/<날짜>-persona-two-off.json --train A B   # 문턱 고르기(무료)
    uv run --frozen python tools/persona_eval.py score eval/results/<날짜>-persona-<tag>.json [--tau 0.3]   # 점수(무료)
    uv run --frozen python tools/persona_eval.py collect <결과.json> --persona B --account persona-b-<tag>@my-universe.test
                                                                     # 끊긴 run 의 한 인물을 DB 에서 살리기(무료)

run 은 유료: 글 한 편 약 $0.10, --repeat N 은 마지막 N편을 기록 Agent 로 K-1번 더(편마다 약 $0.05 × 2). 모두 원장에 적는다.
결과: eval/results/<날짜>-persona-<tag>.json, 벡터는 eval/results/vectors/(git 제외). 운영 DB · Chroma Cloud 를 가리키면 멈춘다.
"""
import argparse
import importlib.util
import itertools
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.agents import graph  # noqa: E402
from app.agents import tools as agent_tools  # noqa: E402
from app.core import config  # noqa: E402
from app.repository import diary, views  # noqa: E402
from app.service.rules import place_stars  # noqa: E402
from app.service.rules.normalize import key as norm_key  # noqa: E402

spec = importlib.util.spec_from_file_location("quality_v3", ROOT / "tools/quality_v3.py")
q3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q3)   # _entry · Spy · 원장: 품질 측정과 같은 길

PERSONAS, RESULTS = ROOT / "eval/personas", ROOT / "eval/results"
K = 3                     # pass^k: 같은 글 k번이 모두 같아야 통과(강의 4강 p.33)
CAP_USD = 10.0            # 인물 하나(20편 ≈ $2 + 반복 · 다시 시도 여유). 2026-10-30: Studio 요청 한도로 다시 시도한 호출까지 세어 $3.5 에서 멈춰 올림(동규 「요금 상관없이」)
OTHER = graph.OTHER_TOPIC


def load(k):
    return json.loads((PERSONAS / f"p{k}.json").read_text(encoding="utf-8"))


def check(d):
    """정답 파일 규칙 → 문제 목록(비면 통과)."""
    es, probs = d["entries"], []
    body = {e["n"]: e["body"] for e in es}
    tops = {t["id"]: t for t in d["topics"]}
    if [e["n"] for e in es] != list(range(1, 21)) or [e["written_at"] for e in es] != sorted(e["written_at"] for e in es):
        probs.append("글 번호 · 시간 순서")
    if sum(e["off_axis"] for e in es) != 2 or Counter(t["domain"] for t in tops.values()) != {"커리어": 3, "인간관계": 2}:
        probs.append("두 영역 밖 글 2편 · 주제 커리어 3 + 인간관계 2")
    use = Counter(x for e in es for x in e["topics"])
    probs += [f"주제 {t} 가 {use[t]}편뿐" for t in tops if use[t] < 4]
    for g in d["links"]:
        for side in ("from", "to"):
            if g[f"{side}_quote"] not in body.get(g[f"{side}_entry"], ""):
                probs.append(f"{g['id']} {side}_quote 가 본문에 없음")
    return probs


def setup(k, d, tag=""):
    """인물마다 로컬 시험 계정(persona-a@ …)을 만들거나 비우고 동의 · 그 인물의 사람(가상)을 등록한다 — 계정이 따로라
    인물 셋을 동시에 돌릴 수 있다. 운영을 가리키면 멈춘다."""
    from app.core import seed
    from app.repository import PgRepo
    if urlparse(config.DATABASE_URL).hostname not in ("127.0.0.1", "localhost") or config.CHROMA_API_KEY:
        sys.exit("로컬 Supabase · ChromaDB 가 아니라서 멈춥니다(.env.local 확인, scripts/dev_up.sh).")
    email = f"persona-{k.lower()}{'-' + tag if tag else ''}@my-universe.test"   # 판(tag)마다 계정 → 같은 인물도 동시에 돌릴 수 있다
    uid = seed.admin_user(email, seed._read(seed.ENV_LOCAL)["DEV_TEST_PASSWORD"])
    repo = PgRepo(config.DATABASE_URL)
    seed.wipe(repo, uid)
    seed.agree(repo, uid)
    with repo.session(uid) as s:
        for p in d["persona"]["people"]:
            diary.add_person(s, p["name"], p["nicknames"], p["relation"])
    return repo, uid


def records(d):
    return [{"n": e["n"], "day": e["written_at"][:10], "written_at": e["written_at"], "title": e["title"], "body": e["body"]}
            for e in d["entries"]]


def record_once(repo, uid, rec, prior):
    """같은 글을 기록 하위 그래프(기록 Agent → 관문 → 온톨로지)로 한 번 더. 임시 기록으로 돌리고 흔적(작은 별 · 벡터)은 지운다.
    prior: 이 글보다 먼저 쓴 글의 작은 별 {이름: 해} — 첫 실행 때처럼 그것만 기록 Agent 에게 준다(뒤 글 · 자기 첫 실행의 이름은 빼서
    다시 정리가 쉬워지지 않게). → ([{name: 기록 Agent 가 낸 이름, domain, sun_id, id}], {생각 id: 벡터}, 비용)."""
    eid = diary.new_id("e")
    with repo.session(uid) as s:
        diary.create_entry(s, eid, diary.parse_dt(rec["written_at"]), None, rec["title"], rec["body"])
        before = {x["id"] for x in diary.stars(s)}
    cfg = {"configurable": {"ctx": graph.Ctx(repo, str(uid), eid)}}
    st = {"user_id": str(uid), "entry_id": eid, "title": rec["title"], "text": rec["body"], "written_at": rec["written_at"],
          "day": rec["day"], "weather": None, "done": ["record_input", "group_stars"], "topics": prior}   # 묶음은 group_sets 가 따로
    with q3.Spy(f"rep-{eid}"):   # Studio 는 같은 입력에 같은 답을 돌려줄 수 있어(캐시) 보이지 않는 표시를 달아 새로 정리하게 한다
        st.update(graph.names(st, cfg))
        st = graph.record_extractor.invoke(st, cfg)
    vecs = repo.vectors.get(uid, ids=[t["id"] for t in st["today"]])
    items = [{"id": t["id"], "name": t["original"].get("topic") or t["topic"], "domain": t["domain"], "sun_id": t["sun_id"],
              "quote": t["quote"]} for t in st["today"]]
    with repo.session(uid) as s:
        usd = sum(float(r["est_usd"] or 0) for r in s.rows("runs", entry_id=eid))
        diary.delete_entry(s, repo.vectors, eid)
        new = [x["id"] for x in diary.stars(s) if x["id"] not in before]   # 실패한 글이 있으면 delete_entry 가 남기므로 직접
        if new:
            s.delete("stars", id=new)
    return items, vecs, usd


def press_like_user(repo, uid, d, n_of, entry_id):
    """가상 사용자가 이 글에서 새로 보인 AI 추정(점선) 관계마다 정답대로 누른다: 심어 둔 연결 → 맞아요, 아니면 → 아니에요.
    누르기 전 제안을 센다(개인 맞춤 Ops ④ 시험 — 아니에요가 쌓이면 다음 글의 제안이 깨끗해지나). 실제 API 함수(POST /feedback)를 부른다."""
    from app.api.routes import feedback
    from app.models import FeedbackIn
    planted = {(g["from_entry"], g["to_entry"]) for g in d["links"]}
    with repo.session(uid) as s:
        mine = [r for r in diary.relations(s) if r["to_record"] == entry_id]
    pair = lambda r: tuple(sorted((n_of.get(r["from_record"]), n_of.get(r["to_record"]))))   # noqa: E731
    shown = {"total": len(mine), "planted": sum(pair(r) in planted for r in mine), "dotted": sum(r["line"] == "점선" for r in mine)}
    shown["unplanted"] = shown["total"] - shown["planted"]
    for r in mine:
        if r["line"] == "점선" and None not in pair(r):
            feedback(FeedbackIn(target="relation", target_id=r["id"], value="맞아요" if pair(r) in planted else "아니에요"),
                     user={"id": uid}, repo=repo)
    return shown


def run_persona(k, d, tag, repeat, react=False):
    repo, uid = setup(k, d, tag)
    n_of = {}
    what = (f"{config.ONTOLOGY_PROFILE or 'v8'} · 맞추기 {config.STAR_JOIN_SIM or '끔'} · 묶기 {'켬' if config.STAR_GROUPS else '끔'} · 설정 "
            f"{config.V8_RECORD_CONFIG_ID}/{config.V8_OBSERVE_CONFIG_ID}")
    out, spent, streak = [], 0.0, 0
    with q3.Spy(f"pe-{tag}-{k}-{datetime.now():%Y%m%d%H%M%S}") as spy:
        for rec in records(d):
            if spent + 2 * q3.PER_POST_USD > CAP_USD or streak >= q3.STOP_STREAK:
                print(f"멈춤: 이번 ${spent:.2f} / 상한 ${CAP_USD}, 연달아 실패 {streak}", flush=True)
                break
            r = q3._entry(repo, uid, rec, spy)
            spent += r["usd"]
            streak = streak + 1 if r["status"] != "done" else 0
            q3.ledger_line(f"가상 인물 {k} {rec['n']}/20 {tag}({what}, 서비스 길)"
                           + (f" — 실패 {','.join(r['errors'])}" if r["errors"] else ""), r["calls"], r["usd"])
            out.append({"n": rec["n"], **{x: r[x] for x in ("entry_id", "status", "errors", "seconds", "calls", "usd", "step_ms")}})
            n_of[r["entry_id"]] = rec["n"]
            if react and r["status"] == "done":
                out[-1]["shown"] = press_like_user(repo, uid, d, n_of, r["entry_id"])
            with repo.session(uid) as s:   # 글마다 우주의 묶음 · 해(무료) → 묶음 흔들림(churn)
                out[-1]["groups"] = {x["id"]: [x.get("group") or x["id"], x["sun_id"]] for x in diary.stars(s)}
            print(k, rec["n"], r["status"], f"생각 {len(r['thoughts'])}", f"{r['seconds']}초", f"${r['usd']}", flush=True)
    return collect(repo, uid, d, out, k, tag, repeat)


def collect(repo, uid, d, out, k="", tag="", repeat=0):
    """DB 에서 결과를 모은다(run 이 끝난 뒤, 또는 중간에 끊긴 run 을 돈 안 들이고 살릴 때 — out 이 None 이면 DB 로 다시 만든다)."""
    if out is None:   # 끝난 기록을 쓴 시각 순서로 글 번호에 맞춘다(같은 글을 다시 돌린 임시 기록은 끝나지 않아 빠짐)
        with repo.session(uid) as s:
            done = sorted(diary.entries(s, status="done"), key=lambda e: e["written_at"])
            out = []
            for n, e in enumerate(done, 1):
                runs = s.rows("runs", entry_id=e["id"])
                out.append({"n": n, "entry_id": e["id"], "status": "done", "errors": [], "calls": sum(r["calls"] or 0 for r in runs),
                            "seconds": round(sum(float(r["ms"] or 0) for r in runs) / 1000, 1),
                            "usd": round(sum(float(r["est_usd"] or 0) for r in runs), 4),
                            "step_ms": {r["step"]: r["ms"] for r in runs if not r["error_code"]}})
    n_of = {o["entry_id"]: o["n"] for o in out}
    with repo.session(uid) as s:
        sun = {x["id"]: x["name"] for x in diary.suns(s)}
        all_stars = diary.stars(s)
        heads = diary.star_heads(all_stars)
        star = {x["id"]: heads[x["id"]]["name"] for x in all_stars}   # 사용자에게 보이는 이름 = 묶음 머리(rules.groups)
        fine = {x["id"]: x["name"] for x in all_stars}
        ts = [t for t in diary.thoughts(s) if t["entry_id"] in n_of]
        rels = diary.relations(s)
        ins = views.insight(s)
    vecs = repo.vectors.get(uid)
    thoughts = [{"id": t["id"], "n": n_of[t["entry_id"]], "position": t["position"], "topic": star.get(t["star_id"], t.get("topic")),
                 "fine": fine.get(t["star_id"], t.get("topic")),
                 "ai_topic": (t.get("original") or {}).get("topic") or fine.get(t["star_id"], t.get("topic")),
                 "domain": sun.get(t["sun_id"]), "domain_first": t.get("domain_first"), "sun_id": t["sun_id"], "kind": t["kind"],
                 "quote": t.get("quote", "")} for t in ts]
    tn = {t["id"]: t["n"] for t in thoughts}
    relations = [{"type": r["type"], "line": r["line"], "from": r["from"], "to": r["to"], "from_n": tn.get(r["from"]),
                  "to_n": tn.get(r["to"])} for r in rels]
    reps = []
    for rec in [r for r in records(d) if not d["entries"][r["n"] - 1]["off_axis"]][-repeat:] if repeat else []:
        got, prior = [], {t["topic"]: t["domain"] for t in thoughts if t["n"] < rec["n"]}
        for _ in range(K - 1):   # 첫 번째는 위 서비스 길 결과
            items, v, usd = record_once(repo, uid, rec, prior)
            q3.ledger_line(f"가상 인물 {k} {rec['n']}/20 {tag} 같은 글 다시(기록 Agent, pass^k)", 1, usd)
            vecs.update(v)
            got.append(items)
        rep = {"n": rec["n"], "runs": got}
        if config.STAR_GROUPS:   # 묶음 기준 일관성: 이 글보다 먼저 쓴 글의 작은 별 + 이번 이름을 서비스와 같은 묶기로(Solar 두 번씩)
            rep["group_sets"] = group_sets([t for t in thoughts if t["n"] < rec["n"]],
                                           [[{"name": t["ai_topic"], "domain": t["domain_first"] or t["domain"], "quote": t["quote"]}
                                             for t in thoughts if t["n"] == rec["n"]]] + got, k, tag)
        reps.append(rep)
        print(k, rec["n"], "다시", [[i["name"] for i in g] for g in got], rep.get("group_sets"), flush=True)
    return {"entries": out, "thoughts": thoughts, "relations": relations, "insight": ins, "repeats": reps}, vecs


def group_sets(prior, runs, k, tag):
    """같은 글을 여러 번 정리한 결과(runs: [[{name, domain, quote}]])마다, 먼저 쓴 글의 작은 별(prior)과 함께 묶어
    이 글의 생각이 앉은 묶음 이름 집합. 유료(Solar 두 번 × 번), 원장에 적는다."""
    from app.core import llm
    from app.service.rules import groups as group_rules
    base = {}
    for t in prior:
        if t["fine"] != OTHER:
            x = base.setdefault(t["fine"], {"name": t["fine"], "sun": t["domain_first"] or t["domain"], "records": set(), "quotes": []})
            x["records"].add(t["n"])
            x["quotes"].append(t["quote"])
    out = []
    with llm.guard([]) as m:
        for items in runs:
            stars = {n: {**x, "records": set(x["records"]), "quotes": list(x["quotes"])} for n, x in base.items()}
            by = {norm_key(n): n for n in stars}
            mine = []
            for i in items:
                if i["name"] == OTHER:
                    continue
                n = by.get(norm_key(i["name"]), i["name"])
                x = stars.setdefault(n, {"name": n, "sun": i["domain"], "records": set(), "quotes": []})
                x["records"].add("이 글")
                x["quotes"].append(i.get("quote", ""))
                mine.append(n)
            rows = [{**x, "id": n, "records": len(x["records"])} for n, x in stars.items()]
            groups, suns = agent_tools.group_stars(rows, [])
            plan = group_rules.apply(rows, groups, suns)
            out.append(sorted({plan[n]["head"] for n in mine}))
    q3.ledger_line(f"가상 인물 {k} {tag} 같은 글 묶음 일관성(Solar 묶기 {len(runs)}번)", m.calls, m.usd)
    return out


##################################################
# 점수(무료): 3계층 중 최종 결과 + 단계(작은 별 · 해 · 지난 생각 잇기)
##################################################

def gt_sets(d):
    return {e["n"]: set(e["topics"]) for e in d["entries"] if not e["off_axis"]}


def pair_f1(sys_sets, gt):
    """글 둘씩: 정답에서 같은 주제를 나누는가 vs 시스템에서 같은 작은 별을 나누는가 → 정밀도 · 재현율 · F1."""
    tp = fp = fn = 0
    for a, b in itertools.combinations(sorted(gt), 2):
        g, s = bool(gt[a] & gt[b]), bool(sys_sets.get(a, set()) & sys_sets.get(b, set()))
        tp, fp, fn = tp + (g and s), fp + (s and not g), fn + (g and not s)
    p, r = tp / (tp + fp) if tp + fp else 0.0, tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}


def entry_stars(thoughts, key="topic"):
    out = {}
    for t in thoughts:
        if t[key] != OTHER:
            out.setdefault(t["n"], set()).add(t[key])
    return out


def score(d, res, stars_by_n=None):
    gt = gt_sets(d)
    tops = {t["id"]: t["domain"] for t in d["topics"]}
    sys_sets = stars_by_n or entry_stars(res["thoughts"])
    want = {e["n"]: {tops[x] for x in e["topics"]} or {"그 밖"} for e in d["entries"]}
    dom_ok = [t["domain"] in want[t["n"]] for t in res["thoughts"]]
    pairs = {(min(r["from_n"], r["to_n"]), max(r["from_n"], r["to_n"]), r["type"])
             for r in res["relations"] if r["from_n"] and r["to_n"] and r["from_n"] != r["to_n"]}
    found = [g for g in d["links"] if any(a == g["from_entry"] and b == g["to_entry"] for a, b, _ in pairs)]   # 글 쌍 기준
    quote = {t["id"]: agent_tools.norm(t["quote"]) for t in res["thoughts"]}
    near = lambda q, g: bool(q) and (q in agent_tools.norm(g) or agent_tools.norm(g) in q)   # noqa: E731
    by_quote = [g for g in d["links"] if any(
        {near(quote.get(r["from"], ""), g["from_quote"]) and near(quote.get(r["to"], ""), g["to_quote"]),
         near(quote.get(r["to"], ""), g["from_quote"]) and near(quote.get(r["from"], ""), g["to_quote"])} & {True}
        for r in res["relations"])]   # 인용 기준: 정답 문장끼리 이었나
    typed = [g for g in d["links"] if (g["from_entry"], g["to_entry"], g["type"]) in pairs]
    planted = {(g["from_entry"], g["to_entry"]) for g in d["links"]}
    covered = []
    for ins in d["insights"]:
        ev = set(ins["evidence_entries"])
        linked = any(a in ev and b in ev for a, b, _ in pairs)
        grouped = any(len({n for n in ev if star in sys_sets.get(n, set())}) >= 2 for star in set().union(*sys_sets.values()))
        covered.append({"id": ins["id"], "linked": linked, "grouped": grouped})
    n_stars = len({s for v in sys_sets.values() for s in v})
    return {
        "stars": n_stars, "gt_topics": len(d["topics"]),
        "topic_pairs": pair_f1(sys_sets, gt),
        "domain_acc": round(sum(dom_ok) / len(dom_ok), 3) if dom_ok else None,
        "links_planted": len(d["links"]), "links_found": len(found), "links_found_same_type": len(typed),
        "links_recall": round(len(found) / len(d["links"]), 3), "links_found_quote": len(by_quote),
        "relations_shown": len(pairs), "relations_unplanted": sum((a, b) not in planted for a, b, _ in pairs),
        "insights_linked": sum(c["linked"] for c in covered), "insights_grouped": sum(c["grouped"] for c in covered),
        "insights": len(covered),
        "failed_entries": sum(e["status"] != "done" for e in res["entries"]),
        "group_pass_k": (lambda r: {"pass": sum(len({tuple(x) for x in g}) == 1 for g in r), "of": len(r)} if r else None)(
            [x["group_sets"] for x in res.get("repeats") or [] if x.get("group_sets")]),
        "group_churn": churn([e["groups"] for e in res["entries"] if e.get("groups")]),
        "usd": round(sum(e["usd"] for e in res["entries"]), 3),
    }


def churn(snaps):
    """글마다 찍은 묶음 [{별 id: [머리 id, 해]}] → 글 하나를 쓸 때 우주가 얼마나 다시 섞이나(평균).
    pairs = 앞뒤 글에 다 있던 별끼리, 한쪽에서라도 같은 묶음이던 짝 중 같이/따로가 바뀐 비율. suns = 해가 바뀐 별 비율."""
    pair, sun = [], []
    for a, b in zip(snaps, snaps[1:]):
        ids = sorted(set(a) & set(b))
        tog = [(x, y) for x, y in itertools.combinations(ids, 2) if a[x][0] == a[y][0] or b[x][0] == b[y][0]]
        if tog:
            pair.append(sum((a[x][0] == a[y][0]) != (b[x][0] == b[y][0]) for x, y in tog) / len(tog))
        if ids:
            sun.append(sum(a[x][1] != b[x][1] for x in ids) / len(ids))
    return {"pairs": round(sum(pair) / len(pair), 3) if pair else 0.0, "suns": round(sum(sun) / len(sun), 3) if sun else 0.0,
            "steps": len(sun)} if sun else None


##################################################
# 작은 별 맞추기 문턱 고르기 · pass^k(무료, 저장한 벡터로 place_stars 를 다시)
##################################################

def simulate(seq, tau, center, stars=None, pools=None):
    """seq: 글 순서대로 [[{name, sun_id, vec}]] → 글마다 작은 별 이름 목록. 서비스와 같은 place_stars + 이름 맞춤(띄어쓰기 무시)."""
    stars, pools, ids = dict(stars or {}), {k: {s: list(v) for s, v in p.items()} for k, p in (pools or {}).items()}, itertools.count()
    out = []
    for items in seq:
        by = {norm_key(n): n for n in stars}
        placed = place_stars([{"topic": by.get(norm_key(i["name"]), i["name"]), "sun_id": i["sun_id"], "vec": i["vec"],
                               "keep_name": i["name"] == OTHER} for i in items], stars, pools, lambda: f"sim{next(ids)}", center, tau)
        out.append([p[0] for p in placed])
    return out


def seq_of(res, vecs):
    by_n = {}
    for t in sorted(res["thoughts"], key=lambda t: (t["n"], t["position"])):
        by_n.setdefault(t["n"], []).append({"name": t["ai_topic"], "sun_id": t["sun_id"], "vec": vecs[t["id"]]})
    return sorted(by_n.items())


def stars_at(res, vecs, tau, center):
    seq = seq_of(res, vecs)
    names = simulate([items for _, items in seq], tau, center)
    return {n: {x for x in ns if x != OTHER} for (n, _), ns in zip(seq, names)}


def pass_k(res, vecs, tau, center):
    """같은 글 K번(서비스 길 1번 + 기록 Agent 다시 K-1번)이 모두 같은 작은 별 묶음이면 통과. 그 글보다 먼저 쓴 글이 쌓인 상태를 놓고 잰다."""
    if not res.get("repeats"):
        return None
    ok = 0
    for rep in res["repeats"]:
        rest = [t for t in res["thoughts"] if t["n"] < rep["n"]]
        stars, pools = {}, {}
        for t in rest:   # 다른 글의 최종 상태(이름 · 해 · 벡터)를 먼저 깔아 둔다
            sid = stars.setdefault(t["topic"], f"s:{t['topic']}")
            pools.setdefault(t["sun_id"], {}).setdefault(sid, []).append(vecs[t["id"]])
        first = [{"name": t["ai_topic"], "sun_id": t["sun_id"], "vec": vecs[t["id"]]}
                 for t in sorted(res["thoughts"], key=lambda t: t["position"]) if t["n"] == rep["n"]]
        runs = [first] + [[{"name": i["name"], "sun_id": i["sun_id"], "vec": vecs[i["id"]]} for i in r] for r in rep["runs"]]
        got = [frozenset(x for x in simulate([items], tau, center, stars, pools)[0] if x != OTHER) for items in runs]
        ok += len(set(got)) == 1
    return {"pass": ok, "of": len(res["repeats"]), "k": K}


def main(argv=None):
    ap = argparse.ArgumentParser(description="가상 인물 시험(서비스 길)")
    ap.add_argument("cmd", choices=["check", "run", "score", "tune", "collect"])
    ap.add_argument("--account", help="collect: 결과를 모을 로컬 계정 이메일(끊긴 run 살리기)")
    ap.add_argument("result", nargs="?")
    ap.add_argument("--persona", nargs="+", default=["A", "B", "C"])
    ap.add_argument("--train", nargs="+", default=["A", "B"])
    ap.add_argument("--tag", default="")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--tau", type=float)
    ap.add_argument("--react", action="store_true", help="가상 사용자가 점선 관계에 정답대로 맞아요 · 아니에요를 누름(개인 맞춤 Ops ④)")
    a = ap.parse_args(argv)
    if a.cmd == "check":
        for k in a.persona:
            print(k, check(load(k)) or "통과")
        return None
    if a.cmd == "collect":   # 끊긴 run 의 한 인물을 DB 에서 살려 결과 파일에 더한다(유료 호출 없음)
        from app.core import seed
        from app.repository import PgRepo
        (k,) = a.persona
        uid = seed.admin_user(a.account, seed._read(seed.ENV_LOCAL)["DEV_TEST_PASSWORD"])
        res, vecs = collect(PgRepo(config.DATABASE_URL), uid, load(k), None)
        path = Path(a.result)
        out = json.loads(path.read_text(encoding="utf-8"))
        out["personas"][k] = {**res, "score": score(load(k), res)}
        (RESULTS / "vectors" / f"{path.stem}-{k}.json").write_text(json.dumps(vecs), encoding="utf-8")
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(k, json.dumps(out["personas"][k]["score"], ensure_ascii=False))
        return out
    if a.cmd == "run":
        if not a.tag:
            ap.error("run 은 --tag 가 필요합니다")
        if q3.ledger_total() > q3.TOTAL_STOP_USD:
            sys.exit(f"원장 누적이 ${q3.TOTAL_STOP_USD} 를 넘어 멈춥니다.")
        out = {"tag": a.tag, "profile": config.ONTOLOGY_PROFILE or "v8", "star_join": config.STAR_JOIN_SIM,
               "star_groups": config.STAR_GROUPS,
               "config": {"record": config.V8_RECORD_CONFIG_ID, "observe": config.V8_OBSERVE_CONFIG_ID}, "personas": {}}
        path = RESULTS / f"{date.today().isoformat()}-persona-{a.tag}.json"
        (RESULTS / "vectors").mkdir(parents=True, exist_ok=True)
        for k in a.persona:
            res, vecs = run_persona(k, load(k), a.tag, a.repeat, a.react)
            out["personas"][k] = {**res, "score": score(load(k), res)}
            (RESULTS / "vectors" / f"{path.stem}-{k}.json").write_text(json.dumps(vecs), encoding="utf-8")
            path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")   # 인물마다 저장(중간에 멈춰도 남게)
            print(k, json.dumps(out["personas"][k]["score"], ensure_ascii=False), f"원장 합계 ${q3.ledger_total():.2f}", flush=True)
        print("→", path.relative_to(ROOT))
        return out
    res_all = json.loads(Path(a.result).read_text(encoding="utf-8"))
    stem = Path(a.result).stem
    vec = {k: json.loads((RESULTS / "vectors" / f"{stem}-{k}.json").read_text()) for k in res_all["personas"]}
    center = agent_tools.sun_vectors()[1]
    if a.cmd == "score":
        for k, res in res_all["personas"].items():
            s = score(load(k), res, stars_at(res, vec[k], a.tau, center) if a.tau else None)
            print(k, json.dumps({**s, "pass_k": pass_k(res, vec[k], a.tau, center)}, ensure_ascii=False))
        return None
    # tune: 학습용 인물(--train)로 문턱을 고르고, 나머지는 고른 값으로만 본다(맞춰 놓고 그 인물로 채점하지 않게)
    grid = [None] + [round(0.05 * i, 2) for i in range(2, 13)]
    rows = {tau: {k: pair_f1(stars_at(r, vec[k], tau, center), gt_sets(load(k)))["f1"] for k, r in res_all["personas"].items()}
            for tau in grid}
    for tau, f in rows.items():
        stars = {k: len({x for v in stars_at(r, vec[k], tau, center).values() for x in v}) for k, r in res_all["personas"].items()}
        print(f"tau {tau}: F1 {f}  작은 별 {stars}")
    train = [k for k in a.train if k in res_all["personas"]]
    best = max(grid[1:], key=lambda t: (sum(rows[t][k] for k in train), -t))
    print(f"고른 문턱 {best} (학습 {train} 평균 F1 {sum(rows[best][k] for k in train) / len(train):.3f},"
          f" 끔 {sum(rows[None][k] for k in train) / len(train):.3f})")
    return best


if __name__ == "__main__":
    main()
