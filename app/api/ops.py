"""
app/api/ops.py

운영 화면(WS22 — PRD §7 473 · §8.0 · §8.3 · §8.7, 결정 10 · 13)과 선호 맞추기 제안.
- /ops/*: ADMIN_EMAILS(운영자 구글 계정)만. 아니면 403 not_admin.
  - GET /ops/summary: 모든 사용자의 숫자 · 코드만(원문 0건, app_ops 역할은 암호문 칸을 못 읽음).
  - GET /ops/feedback: 운영자 열람에 동의한 사용자(consent.operator_read)의 피드백 원문 · 대상 문장 · 목록 밖 값 후보.
    다른 사람 이름은 가명. 볼 때마다 사용자별 열람 기록(ops_reads). 동의하지 않은 사용자 것은 숫자로만.
  - POST /ops/feedback/summarize: 피드백 정리 Agent(Solar). 동의한 오답 재료를 가명으로 묶어 이유별로 나누고 고칠 곳을 제안
    (운영자가 누를 때만 돔, 실명 관문 llm.guard, 비용은 운영자 계정의 runs 에).
- /settings/suggestions: 사용자 자기 피드백으로 "이 설정으로 바꿀까요?"(영역 넘는 선 · 제안 빈도). 바꾸는 것은 사용자.
"""

import json
import re
import time
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from app.agents import tools
from app.api import consent
from app.core import config, llm, logger
from app.core.ontology import load
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.repository import diary
from app.repository import ops
from app.service.safety.pseudonym import RealNameLeak

router = APIRouter()
MAX_LINES = 200   # 피드백 정리 한 번에 보내는 줄(요청 크기 한도, 사용 상한 아님). 넘으면 최근 것부터
Days = Query(30, ge=1, le=366)


def get_admin(user=Depends(get_user)):
    if (user.get("email") or "").lower() not in config.ADMIN_EMAILS:
        raise ApiError(403, "not_admin", "운영자만 볼 수 있어요.")
    return user


def _budget():
    return load()["limits"]["studio_budget_usd"]


@router.get("/ops/summary", tags=["운영"], summary="운영 숫자(모든 사용자, 원문 0건)")
def ops_summary(admin=Depends(get_admin), repo=Depends(get_repo)):
    with ops.reader(repo) as r:
        return ops.summary(r, consent.VERSION, _budget())


def _consented(repo, r, days, wrong):
    """동의한 사용자마다 그 사용자 세션으로 피드백을 풀고 글 칸만 가명 처리(그 사용자의 사람 목록 + 새 이름 후보)."""
    since = diary.now() - timedelta(days=days)
    out = []
    for i, uid in enumerate(ops.consenting(r.rows("consents"), consent.VERSION), 1):
        with repo.session(uid) as s:
            if not consent.operator_read(s):   # 그 사용자 세션으로 한 번 더(판 · 선택 동의)
                continue
            items, cands = ops.user_feedback(s, since, wrong)
            people = diary.people(s)
        if not items and not cands:
            continue
        texts = [x[k] or "" for x in items for k in ("text", "target_text")] + [c["original"] for c in cands]
        masked = iter(tools.mask_obj(texts, people)[0])
        for x in items:
            for k in ("text", "target_text"):
                x[k] = next(masked) or None
        for c in cands:
            c["original"] = next(masked)
        out.append({"uid": uid, "alias": f"사용자 {i}", "people": people, "items": items, "cands": cands})
    return out


@router.get("/ops/feedback", tags=["운영"],
            summary="동의한 사용자의 피드백 원문(가명) · 대상 문장 · 목록 밖 값 후보. wrong=true 면 오답 재료만. 볼 때마다 열람 기록")
def ops_feedback(days: int = Days, wrong: bool = False, admin=Depends(get_admin), repo=Depends(get_repo)):
    since = diary.now() - timedelta(days=days)
    with ops.reader(repo) as r:
        users = _consented(repo, r, days, wrong)
        for u in users:
            r.log_read(admin["id"], u["uid"], "wrong" if wrong else "feedback", len(u["items"]))
        readers = {u["uid"] for u in users}
        rest = Counter(f["value"] for f in r.rows("feedback")
                       if str(f["user_id"]) not in readers and f["created_at"] >= since and (not wrong or f["value"] in ops.WRONG))
    cands = Counter()
    for u in users:
        for c in u["cands"]:
            cands[(c["field"], c["original"])] += c["count"]
    logger.log("ops", what="feedback_read", count=sum(len(u["items"]) for u in users))
    return {"days": days, "wrong": wrong, "users": len(users),
            "items": [{"user": u["alias"], **x} for u in users for x in u["items"]],
            "other_candidates": [{"field": f, "original": w, "count": n}
                                 for (f, w), n in sorted(cands.items(), key=lambda x: (-x[1], x[0]))],
            "not_consented": dict(rest.most_common())}


