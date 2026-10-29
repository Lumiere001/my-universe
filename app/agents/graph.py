"""
app/agents/graph.py

LangGraph Super Graph: 일기 한 편을 safety → names → record → past → observe → voice → save 로 처리한다.
- record_extractor 하위 그래프: 입력 만들기 → 기록 Agent → 정리(rules.clean_record · 관문)
  → 온톨로지(해 정하기 → 작은 별 맞추기 → 생각 벡터를 해 · 작은 별 메타와 함께 Chroma 에)
  → 작은 별 묶기(group_stars: 새 작은 별이 생긴 글이면 쌓인 작은 별 전체를 같은 고민끼리 묶고 묶음마다 해를 고른다, rules.groups)
- 지난 생각 고르기 · 관측 Agent · 관계 규칙은 묶음 이름(group_topic)으로 '같은 주제'를 본다
- observer 하위 그래프: 지난 생각 고르기(rules.pick_past) → 관측 Agent → 규칙(filter_relations)
- 위기여도 흐름은 같다(시험 단계, 2026-10-08 동규): 감지 결과만 암호화해 남기고, 한마디는 위로 + 안부 한 줄(voice).
- 외부 호출(Studio · Solar)은 모두 llm.guard 안에서 보내기 직전에 실명 검사.
- 노드가 끝날 때마다 상태를 entries.steps_enc 에 암호화해 남긴다. 끊긴 뒤 다시 돌리면 끝난 노드는 건너뛴다(resume).
- 대화에서 온 초안(entries.confirmed = '확인 전')은 voice 뒤 save 앞에서 멈춘다. 확인 화면이 고친 뒤 다시 돌리면 save 만 돈다(WS20).
"""

import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import studio, tools
from app.core import config, llm, logger, trace
from app.core.ontology import load
from app.repository import diary, edit
from app.service import voice as voice_rules
from app.service.rules import groups as group_rules
from app.service.rules import advance, clean_record, clean_text, filter_relations, link_domain, place_stars, reask_trigger, to_sun
from app.service.rules.topics import profile
from app.service.rules.normalize import key as norm_key
from app.service.safety import RealNameLeak, detect_crisis, find_new_names
from app.service.studio_format import parse_record

STEPS = [("safety", "글을 살펴보는 중"), ("names", "사람 이름을 가리는 중"), ("record", "생각을 나누는 중"),
         ("past", "지난 생각을 찾는 중"), ("observe", "이어진 생각을 살피는 중"), ("voice", "별지기가 한마디를 고르는 중"),
         ("save", "우주에 저장하는 중")]
LABEL = dict(STEPS)
ORDER = [s for s, _ in STEPS]


class State(TypedDict, total=False):
    user_id: str
    entry_id: str
    title: str
    text: str
    written_at: str          # ISO
    day: str                 # 쓴 날(현지)
    weather: Any
    done: list               # 끝난 노드
    crisis: bool
    crisis_unsure: bool      # 위기 2차 판정(Solar)이 실패함 → 안부 한 줄만
    people: list             # 사람 목록(가명 표). 이 글에서 자동 등록한 사람 포함
    questions: list          # 헷갈리는 이름 질문 id
    topics: dict             # 기존 작은 별 {이름: 해}
    stars_new: int           # 이 글에서 새로 생긴 작은 별 수(group_stars 가 본다)
    record_raw: dict         # 기록 Agent 추출(원래 이름)
    record: dict             # 글 정보(요약 · 말 거는 대상 · 사건)
    kept: list               # 관문을 지난 생각(작은 별 · 해를 정하기 전)
    today: list              # 오늘 생각(id · 작은 별 · 해 포함)
    dropped_quotes: int
    past: list               # 고른 지난 생각
    observed: dict           # 관측 Agent 결과
    relations: list          # 규칙을 거친 관계
    reached: list
    voice: dict
    hold: bool               # 요약 확인 전: voice 뒤 save 앞에서 멈춤(WS20)


@dataclass
class Ctx:
    """노드 밖 자원(상태에 넣지 않음): 저장소 · 진행 알림."""
    repo: Any
    uid: str
    entry_id: str
    emit: Callable = lambda *_: None

    def progress(self, step):
        self.emit({"entry_id": self.entry_id, "step": step, "label": LABEL[step], "done": ORDER.index(step) + 1,
                   "total": len(ORDER)})


def error_code(e):
    if isinstance(e, studio.StudioError):
        return e.code
    if isinstance(e, RealNameLeak):
        return "real_name_leak"
    if type(e).__module__.startswith("openai"):
        return "llm_failed"
    return "internal"


