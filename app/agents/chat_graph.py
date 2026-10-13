"""
app/agents/chat_graph.py

대화 Agent(WS19): 사용자 말 한 턴을 safety → past → reply → summary 로 처리하는 LangGraph 그래프(2차 가이드 ③ 모양).
- safety: 매 턴 위기 2단 판정(규칙 + Solar). 위기면 그 턴은 위로(팩폭도 다정하게) + 안부 한 줄, 질문 · 제안 없음(시험 단계 방침).
- past: 사용자 말을 가명 처리 → 질의용 임베딩 → 그 사용자의 지난 생각 벡터에서 rules.pick_past(코드 코사인)로 고름.
  '이 이야기 이어 하기'로 연 대화면 그 기록의 생각을 앞에 둔다.
- reply: Solar(app.service.chat 프롬프트) → 말 검사 → 한 번 다시 → 기본 문장. 지난 기록 물음은 원문 인용으로 답하고, 없으면 없다고.
- summary: 몇 턴마다(긴 이야기면 바로) '지금까지 정리'를 사용자 말만 근거로 고쳐 쓴다.
외부 호출은 모두 llm.guard 안에서(보내기 직전 실명 검사). 가명 표 = 사람 목록 + 이 대화의 새 이름 후보(등록은 하지 않음 —
등록은 초안이 일기 그래프의 names 단계를 지날 때). 턴 원문은 conversations.enc 에만, 실행 기록(runs · 로그)에는 턴 수 ·
시간 · 호출 수 · 비용 · 검사 문제 개수만 남긴다.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import graph, tools
from app.core import config, llm, logger
from app.repository import conversations, diary
from app.service import chat
from app.service.rules import pick_past
from app.service.safety import detect_crisis, unmask

STEPS = {"safety": "말을 살펴보는 중", "past": "지난 기록을 찾는 중", "reply": "별지기가 답을 고르는 중",
         "summary": "지금까지 정리하는 중"}


class TalkState(TypedDict, total=False):
    text: str            # 이번 사용자 말
    turns: list          # 지금까지 턴(원래 이름) [{"role", "text", ...}]
    summary: str
    people: list         # 가명 표(사람 목록 + 이 대화의 새 이름 후보)
    tone: str
    gentle: bool
    comfort_only: bool
    first: bool          # 끝난 기록이 없음(첫 대화)
    lead: list           # 이어 하는 기록의 생각(앞에 둠)
    sources: list        # 별지기가 인용해도 되는 지난 글(첫 말 근거)
    crisis: bool
    crisis_unsure: bool
    past: list
    reply: dict
    new_summary: str


@dataclass
class TalkCtx:
    repo: Any
    uid: str
    cid: str
    emit: Callable = lambda *_: None
    calls: int = 0
    usd: float = 0.0
    checks: list = field(default_factory=list)


def node(name):
    def deco(fn):
        def run(state, config):
            ctx = config["configurable"]["ctx"]
            ctx.emit({"conversation_id": ctx.cid, "step": name, "label": STEPS[name]})
            with llm.guard(state["people"]) as m:
                try:
                    out = fn(state, ctx) or {}
                finally:
                    ctx.calls, ctx.usd = ctx.calls + m.calls, ctx.usd + m.usd
            return out
        run.__name__ = name
        return run
    return deco


@node("safety")
def safety(state, ctx):
    # 머리말: 물음 꼴의 말("예전에 뭐라고 했지?")에 판정기가 판정 대신 대답해 형식 오류(안부 한 줄)가 나던 것(2026-10-14 --live)
    found = detect_crisis(f"(일기장 대화에서 사용자가 한 말)\n{state['text']}", people=state["people"], llm=True)
    return {"crisis": found["crisis"], "crisis_unsure": any(x["type"] == "llm_error" for x in found["signals"])}


def find_past(repo, uid, text, people, recall=False):
    """사용자 말 → 고른 지난 생각(관련 높은 순) [{"id", "day", "thought", "quote", "entry_id"}]. 끝난 기록이 없으면 부르지 않는다.
    지난 기록 물음(recall)이면 기록 본문에서 물음 낱말이 든 문장을 먼저 더한다(생각으로 안 나뉜 일 · 사건도 원문으로 찾게)."""
    vecs = repo.vectors.get(uid)
    with repo.session(uid) as s:
        done = {e["id"]: e for e in diary.entries(s, status="done")}
        ts = [t for t in diary.thoughts(s, entry_id=list(done)) if t["id"] in vecs] if done and vecs else []
    hits = chat.sentence_hits(text, [(e["id"], diary.local_day(e["written_at"]), e["data"].get("text", "")) for e in done.values()]) \
        if recall else []
    if not ts:
        return hits
    masked, _ = tools.mask_obj([text], people)
    q = llm.embed(masked, query=True)[0]
    for t in ts:
        t.update(record_id=t["entry_id"], day=diary.local_day(done[t["entry_id"]]["written_at"]), emb=vecs[t["id"]])
    center = [sum(c) / len(vecs) for c in zip(*vecs.values())] if len(vecs) >= 2 else None
    picked = pick_past([{"id": "turn", "record_id": "talk", "topic": None, "emb": q}], ts, center=center,
                       limit=chat.PAST_IN_PROMPT)
    return hits + [{"id": p["id"], "entry_id": p["entry_id"], "day": p["day"], "thought": p.get("text", ""),
                    "quote": p.get("quote", "")} for p in picked]


@node("past")
def past(state, ctx):
    lead = state.get("lead") or []
    found = find_past(ctx.repo, ctx.uid, state["text"], state["people"], chat.is_recall(state["text"]))
    ids = {p["id"] for p in lead}
    out = lead + [p for p in found if p["id"] not in ids]
    # 지난 기록 문장에만 나온 이름 후보(사람 목록에 없는 '이름인지 낱말인지' 이름)도 보내기 직전 실명 검사 표에 넣는다
    return {"past": out, "people": chat.mask_people(state["people"], [f"{p['thought']} {p['quote']}" for p in out])}


def _who(t):
    return "사용자" if t["role"] == "user" else "너"   # 이름 같은 낱말(별지기의 별)이 가명 처리에 걸리지 않게


@node("reply")
def reply(state, ctx):
    turns = state["turns"]
    user_turns = sum(t["role"] == "user" for t in turns) + 1
    recall = chat.is_recall(state["text"]) and not state.get("crisis")
    wrap = chat.should_wrap(state["text"], user_turns, state.get("crisis"))
    keeper = [t for t in turns if t["role"] == "keeper"]
    pick = lambda ps: [{k: p.get(k) or "" for k in ("day", "thought", "quote")} for p in ps]   # noqa: E731
    m, table = tools.mask_obj({"text": state["text"], "summary": state.get("summary") or "",
                               "turns": [{"who": _who(t), "text": t["text"]} for t in turns][-chat.TURNS_IN_PROMPT:],
                               "past": pick(state.get("past") or []), "sources": list(state.get("sources") or []),
                               "users": [t["text"] for t in turns if t["role"] == "user"],
                               "keeper": [t["text"] for t in keeper]}, state["people"])
    sources = m["users"] + [m["text"]] + m["sources"] + [f"{p['thought']} {p['quote']}" for p in m["past"]]
    out = chat.respond({**{k: m[k] for k in ("text", "summary", "turns", "past")}, "tone": state["tone"],
                        "gentle": state.get("gentle"), "comfort_only": state.get("comfort_only"), "first": state.get("first"),
                        "crisis": state.get("crisis"), "crisis_unsure": state.get("crisis_unsure"), "recall": recall,
                        "wrap": wrap, "hour": datetime.now(diary.TZ).hour, "sources": sources, "past_replies": m["keeper"],
                        "past_check_ins": [t["check_in"] for t in keeper if t.get("check_in")]})
    ctx.checks = out.pop("checks")
    out["text"] = unmask(out["text"], table)
    return {"reply": out}


@node("summary")
def summary(state, ctx):
    users = [t["text"] for t in state["turns"] if t["role"] == "user"] + [state["text"]]
    if not chat.due_summary(len(users), state["text"]):
        return {}
    m, table = tools.mask_obj({"summary": state.get("summary") or "", "users": users}, state["people"])
    new = chat.summarize(m["summary"], m["users"])
    return {"new_summary": unmask(new, table)} if new else {}


def build():
    g = StateGraph(TalkState)
    prev = START
    for n in (safety, past, reply, summary):
        g.add_node(n.__name__, n)
        g.add_edge(prev, n.__name__)
        prev = n.__name__
    g.add_edge(prev, END)
    return g.compile()


talk_graph = build()


##################################################
# 대화 열기 · 턴 · 초안
##################################################

def _people(s, texts):
    return chat.mask_people([{k: p[k] for k in ("id", "name", "nicknames", "relation")} for p in diary.people(s)], texts)


def _lead(s, eid):
    """이어 하는 기록: {"day", "title", "summary", "quotes"} 와 그 기록의 생각(past 모양). 끝난 기록이 아니면 (None, [])."""
    e = next(iter(diary.entries(s, status="done", id=eid)), None) if eid else None
    if not e:
        return None, []
    day = diary.local_day(e["written_at"])
    ts = [{"id": t["id"], "entry_id": eid, "day": day, "thought": t.get("text", ""), "quote": t.get("quote", "")}
          for t in diary.thoughts(s, entry_id=eid)]
    return {"day": day, "title": e["data"].get("title", ""), "summary": e["data"].get("summary", ""),
            "quotes": [t["quote"] for t in ts if t["quote"]]}, ts


def view(c):
    """대화 → API 모양. 초안 기록 id 는 확인 전일 때만(없어졌으면 null)."""
    return {"id": c["id"], "created_at": diary.iso(c["created_at"]), "updated_at": diary.iso(c["updated_at"]),
            "turns": c.get("turns", []), "summary": c.get("summary", ""), "from_entry": c.get("from_entry"),
            "entry_id": c.get("entry_id"), "turn_count": c["turn_count"],
            "wrap": bool(c.get("turns") and c["turns"][-1].get("kind") == "wrap")}


def start(s, p, from_entry=None, invite=False):
    """새 대화: 서비스가 먼저 묻는 첫 말(LLM 없음)."""
    lead, _ = _lead(s, from_entry)
    o = chat.opening(p, lead, invite)
    return conversations.create(s, {"turns": [{"role": "keeper", "kind": o["kind"], "text": o["text"], "at": diary.iso(diary.now())}],
                                    "summary": "", "from_entry": from_entry if lead else None, "sources": o["sources"]})


def error_code(e):
    return graph.error_code(e)


def turn(repo, uid, cid, text, emit=lambda *_: None, via="text"):
    """사용자 말 한 턴 → 고친 대화(view). 글로 쓴 말이든 받아쓴 말이든 같은 길(via: text | voice, WS21).
    없는 대화면 None. 실패하면 사용자 말도 저장하지 않고 예외(화면은 글을 그대로 두고 다시 보냄)."""
    t0 = time.time()
    with repo.session(uid) as s:
        c = conversations.get(s, cid)
        if not c:
            return None
        settings, _ = diary.profile(s)
        users = [t["text"] for t in c["turns"] if t["role"] == "user"] + [text]
        people = _people(s, users)
        _, lead = _lead(s, c.get("from_entry"))
        first = not s.rows("entries", status="done", limit=1)
    day = diary.today()
    state = {"text": text, "turns": c["turns"], "summary": c.get("summary", ""), "people": people,
             "tone": settings["tone"], "gentle": settings.get("gentle_today") == day,
             "comfort_only": settings.get("comfort_only_today") == day, "first": first, "lead": lead,
             "sources": c.get("sources", [])}
    ctx = TalkCtx(repo, str(uid), cid, emit)
    n = len(users)
    try:
        out = talk_graph.invoke(state, {"configurable": {"ctx": ctx}})
    except Exception as e:
        code = error_code(e)
        logger.log("error", step="talk_turn", conversation=cid, turn=n, code=code, calls=ctx.calls, what=type(e).__name__)
        with repo.session(uid) as s:
            diary.add_run(s, None, "talk_turn", (time.time() - t0) * 1000, ctx.calls, ctx.usd, code, {"conversation": cid, "turn": n})
        raise
    now = diary.iso(diary.now())
    r = out["reply"]
    c["turns"] = c["turns"] + [{"role": "user", "text": text, "at": now, "via": via},
                               {"role": "keeper", "kind": r["kind"], "text": r["text"], "mode": r["mode"], "tone": r["tone"],
                                "check_in": r["check_in"] or None, "at": now}]
    if out.get("new_summary"):
        c["summary"], c["summary_at"] = out["new_summary"], n
    c["crisis"] = bool(c.get("crisis") or out.get("crisis"))   # 위기 표시는 enc 안에만(대화 · 초안 검사에 씀)
    ms = (time.time() - t0) * 1000
    meta = {"conversation": cid, "turn": n, "kind": r["kind"], "checks": ctx.checks, "past": len(out.get("past") or [])}
    with repo.session(uid) as s:
        if not conversations.get(s, cid):   # 답을 만드는 사이 지워진 대화
            return None
        conversations.save(s, c)
        diary.add_run(s, None, "talk_turn", ms, ctx.calls, ctx.usd, None, meta)
        c = conversations.get(s, cid)
    logger.log("step", step="talk_turn", conversation=cid, turn=n, ms=int(ms), calls=ctx.calls, est_usd=round(ctx.usd, 4),
               checks=ctx.checks)
    return view(c)


def make_draft(repo, uid, cid):
    """대화 → 일기 초안 {"title", "text", "fallback"}(사용자 말만 근거, 원래 이름). 사용자 말이 없으면 None."""
    t0 = time.time()
    with repo.session(uid) as s:
        c = conversations.get(s, cid)
        users = [t["text"] for t in c["turns"] if t["role"] == "user"] if c else []
        people = _people(s, users) if users else []
    if not users:
        return None
    with llm.guard(people) as m:
        mk, table = tools.mask_obj(users, people)
        d = chat.draft(mk, crisis=bool(c.get("crisis")), limit=config.MAX_TEXT_CHARS)
    out = {"title": unmask(d["title"], table), "text": unmask(d["text"], table), "fallback": d["fallback"]}
    with repo.session(uid) as s:
        diary.add_run(s, None, "talk_draft", (time.time() - t0) * 1000, m.calls, m.usd, None,
                      {"conversation": cid, "turns": len(users), "fallback": d["fallback"]})
    logger.log("step", step="talk_draft", conversation=cid, calls=m.calls, est_usd=round(m.usd, 4), fallback=d["fallback"])
    return out