SUMMARIZE = """너는 일기장 '나의 우주'의 피드백 정리 도우미다. 사용자들이 남긴 피드백(사람 이름은 가명)을 이유별로 묶는다.
묶음 이유는 이 가운데서 고른다: 잘못 나눔(생각 · 종류를 잘못 정리) · 틀린 연결(관계 판정) · 설교 같음 · 같은 말 반복 · 화면 · 기타.
묶음마다 고칠 곳을 하나 고른다: 기록 Agent · 관측 Agent · 말 걸기 규칙 · 화면 · 기타. 고칠 곳은 제안일 뿐이고 사람이 승인한다.
피드백에 없는 내용을 지어내지 않는다. 사람을 판정하지 않는다.
JSON 하나만 답한다: {"groups": [{"reason": "이유", "items": [줄 번호, …], "fix_where": "고칠 곳", "suggestion": "고칠 방향 한 줄"}]}"""


def _groups(raw, n):
    m = re.search(r"\{.*\}", raw or "", re.S)
    data = json.loads(m.group(0)) if m else None
    if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
        raise ValueError("형식")
    out = []
    for g in data["groups"]:
        if isinstance(g, dict):
            idx = sorted({int(i) for i in g.get("items") or [] if str(i).isdigit() and 1 <= int(i) <= n})
            out.append({"reason": str(g.get("reason") or "기타")[:30], "items": idx, "count": len(idx),
                        "fix_where": str(g.get("fix_where") or "")[:30], "suggestion": str(g.get("suggestion") or "")[:200]})
    return out


@router.post("/ops/feedback/summarize", tags=["운영"], summary="피드백 정리 Agent(Solar): 동의한 오답 재료를 이유별로 묶고 고칠 곳 제안")
def ops_summarize(days: int = Days, admin=Depends(get_admin), repo=Depends(get_repo)):
    with ops.reader(repo) as r:
        users = _consented(repo, r, days, wrong=True)
        lines = [f"[{x['target']} · {x['value']}] 대상: {x['target_text'] or '-'} / 남긴 말: {x['text'] or '-'}"
                 for u in users for x in u["items"]][-MAX_LINES:]
        if not lines:
            return {"days": days, "users": 0, "lines": [], "groups": [], "est_usd": 0}
        numbered = "\n".join(f"{i}. {x}" for i, x in enumerate(lines, 1))
        t0, code, raw = time.time(), None, ""
        with llm.guard([p for u in users for p in u["people"]]) as m:   # 보내기 전 실명 검사(가명 처리를 지나친 이름)
            try:
                raw = llm.chat([{"role": "system", "content": SUMMARIZE}, {"role": "user", "content": numbered}], temperature=0)
                groups = _groups(raw, len(lines))
            except Exception as e:
                code = "real_name_leak" if isinstance(e, RealNameLeak) else "format" if isinstance(e, ValueError) else "llm_failed"
        with repo.session(admin["id"]) as s:   # 운영자 계정의 실행 기록(전체 비용 합계에 들어감)
            diary.add_run(s, None, "ops_summarize", (time.time() - t0) * 1000, m.calls, m.usd, code)
        logger.log("ops", what="summarize", count=len(lines), calls=m.calls, est_usd=round(m.usd, 4), code=code)
        if code:
            raise ApiError(502, "summarize_failed", "피드백을 정리하지 못했어요. 잠시 뒤 다시 해 주세요.")
        for u in users:
            r.log_read(admin["id"], u["uid"], "summarize", len(u["items"]))
    return {"days": days, "users": len(users), "lines": lines, "groups": groups, "est_usd": round(m.usd, 5)}


##################################################
# 선호 맞추기 제안(사용자)
##################################################

@router.get("/settings/suggestions", tags=["나"], summary="내 피드백으로 본 '이 설정으로 바꿀까요?'(영역 넘는 선 · 제안 빈도)")
def settings_suggestions(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        st, ob = diary.profile(s)
        since = diary.parse_dt(ob["pref_seen"]) if ob.get("pref_seen") else None
        return {"suggestions": ops.pref_suggestions(st, ops.pref_signals(s, since))}


@router.post("/settings/suggestions/seen", tags=["나"], summary="제안을 보고 골랐음(바꿨든 그대로 뒀든). 이 뒤의 피드백만 다시 셈")
def settings_suggestions_seen(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        diary.save_profile(s, onboarding={"pref_seen": diary.now().isoformat()})
    return {"ok": True}