def node(name, progress=None):
    """노드 감싸기: 진행 알림 → (끝난 노드면 건너뜀) → 실명 검사 guard 안에서 실행 → 상태 암호화 저장 · 원문 없는 실행 기록."""
    def deco(fn):
        def run(state, config):   # LangGraph 는 인자 이름 config 를 보고 실행 설정을 넘긴다(그래서 wraps 를 쓰지 않음)
            with trace.span(name, kind="CHAIN"):   # 단계 하나 = span 하나(속성은 runs 행과 같은 숫자만)
                return step(state, config)

        def step(state, config):
            ctx = config["configurable"]["ctx"]
            if progress:
                ctx.progress(progress)
            if name in state.get("done", []):
                logger.log("step", step=name, entry_id=ctx.entry_id, skipped=True)
                trace.set(skipped=True)
                return {}
            t0 = time.time()
            with llm.guard(state.get("people") or []) as m:
                try:
                    out = fn(state, ctx) or {}
                except Exception as e:
                    code = error_code(e)
                    logger.log("error", step=name, entry_id=ctx.entry_id, code=code, calls=m.calls, what=type(e).__name__)
                    trace.set(error_code=code, calls=m.calls, est_usd=m.usd)
                    with ctx.repo.session(ctx.uid) as s:
                        diary.add_run(s, ctx.entry_id, name, (time.time() - t0) * 1000, m.calls, m.usd, code)
                    raise
            done = state.get("done", []) + [name]
            meta = {"checks": out.pop("_checks")} if "_checks" in out else {}   # 문제 개수만(상황 · 문제 이름은 남기지 않음)
            ms = (time.time() - t0) * 1000
            with ctx.repo.session(ctx.uid) as s:
                if name != "save":
                    diary.checkpoint(s, ctx.entry_id, name, {**state, **out, "done": done})
                diary.add_run(s, ctx.entry_id, name, ms, m.calls, m.usd, None, meta)
            logger.log("step", step=name, entry_id=ctx.entry_id, ms=int(ms), calls=m.calls, est_usd=round(m.usd, 4),
                       **meta)
            trace.set(calls=m.calls, est_usd=m.usd, **meta)
            return {**out, "done": done}
        run.__name__ = name
        return run
    return deco


##################################################
# safety · names
##################################################

@node("safety", "safety")
def safety(state, ctx):
    # 규칙이 놓친 돌려 말하기는 Solar 가 한 번 더 본다(가명 처리 · 실명 검사는 detect_crisis 안에서)
    with ctx.repo.session(ctx.uid) as s:
        people = diary.people(s)
    found = detect_crisis(f"{state.get('title', '')}\n{state['text']}", people=people, llm=True)
    return {"crisis": found["crisis"], "crisis_unsure": any(x["type"] == "llm_error" for x in found["signals"])}


@node("names", "names")
def names(state, ctx):
    """새 이름 자동 등록(가명으로 보내기 위해), 헷갈리는 이름은 질문으로 남긴다."""
    with ctx.repo.session(ctx.uid) as s:
        people = diary.people(s)
        found = find_new_names(f"{state.get('title', '')}\n{state['text']}", people)
        for n in found["auto"]:
            people.append(diary.add_person(s, n, auto=True))
        asked = {q["name"] for q in diary.questions(s)}
        qs = [diary.add_question(s, ctx.entry_id, a["name"], a["reason"]) for a in found["ask"] if a["name"] not in asked]
    logger.log("step", step="names", entry_id=ctx.entry_id, people_new=len(found["auto"]), questions=len(qs))
    return {"people": [{k: p[k] for k in ("id", "name", "nicknames", "relation")} for p in people], "questions": qs}


##################################################
# record_extractor 하위 그래프
##################################################

@node("record_input", "record")
def record_input(state, ctx):
    with ctx.repo.session(ctx.uid) as s:
        sun = {x["id"]: x["name"] for x in diary.suns(s)}
        topics = {st["name"]: sun.get(st["sun_id"]) for st in diary.stars(s)}
    # 기록 Agent 에게는 작은 별 이름 전체를 준다(묶음 이름만 주면 기존 이름을 못 다시 써서 새 이름이 늘었다 — 가상 인물 E 22 → 43개)
    return {"topics": topics}


OTHER_TOPIC = "기타 생각"   # 가치 이름 · 빈 주제를 모으는 작은 별(match_topic 표시, 2026-10-08 동규 · 오케스트레이터 추천)


@node("record_agent")
def record_agent(state, ctx):
    topics = [t for t in state["topics"] if t != OTHER_TOPIC]   # 모으는 별은 기록 Agent 에게 고를 이름으로 주지 않는다
    return {"record_raw": tools.run_record_agent(state.get("title", ""), state["text"], topics, state["people"])}


def _quote_ok(quote, source):
    """G1: 인용이 원문에 글자 그대로 있어야 한다. 빈 인용은 근거가 없으니 버린다(WS12)."""
    q = tools.norm(quote)
    return bool(q) and q in tools.norm(source)


