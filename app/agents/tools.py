"""
app/agents/tools.py

그래프 노드가 쓰는 도구: 기록 Agent 실행 · 관측 Agent 실행 · 지난 생각 검색 · 한마디 생성 (+ 생각 벡터 만들기).
외부로 나가는 글은 호출마다 한 번에 가명 처리(mask_obj)해서, 한 요청 안에서는 같은 사람이 같은 가명이 되고
받은 답은 그 요청의 표로 되돌린다(unmask_obj). 실명 검사는 llm.guard 가 보내기 직전에 한다.
"""

import json
import re
from functools import lru_cache

from app.agents import studio
from app.core import config, llm, logger
from app.core.ontology import load
from app.repository import diary
from app.service import studio_format as sf
from app.service import voice
from app.service.rules import pick_past
from app.service.safety import mask, unmask

SEP = "\n␞\n"   # 조각 사이 구분 줄(사람 이름 규칙에 걸리지 않는 글자)


def _strings(x, out):
    if isinstance(x, str):
        out.append(x)
    elif isinstance(x, dict):
        for v in x.values():
            _strings(v, out)
    elif isinstance(x, list):
        for v in x:
            _strings(v, out)
    return out


def _put(x, it):
    if isinstance(x, str):
        return next(it)
    if isinstance(x, dict):
        return {k: _put(v, it) for k, v in x.items()}
    if isinstance(x, list):
        return [_put(v, it) for v in x]
    return x


def mask_obj(obj, people):
    """dict · list 속 글자를 한 번에 가명 처리 → (같은 모양, 가명 표). 한 요청 안에서는 같은 사람 = 같은 가명."""
    parts = [s.replace("␞", "") for s in _strings(obj, [])]
    masked, table = mask(SEP.join(parts), people)
    out = masked.split(SEP)
    if len(out) != len(parts):
        raise ValueError("가명 처리 조각 수가 맞지 않음")
    return _put(obj, iter(out)), table


def unmask_obj(obj, table):
    return _put(obj, iter([unmask(s, table) for s in _strings(obj, [])]))


##################################################
# 기록 · 관측 Agent (Studio)
##################################################

def run_record_agent(title, text, topics, people):
    """제목 · 본문 · 기존 작은 별 이름 → 기록 Agent 추출 JSON(원래 이름으로 되돌린 것)."""
    m, table = mask_obj({"title": title, "text": text, "topics": list(topics)}, people)
    data = studio.run("record", sf.record_html(m["title"] or "제목 없음", m["text"], m["topics"]))
    return unmask_obj(data, table)


OBS_KEYS = ("id", "topic", "domain", "kind", "certainty", "quote", "self_change", "day")


def run_observe_agent(day, today, past, aspiration, people):
    """오늘 생각 · 고른 지난 생각 · 되고 싶은 모습 → parse_observe 결과(원래 이름으로 되돌린 것)."""
    pick = lambda ts: [{k: t.get(k) or "" for k in OBS_KEYS} for t in ts]   # noqa: E731
    m, table = mask_obj({"today": pick(today), "past": pick(past), "asp": aspiration or {}}, people)
    html, ids = sf.observe_html(day, m["today"], m["past"], m["asp"] or None)
    return unmask_obj(sf.parse_observe(studio.run("observe", html), ids), table)


##################################################
# 생각 벡터 · 지난 생각 검색
##################################################

def embed(texts, people):
    """가명 처리한 글로 만든 벡터(원문은 벡터 저장소에 넣지 않는다)."""
    if not texts:
        return []
    masked, _ = mask_obj(list(texts), people)
    return llm.embed(masked)


@lru_cache(maxsize=1)
def sun_vectors():
    """기준 축 9개의 대표 낱말 벡터와 중심(이미 만들어 둔 파일, 지금 임베딩 모델 것만)."""
    ops = config.BASE_DIR / "data" / "ops"
    model = config.EMBED_PASSAGE_MODEL
    try:
        alias = json.loads((ops / f"domain_aliases_{model}.json").read_text(encoding="utf-8"))
        center = json.loads((ops / f"topic_center_{model}.json").read_text(encoding="utf-8"))
    except FileNotFoundError:   # 해를 못 정한 주제가 모두 '삶의 성취'로 간다 → 시작할 때 경고(main.py)
        logger.log("error", what="sun_vectors", code="sun_vectors_missing")
        return {}, None
    vecs = {d["name"]: [alias[w] for w in [d["name"], *d["keywords"]] if w in alias] for d in load()["domains"]}
    return {k: v for k, v in vecs.items() if v}, center


def search_past(repo, uid, entry_id, today):
    """오늘 생각(id · topic) → 고른 지난 생각(관련 높은 순, 벡터 없이). rules.pick_past 를 그대로 쓴다."""
    vecs = repo.vectors.get(uid)
    with repo.session(uid) as s:
        done = {e["id"]: e for e in diary.entries(s, status="done") if e["id"] != entry_id}
        past = [t for t in diary.thoughts(s, entry_id=list(done)) if t["id"] in vecs] if done else []
        sun_name = {x["id"]: x["name"] for x in diary.suns(s)}
    for t in past:
        e = done[t["entry_id"]]
        t.update(record_id=t["entry_id"], day=diary.local_day(e["written_at"]), written_at=diary.iso(e["written_at"]),
                 domain=sun_name.get(t["sun_id"]), thought=t.get("text", ""), emb=vecs[t["id"]])
    today_v = [{"id": t["id"], "record_id": entry_id, "topic": t["topic"], "emb": vecs.get(t["id"])} for t in today]
    center = [sum(c) / len(vecs) for c in zip(*vecs.values())] if len(vecs) >= 2 else None   # 이 사용자 생각 벡터의 평균
    picked = pick_past(today_v, past, center=center)
    return [{k: v for k, v in p.items() if k != "emb"} for p in picked]


##################################################
# 한마디
##################################################

VOICE_TEXT = ("text", "summary", "thoughts", "reached", "aspiration", "commitments", "kept", "open_questions",
              "person_history", "past_messages", "past_thoughts", "changes", "widen")


def speak(ctx, people):
    """voice.generate 를 가명 글로 부르고 한마디 · 다음 질문을 원래 이름으로 되돌린다(안부 한 줄은 고정 문장이라 그대로)."""
    m, table = mask_obj({k: ctx[k] for k in VOICE_TEXT if ctx.get(k)}, people)
    out = voice.generate({**ctx, **m})
    return {**out, "message": unmask(out["message"], table), "next_question": unmask(out["next_question"], table)}


def norm(s):
    return re.sub(r"\s+", "", s or "")
