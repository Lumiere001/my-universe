"""
app/api/routes.py

우주 · 온톨로지 · 피드백 · 사람 · 되고 싶은 모습 · 나 · 설정 · 계정 지우기 · 운영(/health · /stats).
"""

import time
import unicodedata
from typing import Annotated, Literal

from datetime import datetime

from fastapi import APIRouter, Depends, Header, Path, Response

from app.agents import graph, tools
from app.api import consent
from app.core import auth, config, llm, logger
from app.core.ontology import load
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.models import AnswerIn, AskIn, PushIn, AspirationIn, DeclineIn, FeedbackIn, PersonIn, PersonPatch, SettingsPatch, WhyIn
from app.repository import diary, ops, views
from app.service import brief, chat, push, voice
from app.service.rules.topics import cos
from app.service.safety import detect_crisis, unmask
from app.service.rules import press

router = APIRouter()
Id = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,80}$")]   # id 모양만(제어 문자 · 다른 글자는 422)
_DEEP = {"at": 0.0, "out": None}   # deep 점검 결과를 10초 둔다(로그인 없이 부를 수 있어 DB · Chroma 연결을 아끼려고)


@router.get("/health", tags=["운영"])
def health(response: Response, deep: bool = False):
    """deep=1 이면 DB(select 1) · ChromaDB(컬렉션 열기)까지 닿는지 본다(업스테이지 가이드 ④ Step 5 · ⑥ Step 3).
    하나라도 안 되면 503 · degraded. 오류는 종류 이름만(주소 · 메시지는 내보내지 않음)."""
    out = {"status": "ok", "version": config.VERSION}
    if not deep:
        return out
    if _DEEP["out"] and time.time() - _DEEP["at"] < 10:
        response.status_code = 200 if _DEEP["out"]["status"] == "ok" else 503
        return _DEEP["out"]
    checks = {}
    try:
        import psycopg
        if not config.DATABASE_URL:
            raise LookupError("unconfigured")
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as c:
            c.execute("select 1")
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = str(e) if isinstance(e, LookupError) else type(e).__name__
    try:
        from app.repository.vectors import ChromaVectors
        ChromaVectors()
        checks["vectors"] = "ok"
    except Exception as e:
        checks["vectors"] = type(e).__name__
    if any(v != "ok" for v in checks.values()):
        response.status_code, out["status"] = 503, "degraded"
    _DEEP.update(at=time.time(), out={**out, "checks": checks})
    return _DEEP["out"]


@router.get("/ontology", tags=["운영"], summary="app/core/ontology/v8.json 그대로")
def ontology():
    return load()