@node("record_clean")
def record_clean(state, ctx):
    raw = parse_record(state["record_raw"])
    for t in raw["thoughts"]:   # 기타(원래 말) · 감정(감사)를 rules 가 다시 판단하게 원래 말로 넘긴다
        for f in ("kind", "certainty", "value"):
            if t.get(f"{f}_original"):
                t[f] = t[f"{f}_original"]
        if "감사" in t.get("flags", []):
            t["kind"] = "감사"
    with ctx.repo.session(ctx.uid) as s:
        custom = [x["name"] for x in diary.suns(s) if x["custom"]]
        aliases = diary.profile(s)[0].get("topic_aliases")   # WS16: 사용자가 합친 작은 별의 옛 이름 → 합친 이름
    topics = state["topics"]
    rec = clean_record(raw, state["people"], {k: v for k, v in topics.items() if v}, custom, aliases)
    source = f"{state.get('title', '')}\n{state['text']}"
    kept = [t for t in rec["thoughts"] if _quote_ok(t["quote"], source)]   # 원문에 없는 인용은 버린다(1차 G1)
    for t in kept:
        if {"가치 이름", "빈 주제"} & set(t["problems"]):
            t["topic"], t["domain"] = OTHER_TOPIC, topics.get(OTHER_TOPIC) or t["domain"]
    info = {k: rec[k] for k in ("summary", "addressee", "events", "record_type", "original")}
    info["summary"] = clean_text(info["summary"], source)   # G3 + 내부 번호
    return {"record": info, "kept": kept, "dropped_quotes": len(rec["thoughts"]) - len(kept)}


@node("ontology")
def ontology(state, ctx):
    """온톨로지에 붙이기: ① 해 정하기(대표 낱말 → 중심 보정 임베딩으로 기준 축, 두 영역 모드면 커리어 · 인간관계 · 그 밖으로 묶음)
    ② 작은 별 맞추기(기존 이름 · 비슷한 말이면 그 별, 새 이름이면 STAR_JOIN_SIM 이 켜졌을 때 같은 해 작은 별 중심과 비교)
    ③ 생각 벡터를 해 · 작은 별 메타와 함께 Chroma 에 넣기."""
    kept = state.get("kept")
    if kept is None:   # 이 단계가 생기기 전(10/29)에 record_clean 이 여기까지 끝낸 이어 하기 상태
        return {}
    topics = state["topics"]
    with ctx.repo.session(ctx.uid) as s:
        custom = [x["name"] for x in diary.suns(s) if x["custom"]]
    tvecs = tools.embed([t["thought"] or t["quote"] for t in kept], state["people"])   # 생각 벡터(가명 글)
    # 낱말로 해를 못 정한 새 주제는 이 글에서 그 주제가 붙은 생각들의 평균 벡터로 정한다. 주제 이름(몇 낱말)의 벡터로 정하면
    # 가상 인물 A 의 해가 59% 만 맞았고, 생각 문장 평균으로는 86%(낱말 먼저 규칙은 그대로, 2026-10-29 tools/persona_eval.py)
    tmean = {}
    for t, v in zip(kept, tvecs):
        tmean.setdefault(t["topic"], []).append(v)
    tmean = {k: [sum(c) / len(vs) for c in zip(*vs)] for k, vs in tmean.items()}
    sun_vecs, center = tools.sun_vectors()
    if not (sun_vecs and center and tvecs and len(tvecs[0]) == len(center)):   # 다른 임베딩 모델이면 벡터 보충을 건너뜀
        sun_vecs, center = None, None
    if sun_vecs and profile():   # 두 영역 모드: 낱말로 안 정해지면 두 영역 중 하나로(멘토링 '틀을 강제로 잡기').
        # '그 밖'은 주제 이름의 낱말이 그 축을 가리킬 때만(예: 운동 · 여행). 가상 인물 해 맞힌 비율 A 86 · B 78 → 81 · C 44 → 67%
        sun_vecs = {k: v for k, v in sun_vecs.items() if to_sun(k) != profile()["other"]}
    by_name = {norm_key(n): n for n in topics}
    tau = config.STAR_JOIN_SIM if center else None   # 문턱은 중심 보정 코사인 기준이라 중심이 없으면 맞추기를 끈다
    today, people_id, items = [], {}, []
    for p in state["people"]:
        for n in [p["name"], *(p.get("nicknames") or [])]:
            people_id[n] = p["id"]
    with ctx.repo.session(ctx.uid) as s:
        all_stars = diary.stars(s)
        stars = {st["name"]: st["id"] for st in all_stars}
        for i, t in enumerate(kept):   # ① 해 정하기
            domain = to_sun(t["domain"] or (sun_vecs and link_domain(t["topic"], tmean[t["topic"]], sun_vecs, center, custom))
                            or "삶의 성취")
            items.append({"topic": by_name.get(norm_key(t["topic"]), t["topic"]), "domain": domain, "vec": tvecs[i],
                          "sun_id": diary.ensure_sun(s, domain, custom=domain in custom), "keep_name": t["topic"] == OTHER_TOPIC})
        pools = {}
        if tau:   # 같은 해의 지난 생각 벡터를 작은 별별로. 어느 별 · 어느 해인지는 DB 가 정답(옮기기 · 합치기 · 해 표시가 없는 옛 벡터도 맞게)
            member = {r["id"]: r["star_id"] for r in s.rows("thoughts")}   # 생각 → 작은 별(복호화 없이)
            star_sun = {st["id"]: st["sun_id"] for st in all_stars}
            live, want = set(stars.values()), {it["sun_id"] for it in items}   # 이름이 같은 별이 둘이면 stars 에는 하나만 남는다
            for vid, v in ctx.repo.vectors.get(ctx.uid).items():
                sid = member.get(vid)
                if sid in live and star_sun.get(sid) in want:
                    pools.setdefault(star_sun[sid], {}).setdefault(sid, []).append(v)
        placed = place_stars(items, stars, pools, lambda: diary.new_id("s"), center, tau)   # ② 작은 별 맞추기
        for i, (t, it, (name, new, _)) in enumerate(zip(kept, items, placed)):
            if new:
                diary.add_star(s, stars[name], name, it["sun_id"])
            original = {**t["original"], **({"topic": t["topic"]} if name != t["topic"] else {})}   # 기록 Agent 가 낸 이름
            today.append({**{k: t[k] for k in ("thought", "kind", "certainty", "value", "quote", "self_change", "flags")},
                          "original": original, "topic": name, "domain": it["domain"], "domain_first": it["domain"],   # 묶기 전 해
                          "id": diary.thought_id(ctx.entry_id, i),
                          "record_id": ctx.entry_id,
                          "record_type": state["record"]["record_type"],   # 시 · 창작이면 관계를 잇지 않는다(rules.filter_relations)
                          "day": state["day"], "written_at": state["written_at"], "position": i, "star_id": stars[name],
                          "sun_id": it["sun_id"],   # 기록 Agent 의 사람 칸 + 생각 · 인용에 이름이 그대로 나온 사람
                          "people": sorted({people_id[n] for n in t["people"] if n in people_id}
                                           | {pid for n, pid in people_id.items() if n in t["thought"] + t["quote"]})})
    # ③ 생각 벡터를 해 · 작은 별 메타와 함께 Chroma 에
    ctx.repo.vectors.upsert(ctx.uid, [{"id": t["id"], "emb": v, "entry_id": ctx.entry_id, "sun_id": t["sun_id"],
                                       "star_id": t["star_id"], "written_at": state["written_at"], "kind": t["kind"]}
                                      for t, v in zip(today, tvecs)])
    trace.set(profile=config.ONTOLOGY_PROFILE or "v8", stars_new=sum(p[1] for p in placed),   # 강의 5강: span 에 평가 신호
              stars_joined=sum(p[2] for p in placed), other_sun=sum(t["domain"] == (profile() or {}).get("other") for t in today))
    return {"today": today, "stars_new": sum(p[1] for p in placed)}


##################################################
# observer 하위 그래프
##################################################

@node("past", "past")
def past(state, ctx):
    return {"past": tools.search_past(ctx.repo, ctx.uid, ctx.entry_id, grouped(state["today"])) if state["today"] else []}


@node("observe", "observe")
def observe(state, ctx):
    if not state["today"]:
        return {"observed": {}}
    with ctx.repo.session(ctx.uid) as s:
        asp = (diary.aspirations(s) or [None])[-1]
    a = {"said": asp["said"], "value": (asp["values"] or [""])[0]} if asp else None
    return {"observed": tools.run_observe_agent(state["day"], grouped(state["today"]), state["past"], a, state["people"])}


@node("rules")
def rules(state, ctx):
    obs = state.get("observed") or {}
    ts = {t["id"]: t for t in grouped(state["today"]) + state["past"]}   # 판단형은 같은 묶음 안에서만(rules.groups)
    source = tools.norm(state["text"] + "".join(f"{t.get('quote', '')}{t.get('thought', '')}" for t in ts.values()))
    cands = [{"a": r["from"], "b": r["to"], "type": r["type"], "explanation": r.get("explanation", ""),
              "quoted": bool(r.get("evidence")) and tools.norm(r["evidence"]) in source,
              "author_stated": r.get("author_stated"), "axis": r.get("axis", ""), "topic": r.get("topic", ""),
              "quote": r.get("evidence") or None} for r in obs.get("relations", [])]
    with ctx.repo.session(ctx.uid) as s:
        states = diary.states(s)
    kept, dropped = filter_relations(cands, ts, states)
    quote = {frozenset((c["a"], c["b"])): c["quote"] for c in cands if c["quoted"]}
    for k in kept:
        k["quote"] = quote.get(frozenset((k["from"], k["to"])))
    today_ids = {t["id"] for t in state["today"]}
    reached = [{**r, "explanation": clean_text(r.get("explanation"), state["text"])}
               for r in obs.get("reached", []) if r["thought"] in today_ids and r.get("evidence")]
    logger.log("step", step="rules", entry_id=ctx.entry_id, relations=len(kept), dropped=len(dropped))
    return {"relations": kept, "reached": reached}


##################################################
# voice · save
##################################################

def _flag(settings, k, day):
    return settings.get(k) == day


def _addressee_person(state):
    """편지처럼 특정 인물에게 쓴 글이면 그 사람 id(이 글의 생각에 처음 나온 사람)."""
    if state["record"].get("addressee") != "특정 인물":
        return None
    return next((p for t in state["today"] for p in t["people"]), None)