@router.get("/stats", tags=["운영"], summary="원문 없는 운영 숫자(본인 것만)")
def stats(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.stats(s)


@router.get("/universe", tags=["우주"])
def universe(user=Depends(get_user), repo=Depends(get_repo)):
    graph.ensure_groups(repo, user["id"])   # 모드를 바꾼 뒤 처음 열 때 한 번 작은 별 묶기(rules.groups)
    with repo.session(user["id"]) as s:
        return views.universe(s)


Period = Literal["week", "month", "all"]
PERIOD_LABEL = {"week": "이번 주", "month": "이번 달", "all": "처음부터"}


@router.get("/insight", tags=["우주"], summary="나에 대해 알게 된 것: 해 → 작은 별 → 이어 온 · 바뀐 · 맞서는 · 정리된 생각(원문 인용)")
def insight(period: Period = "all", user=Depends(get_user), repo=Depends(get_repo)):
    graph.ensure_groups(repo, user["id"])   # 모드를 바꾼 뒤 처음 열 때 한 번 작은 별 묶기(rules.groups)
    with repo.session(user["id"]) as s:
        return views.insight(s, period)


@router.get("/insight/brief", tags=["우주"], summary="흐름 요약(PRD v9 Q10): 기간 안 원문 재료로만, 문장마다 출처 · 새 기록이 있을 때만 다시 씀")
def insight_brief(period: Period = "month", user=Depends(get_user), repo=Depends(get_repo)):
    uid = user["id"]
    graph.ensure_groups(repo, uid)
    with repo.session(uid) as s:
        ins = views.insight(s, period)
        people = diary.people(s)
        last = s.rows("entries", status="done", order="updated_at desc", limit=1)
        key = f"{period}:{(ins['period'] or {}).get('records')}:{last[0]['updated_at'] if last else ''}"
        cache = (diary.profile(s)[1].get("brief") or {}).get(period)
        start = brief.since(period, diary.today())
        reached = [{"record_id": r["entry_id"], "day": diary.local_day(r["at"]), "quote": r.get("quote", "")}
                   for a in diary.aspirations(s)[-1:] for r in a["reached"] if not start or diary.local_day(r["at"]) >= str(start)]
    if cache and cache.get("key") == key:
        return cache["out"]
    if not ins["period"] or ins["period"]["records"] < brief.MIN_RECORDS:
        return {"state": "few" if ins["period"] else "none", "sections": []}
    text, refs = brief.material(ins, reached)
    t0 = time.time()
    try:
        m, table = tools.mask_obj({"t": text, "suns": [x["name"] for x in ins["suns"]]}, people)
        secs, _ = brief.parse(llm.chat(brief.brief_messages(m["t"], PERIOD_LABEL[period], m["suns"]), temperature=0.3),
                              refs, lambda x: unmask(x, table))
    except Exception as e:   # 요약은 덤: 못 만들면 궤적 카드만(화면이 '다시 시도'를 보인다)
        logger.log("error", step="brief", code=type(e).__name__)
        secs = []
    out = {"state": "ok" if secs else "failed", "sections": secs}
    with repo.session(uid) as s:
        diary.add_run(s, None, "brief", (time.time() - t0) * 1000, 1, meta={"period": period, "sections": len(secs)})   # 운영 지표
        if secs:
            ob = diary.profile(s)[1]
            diary.save_profile(s, onboarding={"brief": {**(ob.get("brief") or {}), period: {"key": key, "out": out}}})
    return out


ASK_HITS = 8   # 묻기 칸이 Solar 에 넘기는 원문 수(낱말 찾기 + 뜻 찾기)


@router.post("/insight/ask", tags=["우주"], summary="내 일기에 묻기(PRD v9 Q11): 찾은 원문만으로 답, 일기로 남기지 않음")
def insight_ask(body: AskIn, user=Depends(get_user), repo=Depends(get_repo)):
    uid, q = user["id"], body.question.strip()
    with repo.session(uid) as s:
        consent.check(s)
        people = diary.people(s)
        entries = [e for e in diary.entries(s, status="done")]
        texts = [(e["id"], diary.local_day(e["written_at"]), e["data"].get("text", "")) for e in entries]
        day_of = {e["id"]: diary.local_day(e["written_at"]) for e in entries}
    if detect_crisis(q, people)["crisis"]:   # 위기 낱말이면 찾지 않고 대화의 위기 대응과 같은 위로 한 줄
        return {"state": "crisis", "sentences": [], "message": voice.CRISIS_SAFE["다정하게"][0]}
    hits = [{"entry_id": h["entry_id"], "day": h["day"], "quote": h["quote"]} for h in chat.sentence_hits(q, texts)]
    t0 = time.time()
    try:
        m, table = tools.mask_obj({"q": q}, people)
        qv = llm.embed([m["q"]], query=True)[0]
        vecs = repo.vectors.get(uid)
        near = sorted(vecs, key=lambda k: -cos(qv, vecs[k]))[:ASK_HITS]
        with repo.session(uid) as s:
            hits += [{"entry_id": t["entry_id"], "day": day_of.get(t["entry_id"], ""), "quote": t.get("quote") or t.get("text", "")}
                     for t in diary.thoughts(s, id=near) if t["entry_id"] in day_of]
        seen, refs = set(), {}
        for h in hits:
            if h["quote"] and h["quote"] not in seen and len(refs) < ASK_HITS:
                seen.add(h["quote"])
                refs[f"R{len(refs) + 1}"] = h
        if not refs:
            return {"state": "none", "sentences": []}
        lines = [f"[{k} {h['day']}] “{h['quote']}”" for k, h in refs.items()]
        mm, table = tools.mask_obj({"q": q, "lines": lines}, people)
        secs, found = brief.parse(llm.chat(brief.ask_messages(mm["q"], "\n".join(mm["lines"])), temperature=0.2),
                                  {k: {"entry_id": h["entry_id"], "day": h["day"]} for k, h in refs.items()}, lambda x: unmask(x, table))
    except Exception as e:
        logger.log("error", step="ask", code=type(e).__name__)
        return {"state": "failed", "sentences": []}
    with repo.session(uid) as s:
        diary.add_run(s, None, "ask", (time.time() - t0) * 1000, 2, meta={"found": bool(secs)})   # 운영 지표(물음 글은 남기지 않음)
    sents = [x for sec in secs for x in sec["sentences"]]
    return {"state": "ok" if sents and found is not False else "none", "sentences": sents}


##################################################
# 피드백 · 상태 버튼
##################################################

TODAY_FLAGS = {"오늘은 살살": "gentle_today", "오늘은 위로만": "comfort_only_today"}
BLANK = "\u115f\u1160\u3164\uffa0\u2800\ufffc"   # 한글 채움 문자 · 점자 빈칸 · 받아쓰기 자리표: 글자지만 보이지 않음


def _visible(text):
    """보이는 글자가 하나라도 있나. 띄어쓰기 · 제어 · 폭 없는 글자 · 채움 문자만이면 빈 글(화면 OneLine 과 같은 규칙)."""
    return any(not c.isspace() and unicodedata.category(c) not in ("Cc", "Cf") and c not in BLANK for c in text or "")


@router.post("/feedback", tags=["피드백"])
def feedback(body: FeedbackIn, user=Depends(get_user), repo=Depends(get_repo)):
    if body.value == "불편한 점 한 줄" and not _visible(body.text):   # 그냥 받으면 운영 화면 '남긴 말'이 빈 칸으로 남는다
        raise ApiError(422, "invalid_input", "불편한 점을 한 줄 적어 주세요.")
    changed = removed = None
    with repo.session(user["id"]) as s:
        if body.value in ("맞아요", "아니에요", "지켰어요", "그만둘래요"):
            if not body.target_id:
                raise ApiError(422, "invalid_input", "어느 항목에 대한 버튼인지 알 수 없어요. 화면을 새로 고친 뒤 다시 눌러 주세요.")
            old = diary.states(s)
            rels = diary.relations(s) if body.value in ("맞아요", "아니에요") else []
            try:
                new, new_rels = press(old, rels, body.target_id, body.value, diary.today())
            except ValueError:
                raise ApiError(409, "invalid_target", "이 항목에는 이 버튼을 쓸 수 없어요.")
            after = {r["id"]: r for r in new_rels}
            for r in rels:
                if r["id"] not in after:
                    s.delete("relations", id=r["id"])
                    removed = {k: r[k] for k in ("type", "from", "to")}   # 오답 재료(피드백 암호문에만)
                elif after[r["id"]] != r:
                    diary.save_relation(s, after[r["id"]])
            diary.save_states(s, new, old)
            changed = new.get(body.target_id)
        elif body.value in TODAY_FLAGS:
            diary.save_profile(s, settings={TODAY_FLAGS[body.value]: diary.today()})
        elif body.value == "날씨 건너뜀":
            diary.save_profile(s, settings={"weather_ask": False}, onboarding={"weather_asked": True})
        diary.add_feedback(s, body.target, body.target_id, body.value,
                           body.text if body.value == "불편한 점 한 줄" else None, relation=removed)
        tuned = ops.auto_pref(s)   # 개인 고리: 반응이 한쪽으로 쌓이면 그 사람 설정을 한 칸(알림 · 되돌리기는 /settings/suggestions)
    return {"ok": True, "state": changed and {"type": changed["kind"], "status": changed.get("state"),
                                              "mistake": "실수" in changed.get("marks", [])}, "tuned": tuned}


##################################################
# 사람
##################################################

def _nicks(s):
    return [n.strip() for n in (s or "").split(",") if n.strip()]


@router.get("/people", tags=["사람"])
def list_people(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return {"people": views.people_list(s)}


@router.post("/people", tags=["사람"])
def add_person(body: PersonIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.person_api(diary.add_person(s, body.name, _nicks(body.nickname), body.relation))


@router.patch("/people/{pid}", tags=["사람"])
def update_person(body: PersonPatch, pid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        p = diary.update_person(s, pid, body.name, None if body.nickname is None else _nicks(body.nickname), body.relation)
    if not p:
        raise ApiError(404, "not_found", "이 사람을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
    return views.person_api(p)


@router.delete("/people/{pid}", tags=["사람"], summary="지우기 = 저장된 글 속 이름을 관계 말로 바꾸고 문장은 남김")
def delete_person(pid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        n = diary.delete_person(s, pid)
    if n is None:
        raise ApiError(404, "not_found", "이 사람을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
    return {"ok": True, "replaced": n}


@router.post("/people/questions/{qid}", tags=["사람"])
def answer_question(body: AnswerIn, qid: Id, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        q = next(iter(diary.questions(s, id=qid)), None)
        if not q:
            raise ApiError(404, "not_found", "이 질문을 찾지 못했어요. 화면을 새로 고쳐 주세요.")
        people = diary.people(s)
        if body.answer in ("다른 사람", "사람 이름"):
            diary.add_person(s, q["name"])
        elif body.answer == "같은 사람" and q["reason"] == "별명":
            # 이미 있는 이름과 겹치는 사람(find_new_names 의 별명 규칙과 같음)의 별명으로 더한다
            base = q["name"][:-1] if q["name"].endswith("이") else q["name"]
            p = next((p for p in people if any(base in t or t in q["name"] for t in [p["name"], *p["nicknames"]])), None)
            if p:
                diary.update_person(s, p["id"], nicknames=[*p["nicknames"], q["name"]])
        s.update("people_questions", {"answer": body.answer}, id=qid)
    return {"ok": True}


##################################################
# 되고 싶은 모습
##################################################

@router.get("/aspiration", tags=["되고 싶은 모습"])
def get_aspiration(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return views.aspiration_state(s)


@router.post("/aspiration", tags=["되고 싶은 모습"], summary="새 판(이력 보존)")
def save_aspiration(body: AspirationIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        diary.add_aspiration(s, body.now, body.want, body.obstacle, body.if_then, body.values, body.why, body.scene)
        diary.save_profile(s, onboarding={"aspiration": "set", "aspiration_step": None, "intro": True})
        return views.aspiration_api(diary.aspirations(s)[-1])


@router.post("/aspiration/values", tags=["되고 싶은 모습"], summary="이유에서 가치 칩 제안(임베딩 비슷함, PRD v9)")
def suggest_values(body: WhyIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        consent.check(s)
        people = diary.people(s)
    try:
        return {"values": tools.suggest_values(body.why, people)}
    except Exception:   # 제안은 덤: 못 하면 칩만 보이고 사용자가 고른다
        return {"values": []}


@router.post("/aspiration/decline", tags=["되고 싶은 모습"], summary="skip = 이번엔 넘어가기, stop = 그만 묻기, later = 처음 인터뷰 나중에")
def decline_aspiration(body: DeclineIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        # later: '아직 안 함'으로 남겨 며칠 쓴 뒤 다시 권한다(PRD v9 Q3-2). 처음 인터뷰만 지난 것으로 적는다
        diary.save_profile(s, onboarding={"intro": True} if body.mode == "later"
                           else {"aspiration": body.mode, "aspiration_step": None, "intro": True})
    return {"ok": True}


##################################################
# 고른 시각 알림(PRD v9 Q8)
##################################################

@router.get("/push/key", tags=["알림"], summary="알림 공개 키(없으면 알림 기능 꺼짐)")
def push_key():
    return {"public_key": config.VAPID_PUBLIC_KEY or None}


@router.get("/push/subscribe", tags=["알림"], summary="이 사람의 알림 시각들(기기마다 하나)")
def push_list(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        return {"subs": [{"id": r["id"], "notify_at": r["notify_at"]} for r in s.rows("push_subs")]}


@router.post("/push/subscribe", tags=["알림"], summary="알림 켜기 · 시각 바꾸기(같은 기기는 하나로 바꿈)")
def push_subscribe(body: PushIn, user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        for r in s.rows("push_subs"):
            if diary.unseal(s, "push_subs", r["id"], r["enc"]).get("endpoint") == body.endpoint:
                s.delete("push_subs", id=r["id"])
        pid = diary.new_id("ps")
        s.insert("push_subs", {"id": pid, "notify_at": body.notify_at, "last_sent": None,
                               "enc": diary.seal(s, "push_subs", pid, {"endpoint": body.endpoint, "keys": body.keys})})
    return {"ok": True, "notify_at": body.notify_at}


@router.delete("/push/subscribe", tags=["알림"], status_code=204, summary="알림 끄기(이 사람의 모든 기기)")
def push_unsubscribe(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        s.delete("push_subs")
    return Response(status_code=204)


@router.post("/push/due", tags=["알림"], include_in_schema=False)
def push_due(x_cron_secret: Annotated[str | None, Header()] = None, repo=Depends(get_repo)):
    """30분마다 예약 작업(.github/workflows/push.yml)이 부른다. 이 30분 자리를 고른 사람에게 하루 한 번, 고른 별지기 말투의 한 줄.
    보낼 사람만 app_ops 로 고르고(평문 칸), 구독을 풀어 보내는 일은 그 사용자 세션에서. 만료된 구독은 지운다."""
    if not config.CRON_SECRET or x_cron_secret != config.CRON_SECRET:
        raise ApiError(403, "forbidden", "예약 작업만 부를 수 있어요.")
    if not (config.VAPID_PUBLIC_KEY and config.VAPID_PRIVATE_KEY):
        return {"off": True, "sent": 0}
    now = datetime.now(diary.TZ)
    at, today = push.slot(now), now.date()
    with ops.reader(repo) as r:
        due = [x for x in r.rows("push_subs") if x["notify_at"] == at and str(x["last_sent"] or "") != str(today)]
    sent = gone = 0
    for x in due:
        with repo.session(x["user_id"]) as s:
            row = s.rows("push_subs", id=x["id"])
            last = s.rows("entries", status="done", order="written_at desc", limit=1)
            if not row or not push.should_send(today, row[0]["last_sent"], diary.local_day(last[0]["written_at"]) if last else None):
                continue
            res = push.send(diary.unseal(s, "push_subs", x["id"], row[0]["enc"]), push.payload(diary.profile(s)[0]["tone"]),
                            config.VAPID_PRIVATE_KEY, config.VAPID_SUBJECT)
            if res == "gone":
                s.delete("push_subs", id=x["id"])
                gone += 1
            elif res == "ok":
                s.update("push_subs", {"last_sent": today}, id=x["id"])
                sent += 1
    logger.log("step", step="push_due", slot=at, due=len(due), sent=sent, gone=gone)
    return {"slot": at, "due": len(due), "sent": sent, "gone": gone}


##################################################
# 나 · 설정
##################################################

@router.get("/me", tags=["나"])
def me(user=Depends(get_user), repo=Depends(get_repo)):
    with repo.session(user["id"]) as s:
        st, ob = diary.profile(s)
        n = len(s.rows("entries", status="done"))
    return {"user": user, "settings": st,
            "onboarding": {"entries": n, "aspiration": ob["aspiration"], "weather_asked": ob["weather_asked"],
                           "intro": bool(ob.get("intro")) or n > 0},   # 이미 쓰던 사람은 처음 인터뷰로 보내지 않음
            "voice_call": config.VOICE_CALL_ON}   # 이야기 화면의 전화 단추(켜고 끄기는 백엔드 env 하나)


@router.delete("/me", tags=["나"], status_code=204, summary="계정과 모든 기록 지우기(되돌릴 수 없음)")
def delete_me(user=Depends(get_user), repo=Depends(get_repo)):
    """순서: 벡터(Chroma) → DB 의 모든 행 → auth 계정(관리 API, 남은 행은 FK cascade). 벡터를 못 지우면 아무것도 안 지우고 오류."""
    uid = user["id"]
    if not (config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY):
        raise ApiError(503, "account_delete_unconfigured", "지금은 계정을 지울 수 없어요. 운영자에게 알려 주세요.")
    with repo.session(uid) as s:
        if any(diary.is_locked(e) for e in s.rows("entries")):
            raise ApiError(409, "already_running", "정리 중인 기록이 끝난 뒤에 지울 수 있어요.")
    try:
        repo.vectors.delete(uid)
    except Exception as e:
        logger.log("error", what="delete_me", code="vector_delete_failed", user_id=uid, status=type(e).__name__)
        raise ApiError(503, "vector_delete_failed", "기록을 지우지 못했어요. 계정은 그대로예요. 잠시 뒤 다시 해 주세요.")
    with repo.session(uid) as s:
        diary.wipe(s)
    auth.delete_account(uid)
    logger.log("step", what="delete_me", user_id=uid, ok=True)
    return Response(status_code=204)


@router.patch("/settings", tags=["나"])
def patch_settings(body: SettingsPatch, user=Depends(get_user), repo=Depends(get_repo)):
    patch = body.model_dump(exclude_unset=True)
    with repo.session(user["id"]) as s:
        cur, _ = diary.profile(s)
        if patch.get("tone") == "팩폭" and not patch.get("fact_bomb_ack", cur["fact_bomb_ack"]):
            raise ApiError(409, "fact_bomb_ack_required", "팩폭은 경고를 확인한 뒤에 고를 수 있어요.")
        if patch.get("fact_bomb_ack") is False and cur["tone"] == "팩폭" and "tone" not in patch:
            patch["tone"] = "다정하게"   # 경고 확인을 거두면 팩폭도 거둔다
        new = {**cur, **patch}
        if new["tone"] == voice.CUSTOM and not new.get("tone_note"):
            raise ApiError(422, "tone_note_required", "원하는 말투를 한 줄 적어 주세요.")
        st, _ = diary.save_profile(s, settings=patch)
    return st