PERSON_HISTORY_MAX = 5   # 운영 기본값(연구 근거 아님)


def _person_history(s, pid, done):
    """그 사람이 나온 지난 기록의 요약(최근 것부터). done: 끝난 기록(최근 → 오래된)."""
    tids = [r["thought_id"] for r in s.rows("thought_people", person_id=pid)]
    eids = {t["entry_id"] for t in s.rows("thoughts", id=tids)} if tids else set()
    return [f"{diary.local_day(e['written_at'])} {e['data']['summary']}" for e in done
            if e["id"] in eids and e["data"].get("summary")][:PERSON_HISTORY_MAX]


def _widen_cands(s, state, done, days_written):
    """좁아짐 막기 재료 후보(앞이 우선): 오늘과 맞서는 지난 생각(쌍행성) → 오래 비어 있는 해 → 글이 없는 기준 축."""
    ts = {t["id"]: t for t in state["today"] + state["past"]}
    today_ids = {t["id"] for t in state["today"]}
    out = [{"kind": "twin", "key": f"twin:{r['from']}", "past": ts[r["from"]].get("thought", ""),
            "today": ts[r["to"]].get("thought", ""), "day": ts[r["from"]].get("day")}
           for r in state["relations"] if r["type"] == "긴장" and r["to"] in today_ids and r["from"] in ts
           and r["from"] not in today_ids]
    if days_written < voice_rules.ASPIRATION_AFTER_DAYS:   # 며칠 쓰기 전에는 다른 해를 묻지 않는다
        return out
    sun_name = {x["id"]: x["name"] for x in diary.suns(s)}
    pos = {e["id"]: i for i, e in enumerate(done)}          # 0 = 가장 최근 기록
    last = {}                                               # 해 → 가장 최근에 나온 기록의 순위
    for t in s.rows("thoughts", entry_id=list(pos)) if pos else []:
        last[t["sun_id"]] = min(last.get(t["sun_id"], pos[t["entry_id"]]), pos[t["entry_id"]])
    today_suns = {t["sun_id"] for t in state["today"]}
    quiet = sorted((sid for sid, i in last.items() if i >= voice_rules.QUIET_AFTER_ENTRIES and sid not in today_suns
                    and sid in sun_name), key=lambda sid: -last[sid])
    out += [{"kind": "sun", "key": f"sun:{sun_name[sid]}", "name": sun_name[sid]} for sid in quiet]
    written = {sun_name.get(sid) for sid in last} | {t["domain"] for t in state["today"]}
    out += [{"kind": "axis", "key": f"sun:{d['name']}", "name": d["name"]} for d in load()["domains"] if d["name"] not in written]
    return out


@node("voice", "voice")
def speak(state, ctx):
    day = diary.today()
    with ctx.repo.session(ctx.uid) as s:
        settings, onboarding = diary.profile(s)
        msgs = [diary.message(s, r) for r in s.rows("messages", order="created_at")]
        done = [e for e in diary.entries(s, status="done") if e["id"] != ctx.entry_id]
        states = diary.states(s)
        asp = (diary.aspirations(s) or [None])[-1]
        need = [k for k, v in states.items() if v["kind"] in ("다짐", "질문") and v["state"] == "열림"]
        text_of = {t["id"]: t.get("text", "") for t in diary.thoughts(s, id=need)} if need else {}
        person = _addressee_person(state)
        history = _person_history(s, person, done) if person else []
        days = len({diary.local_day(e["written_at"]) for e in done})
        widen = voice_rules.pick_widen(_widen_cands(s, state, done, days), [m.get("widen", "") for m in msgs])
    vow_kept = {r["from"] for r in state["relations"] if r.get("vow_kept")}
    ts = {t["id"]: t for t in state["today"] + state["past"]}
    changes = [{"before": ts[r["from"]].get("thought", ""), "after": ts[r["to"]].get("thought", ""), "day": ts[r["from"]].get("day")}
               for r in state["relations"] if r["type"] == "바뀜" and r["from"] in ts and r["to"] in ts]
    asked = onboarding.get("aspiration")
    # 이번엔 넘어가기 → 계기가 생기면 다시 묻는다(위기 · 무거운 날에 생긴 계기는 미뤄 둔 것을 다음 글에서)
    reask = asked == "skip" and bool(onboarding.get("reask_pending") or reask_trigger(state["relations"], states))
    commitments = [{"text": text_of.get(k, ""), "state": v["state"], "due": v.get("due"),
                    "overdue": bool(v.get("due") and v["due"] < day)}
                   for k, v in states.items() if v["kind"] == "다짐" and v["state"] == "열림" and k not in vow_kept and text_of.get(k)]
    ctx_v = {
        "tone": settings["tone"], "tone_note": settings.get("tone_note") or "",   # 말투 바람은 tools.speak 가 가명 처리
        "text": state["text"], "summary": state["record"].get("summary", ""),
        "thoughts": [{k: t[k] for k in ("thought", "kind", "certainty", "quote")} for t in state["today"]],
        "weather": state.get("weather"), "addressee": state["record"].get("addressee"), "written_at": state["written_at"],
        "past_messages": [m.get("text", "") for m in msgs],
        "past_check_ins": [m["check_in"] for m in msgs if m.get("check_in")],
        "crisis": state.get("crisis"), "crisis_unsure": state.get("crisis_unsure"),
        "aspiration": {"said": asp["said"], "value": (asp["values"] or [""])[0], "obstacle": asp.get("obstacle"),
                       "if_then": asp.get("if_then")} if asp else None,
        "reached": [{"quote": r["evidence"], "note": r.get("explanation", "")} for r in state.get("reached", [])],
        "commitments": commitments[:5],
        "kept": [text_of.get(k, "") for k in vow_kept if text_of.get(k)],
        "open_questions": [text_of[k] for k, v in states.items() if v["kind"] == "질문" and v["state"] == "열림" and text_of.get(k)][:3],
        "days_written": days,
        "weather_skipped": not settings.get("weather_ask", True),
        "aspiration_step": onboarding.get("aspiration_step"),
        "aspiration_off": asked == "stop" or (asked == "skip" and not reask),   # 그만 묻기만 영구
        "heavy": voice_rules.is_heavy(state["today"], state["record"].get("events")),
        "person_history": history,
        "past_thoughts": [{k: p.get(k) or "" for k in ("thought", "quote", "day")} for p in state["past"]],
        "changes": changes,
        "widen": widen,
        "settings": {"gentle": _flag(settings, "gentle_today", day), "comfort_only": _flag(settings, "comfort_only_today", day),
                     "suggest": {"적게": "안 함", "보통": "가끔", "많이": "자주"}.get(settings.get("suggestions"), "가끔")},
    }
    later = reask and bool(state.get("crisis_unsure") or "무거운 날" in voice_rules.situations(ctx_v))
    if later:   # 위기 · 무거운 날(위기 판정 실패 포함)엔 되고 싶은 모습을 다시 묻지 않고 다음 글로 미룬다
        reask, ctx_v["aspiration_off"] = False, True
    out = tools.speak(ctx_v, state["people"])
    checks = sorted({p.split(":")[0] for c in out["checks"] for p in c.get("problems", [])})
    return {"voice": {**{k: out[k] for k in ("message", "next_question", "mode", "next_kind", "tone", "check_in")},
                      "widen": widen["key"] if widen and out.get("widen") else "", "reask": reask, "reask_later": later,
                      "repeated": any(p.startswith("지난 한마디") for c in out["checks"] for p in c.get("problems", []))},   # WS22
            "_checks": len(checks)}


@node("save", "save")
def save(state, ctx):
    eid = ctx.entry_id
    with ctx.repo.session(ctx.uid) as s:
        e = diary.entry(s, eid)
        # 다시 돌려도 같은 결과가 되게 이 기록의 생각부터 지우고 다시 쓴다
        old = [t["id"] for t in s.rows("thoughts", entry_id=eid)]
        if old:
            s.delete("thought_people", thought_id=old)
            s.delete("relations", to_thought=old)
            s.delete("aspiration_reached", entry_id=eid)
            s.delete("thoughts", entry_id=eid)
        s.delete("messages", entry_id=eid)
        for t in state["today"]:
            diary.save_thought(s, eid, t)
        for r in state["relations"]:
            diary.save_relation(s, r)
        old_states = diary.states(s)
        ts = {t["id"]: t for t in grouped(state["today"]) + state["past"]}
        diary.save_states(s, advance(old_states, ts, state["relations"], eid), old_states)
        asp = (diary.aspirations(s) or [None])[-1]
        if asp:
            for r in state.get("reached", []):
                rid = diary.new_id("rc")
                s.insert("aspiration_reached", {"id": rid, "aspiration_id": asp["id"], "entry_id": eid, "thought_id": r["thought"],
                                                "at": diary.parse_dt(state["written_at"]),
                                                "enc": diary.seal(s, "aspiration_reached", rid, {"quote": r["evidence"],
                                                                                               "note": r.get("explanation", "")})})
        v = state["voice"]
        mid = diary.new_id("m")
        s.insert("messages", {"id": mid, "entry_id": eid, "tone": v["tone"], "next_kind": v["next_kind"],
                              "suggested": voice_rules.checks.has_suggestion(v["message"]), "repeated": v.get("repeated"),   # WS22
                              "enc": diary.seal(s, "messages", mid, {"text": v["message"], "next_question": v["next_question"],
                                                                     "mode": v["mode"], "check_in": v.get("check_in", ""),
                                                                     "widen": v.get("widen", "")})})
        stars = Counter(t["star_id"] for t in state["today"])
        star = max(stars, key=lambda k: (stars[k], -[t["star_id"] for t in state["today"]].index(k))) if stars else None
        sun = next((t["sun_id"] for t in state["today"] if t["star_id"] == star), None)
        info = state["record"]
        person = _addressee_person(state)
        data = {**e["data"], "summary": info.get("summary", ""), "events": info.get("events", []), "addressee_person": person,
                "past": [p["id"] for p in state["past"]], "original": info.get("original") or {}}
        if state.get("crisis"):
            data["crisis"] = True   # 위기 표시는 enc 안에만(얼마나 자주 걸리는지 보려고 남김)
        s.update("entries", {"status": "done", "step": "save", "star_id": star, "sun_id": sun, "addressee": info.get("addressee"),
                             "enc": diary.seal(s, "entries", eid, data), "steps_enc": None, "error_code": None,
                             "record_type": info.get("record_type"), "updated_at": diary.now()}, id=eid)
        ob = {"weather_asked": True} if v["next_kind"] == "weather" else {}
        if v.get("reask"):
            # 이번엔 넘어가기 뒤 계기가 생김 → 되고 싶은 모습을 다시 묻는다(GET /aspiration should_ask)
            ob.update(aspiration="none", reask_pending=False)
        elif v.get("reask_later"):
            ob["reask_pending"] = True
        if ob:
            diary.save_profile(s, onboarding=ob)
    return {}


##################################################
# 작은 별 묶기(rules.groups)
##################################################

def grouped(ts):
    """관측 쪽이 보는 주제 = 묶음 이름(group_stars 가 붙인 group_topic). 저장하는 topic 은 기록 Agent 가 낸 작은 별 이름 그대로."""
    return [{**t, "topic": t.get("group_topic") or t["topic"]} for t in ts]


def regroup(repo, uid, people, today=(), entry_id=None):
    """쌓인 작은 별 전체를 다시 묶는다(Solar 두 번, llm.guard 안에서 부른다 — 이름 · 원문 예는 가명으로 나간다).
    묶음 머리를 작은 별 enc 에 적고, 묶음의 해로 별 · 생각 · 기록의 해를 옮긴다(사용자가 옮긴 별은 그대로). 작은 별은 지우지 않는다.
    매번 처음의 작은 별 전체를 놓고 새로 묶는다(합친 별을 다시 묶으면 눈덩이). 끝난 글의 생각 + 지금 글의 생각(today, 아직 저장 전).
    → {stars, groups, moved} 또는 None(작은 별 2개 미만)."""
    with repo.session(uid) as s:
        when = {e["id"]: e["written_at"] for e in diary.entries(s, status="done")}
        all_ = [x for x in diary.stars(s) if x["name"] != OTHER_TOPIC]   # 모으는 별은 묶지 않는다
        suns = diary.suns(s)
        ts = diary.thoughts(s, entry_id=list(when)) if when else []
        declined = edit.declined(s)
    sun_name = {x["id"]: x["name"] for x in suns}
    custom = [x["name"] for x in suns if x["custom"]]
    info = {x["id"]: ([], set()) for x in all_}
    mine = [{**t, "entry_id": entry_id} for t in today]
    for t in sorted((t for t in ts if t["entry_id"] != entry_id), key=lambda t: (when[t["entry_id"]], t["position"])) + mine:
        if t["star_id"] in info:
            info[t["star_id"]][0].append(t.get("quote") or t.get("text") or t.get("thought") or "")
            info[t["star_id"]][1].add(t["entry_id"])
    # ponytail: 작은 별 전체를 한 번에 보낸다(별 100개 ≈ 입력 4천 토큰 ≈ $0.004). 수백 개가 되면 해마다 나눠 묶기.
    stars = [{"id": x["id"], "name": x["name"], "sun": sun_name.get(x["sun_id"]), "pin": x.get("pin"),
              "records": len(info[x["id"]][1]), "quotes": info[x["id"]][0]} for x in all_ if info[x["id"]][1]]
    if len(stars) < 2:
        return None
    groups, picked = tools.group_stars(stars, people, custom)
    plan = group_rules.apply(stars, groups, picked, declined)
    moved = 0
    with repo.session(uid) as s:
        now = {x["id"]: x for x in diary.stars(s)}
        for st in stars:
            x, p = now.get(st["id"]), plan[st["id"]]
            if not x:
                continue   # 그사이 사용자가 합치거나 지운 별
            head = p["head"] if p["head"] != x["id"] and p["head"] in now else None
            if x.get("group") != head:
                diary.set_star(s, x, group=head)
            if p["sun"] and p["sun"] != sun_name.get(x["sun_id"]) and not x.get("pin"):
                edit.set_sun(s, x["id"], diary.ensure_sun(s, p["sun"], custom=p["sun"] in custom), p["sun"])
                moved += 1
        diary.save_profile(s, settings={"groups_profile": config.ONTOLOGY_PROFILE or "v8"})
    return {"stars": len(stars), "groups": len({p["head"] for p in plan.values()}), "moved": moved}


def ensure_groups(repo, uid):
    """묶음이 지금 모드로 만들어진 적이 없으면(두 영역 모드를 켠 뒤 · 묶기가 생기기 전 글만 있는 사용자) 우주를 열 때 한 번 묶는다
    — 기존 해 옮기기를 따로 하지 않아도 된다. 정리 중인 글이 있으면 다음에. 실패하면 그대로 보여 준다."""
    mode = config.ONTOLOGY_PROFILE or "v8"
    if not config.STAR_GROUPS:
        return None
    with repo.session(uid) as s:
        if diary.profile(s)[0].get("groups_profile") == mode or edit.busy(s):
            return None
        people = diary.people(s)
    t0, out, code = time.time(), None, None
    with llm.guard(people) as m:
        try:
            out = regroup(repo, uid, people)
        except Exception as e:
            code = error_code(e)
            logger.log("error", step="group_stars", code=code, what=type(e).__name__)
    with repo.session(uid) as s:
        diary.add_run(s, None, "group_stars", (time.time() - t0) * 1000, m.calls, m.usd, code)
        if out is None and code is None:   # 작은 별이 2개 미만: 묶을 것이 없다
            diary.save_profile(s, settings={"groups_profile": mode})
    return out


@node("group_stars")
def group_stars(state, ctx):
    """④ 작은 별 묶기(관측 전): 새 작은 별이 생긴 글이면 쌓인 작은 별 전체(이 글 포함)를 다시 묶는다. 이 글의 생각에 묶음 이름
    (group_topic)과 묶음의 해를 붙여 지난 생각 고르기 · 관측 · 관계 규칙이 묶음 단위로 보게 한다. 묶기가 실패해도 글은 이어서 정리한다."""
    today = state.get("today") or []
    if not (config.STAR_GROUPS and today):
        return {}
    if state.get("stars_new"):
        try:
            out = regroup(ctx.repo, ctx.uid, state.get("people") or [], today, ctx.entry_id)
            if out:
                trace.set(**{f"group_{k}": v for k, v in out.items()})   # 강의 5강: span 에 평가 신호(별 수 · 묶음 수)
        except Exception as e:
            logger.log("error", step="group_stars", entry_id=ctx.entry_id, code=error_code(e), what=type(e).__name__)
            trace.set(error_code=error_code(e))
    with ctx.repo.session(ctx.uid) as s:
        all_ = diary.stars(s)
        sun_name = {x["id"]: x["name"] for x in diary.suns(s)}
    heads, star_sun = diary.star_heads(all_), {x["id"]: x["sun_id"] for x in all_}
    out = []
    for t in today:
        h, sid = heads.get(t["star_id"]), star_sun.get(t["star_id"])
        if not h or t["topic"] == OTHER_TOPIC:   # 모으는 별은 묶지 않는다
            out.append(t)
            continue
        out.append({**t, "group_topic": h["name"], **({"sun_id": sid, "domain": sun_name[sid]} if sid in sun_name else {})})
    return {"today": out}


##################################################
# 그래프 조립
##################################################

def _sub(nodes):
    g = StateGraph(State)
    prev = START
    for n in nodes:
        g.add_node(n.__name__, n)
        g.add_edge(prev, n.__name__)
        prev = n.__name__
    g.add_edge(prev, END)
    return g.compile()


record_extractor = _sub([record_input, record_agent, record_clean, ontology, group_stars])
observer = _sub([past, observe, rules])


def build():
    g = StateGraph(State)
    g.add_node("safety", safety)
    g.add_node("names", names)
    g.add_node("record", record_extractor)
    g.add_node("observer", observer)
    g.add_node("voice", speak)
    g.add_node("save", save)
    g.add_edge(START, "safety")
    g.add_edge("safety", "names")
    g.add_edge("names", "record")
    g.add_edge("record", "observer")
    g.add_edge("observer", "voice")
    # 대화에서 온 초안(확인 전)은 save 앞에서 멈춘다(WS20). 확인하면 끝난 노드를 건너뛰고 save 만 돈다.
    g.add_conditional_edges("voice", lambda st: END if st.get("hold") else "save", ["save", END])
    g.add_edge("save", END)
    return g.compile()


super_graph = build()


def run(repo, uid, entry_id, emit=lambda *_: None):
    """기록 하나를 처리(처음이든 이어 하기든). 끝난 노드는 건너뛴다. 실패하면 상태를 failed 로 두고 예외를 다시 던진다."""
    ctx = Ctx(repo, str(uid), entry_id, emit)
    with repo.session(uid) as s:
        e = diary.entry(s, entry_id)
    state = e["steps"] or {"user_id": str(uid), "entry_id": entry_id, "title": e["data"].get("title", ""),
                           "text": e["data"]["text"], "written_at": diary.iso(e["written_at"]),
                           "day": diary.local_day(e["written_at"]), "weather": e["weather"], "done": []}
    if e["status"] == "done":
        state["done"] = ORDER + ["record_input", "record_agent", "record_clean", "ontology", "group_stars", "rules"]
    state["hold"] = e.get("confirmed") == "확인 전"   # 요약 확인을 기다림(entries.confirmed, WS20)
    try:
        super_graph.invoke(state, {"configurable": {"ctx": ctx}, "recursion_limit": 50})
    except Exception as err:
        with repo.session(uid) as s:
            diary.set_status(s, entry_id, "failed", error_code(err))
        raise
