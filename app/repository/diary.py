"""
app/repository/diary.py

나의 우주 데이터 읽기 · 쓰기. 원문은 여기서만 암호화 · 복호화한다(security.seal / unseal, aad = '표:행 id').
세션 s 는 repo.session(user_id) 가 준 것(모든 쿼리에 그 사용자 id 가 붙고 RLS 가 걸림).
"""

import secrets
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core import config, security
from app.service.rules.dates import read_day
from app.service.safety import forget

TZ = ZoneInfo(config.TIMEZONE)
SETTINGS = {"tone": "다정하게", "fact_bomb_ack": False, "gentle_today": None, "comfort_only_today": None,
            "suggestions": "보통", "cross_links": "눌렀을 때", "weather_ask": True, "keeper_name": "별지기"}
ONBOARDING = {"aspiration": "none", "aspiration_step": None, "weather_asked": False}
ENC_TABLES = ("entries", "thoughts", "relations", "messages", "stars", "aspirations", "aspiration_reached", "people_questions",
              "feedback")
MOOD_FEEDBACK = ("오늘은 위로만", "오늘은 살살")   # 마음 상태 버튼: 값은 enc 에만, 평문 칸에는 MOOD_LABEL
MOOD_LABEL = "상태 버튼"


def new_id(prefix):
    return f"{prefix}_{secrets.token_hex(6)}"


def thought_id(entry_id, position):
    """생각 id = 기록 id + 순서. 같은 기록을 다시 돌려도 같은 id, id 순서 = 글 속 순서(rules 가 id 로 정렬함)."""
    return f"{entry_id}-t{position:02d}"


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(TZ).isoformat(timespec="seconds") if dt else None


def local_day(dt):
    return dt.astimezone(TZ).date().isoformat()


def parse_dt(s):
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=TZ)


def today():
    return datetime.now(TZ).date().isoformat()


def seal(s, table, rid, data):
    return security.seal(s.uid, f"{table}:{rid}", data)


def unseal(s, table, rid, blob):
    return security.unseal(s.uid, f"{table}:{rid}", blob)


def studio_config():
    """지금 쓰는 Studio 설정 번호 '기록 판/관측 판'(예: 2/2). runs · feedback · 같은 글 HMAC 에 붙인다."""
    return f"{config.V8_RECORD_CONFIG_ID}/{config.V8_OBSERVE_CONFIG_ID}"


def content_hash(s, title, text, written_at):
    """같은 날(쓴 날, 현지 날짜) 쓴 같은 글 · 같은 설정이면 같은 값(띄어쓰기 · 줄바꿈 · 유니코드 조합 차이는 무시).
    다른 날 쓴 같은 짧은 글('오늘도 별일 없었다.')은 새 기록이다. 사용자별 HMAC 이라 글을 되살릴 수 없다."""
    norm = unicodedata.normalize("NFC", " ".join(f"{title or ''}\n{text}".split()))
    return security.digest(s.uid, f"content\n{studio_config()}\n{local_day(written_at)}\n{norm}")


def ref_hash(s, source, ref):
    """가져온 원본 표시(게시물 시각 · 파일 이름 …)는 평문으로 두지 않는다."""
    return security.digest(s.uid, f"ref\n{source}\n{ref}") if ref else None


def _rid(table, row):
    return row["key"] if table == "states" else row["id"]


def _map_strings(x, fn):
    if isinstance(x, str):
        return fn(x)
    if isinstance(x, list):
        return [_map_strings(v, fn) for v in x]
    if isinstance(x, dict):
        return {k: _map_strings(v, fn) for k, v in x.items()}
    return x


##################################################
# 나 · 설정
##################################################

def profile(s):
    """설정 · 첫 만남 상태. enc 에 둔다('오늘은 위로만' 날짜 같은 마음 상태가 들어 있음). 평문 칸은 예전 행 읽기용."""
    r = s.rows("profiles")
    if not r:
        s.insert("profiles", {"settings": {}, "onboarding": {}})
        r = [{"settings": {}, "onboarding": {}}]
    d = unseal(s, "profiles", s.uid, r[0].get("enc"))
    return ({**SETTINGS, **(r[0]["settings"] or {}), **d.get("settings", {})},
            {**ONBOARDING, **(r[0]["onboarding"] or {}), **d.get("onboarding", {})})


def save_profile(s, settings=None, onboarding=None):
    st, ob = profile(s)
    st, ob = {**st, **(settings or {})}, {**ob, **(onboarding or {})}
    s.update("profiles", {"settings": {}, "onboarding": {},
                          "enc": seal(s, "profiles", s.uid, {"settings": st, "onboarding": ob})})
    return st, ob


##################################################
# 사람
##################################################

def people(s):
    return [{"id": r["id"], **unseal(s, "people", r["id"], r["enc"]), "relation": r["relation"], "auto": r["auto"]}
            for r in s.rows("people", order="created_at")]


def add_person(s, name, nicknames=(), relation="", auto=False):
    pid = new_id("p")
    data = {"name": name, "nicknames": [n for n in nicknames if n]}
    s.insert("people", {"id": pid, "relation": relation or "", "auto": auto, "enc": seal(s, "people", pid, data)})
    return {"id": pid, **data, "relation": relation or "", "auto": auto}


def update_person(s, pid, name=None, nicknames=None, relation=None):
    p = next((p for p in people(s) if p["id"] == pid), None)
    if not p:
        return None
    p = {**p, **{k: v for k, v in {"name": name, "nicknames": nicknames, "relation": relation}.items() if v is not None}}
    s.update("people", {"relation": p["relation"], "auto": False,
                        "enc": seal(s, "people", pid, {"name": p["name"], "nicknames": p["nicknames"]})}, id=pid)
    return {**p, "auto": False}


def delete_person(s, pid):
    """지우기 = 저장된 글 속 이름 · 별명을 관계 말로 바꾸고 문장은 남긴다(끊긴 기록의 단계 저장값 · 피드백 글 포함).
    그 이름을 묻던 질문은 지운다. 벡터는 가명 글로 만들어 이름이 없다. 바꾼 행 수를 돌려준다."""
    p = next((p for p in people(s) if p["id"] == pid), None)
    if not p:
        return None
    names = {p["name"], *p["nicknames"]}
    for q in questions(s):
        if q["name"] in names:
            s.delete("people_questions", id=q["id"])
    replaced = 0
    for r in s.rows("entries"):
        if r.get("steps_enc"):
            data = unseal(s, "entries.steps", r["id"], r["steps_enc"])
            new = _map_strings(data, lambda t: forget(t, p))
            if new != data:
                replaced += 1
                s.update("entries", {"steps_enc": seal(s, "entries.steps", r["id"], new)}, id=r["id"])
    for table in ENC_TABLES + ("states",):
        for r in s.rows(table):
            rid = _rid(table, r)
            data = unseal(s, table, rid, r["enc"])
            new = _map_strings(data, lambda t: forget(t, p))
            if new != data:
                replaced += 1
                s.update(table, {"enc": seal(s, table, rid, new)}, **({"key": rid} if table == "states" else {"id": rid}))
    s.delete("thought_people", person_id=pid)
    s.delete("people", id=pid)
    return replaced


def add_question(s, entry_id, name, reason):
    qid = new_id("q")
    s.insert("people_questions", {"id": qid, "entry_id": entry_id, "reason": reason, "answer": None,
                                  "enc": seal(s, "people_questions", qid, {"name": name})})
    return qid


def questions(s, **eq):
    return [{"id": r["id"], "entry_id": r["entry_id"], "reason": r["reason"], "answer": r["answer"],
             **unseal(s, "people_questions", r["id"], r["enc"])} for r in s.rows("people_questions", order="created_at", **eq)]


##################################################
# 해 · 작은 별
##################################################

def suns(s):
    return [{"id": r["id"], "name": r["name"], "custom": r["custom"]} for r in s.rows("suns", order="created_at")]


def ensure_sun(s, name, custom=False):
    hit = s.rows("suns", name=name)
    if hit:
        return hit[0]["id"]
    sid = new_id("d")
    s.insert("suns", {"id": sid, "name": name, "custom": custom})
    return sid


def stars(s):
    return [{"id": r["id"], "sun_id": r["sun_id"], **unseal(s, "stars", r["id"], r["enc"])}
            for r in s.rows("stars", order="created_at")]


def add_star(s, sid, name, sun_id):
    s.upsert("stars", {"id": sid, "sun_id": sun_id, "enc": seal(s, "stars", sid, {"name": name})})


##################################################
# 기록
##################################################

def create_entry(s, eid, written_at, weather, title, text, source="텍스트", source_ref=None, day=None):
    """source: 대화 / 텍스트 / 사진 / 지난 글 묶음. day: 사용자가 고른 글이 다루는 날(date · 'YYYY-MM-DD' · None).
    고르지 않았으면 제목 · 본문 첫 줄 속 날짜(G2), 없으면 쓴 날(추정). 대화는 대화한 날(확실) + 확인 전."""
    written = written_at.astimezone(TZ).date()
    picked = date.fromisoformat(day) if isinstance(day, str) else day
    d, basis, check = read_day(title, text, written, picked or (written if source == "대화" else None))
    data = {"title": title, "text": text, **({"day_check": True} if check else {})}
    s.insert("entries", {"id": eid, "written_at": written_at, "weather": weather, "status": "processing", "step": None,
                         "addressee": None, "star_id": None, "sun_id": None, "steps_enc": None,
                         "error_code": None, "enc": seal(s, "entries", eid, data), "updated_at": now(),
                         "source": source, "source_ref": ref_hash(s, source, source_ref), "day": d, "day_basis": basis,
                         "confirmed": "확인 전" if source == "대화" else None, "record_type": None,
                         "content_hash": content_hash(s, title, text, written_at)})


def same_entry(s, title, text, written_at, source="텍스트", source_ref=None):
    """같은 날 쓴 같은 글(같은 설정) 또는 같은 원본을 이미 받은 기록 id. 없으면 None(PRD §8.5 A: 다시 보내지 않기)."""
    hit = s.rows("entries", content_hash=content_hash(s, title, text, written_at), limit=1)
    if not hit and source_ref:
        hit = s.rows("entries", source_ref=ref_hash(s, source, source_ref), limit=1)
    return hit[0]["id"] if hit else None


def set_day(s, eid, day):
    """사용자가 고친 글이 다루는 날(확실). '날짜 확인 필요' 표시를 거둔다. 정리 결과(생각의 날)는 다시 돌리지 않는다."""
    data = {k: v for k, v in entry(s, eid)["data"].items() if k != "day_check"}
    s.update("entries", {"day": day, "day_basis": "확실", "enc": seal(s, "entries", eid, data), "updated_at": now()}, id=eid)


def entry(s, eid):
    r = s.rows("entries", id=eid)
    if not r:
        return None
    r = r[0]
    r["data"] = unseal(s, "entries", eid, r["enc"])
    r["crisis"] = bool(r["data"].get("crisis"))   # 위기 표시는 enc 안에만
    r["steps"] = unseal(s, "entries.steps", eid, r["steps_enc"]) if r.get("steps_enc") else {}
    return r


def checkpoint(s, eid, step, steps):
    s.update("entries", {"step": step, "steps_enc": seal(s, "entries.steps", eid, steps), "updated_at": now()}, id=eid)
    until = now() + timedelta(seconds=config.RUN_LOCK_S)
    s.update("entries", {"locked_until": until}, lt={"locked_until": until}, id=eid)   # 잡혀 있는 잠금만 늘린다


def lock(s, eid):
    """실행 잠금: 잠금이 없거나 만료됐을 때만 잡는다(DB 조건부 update 라 인스턴스가 여러 개여도 하나만 잡음)."""
    t = now()
    until = t + timedelta(seconds=config.RUN_LOCK_S)
    return bool(s.update("entries", {"locked_until": until}, id=eid, locked_until=None)
                or s.update("entries", {"locked_until": until}, lt={"locked_until": t}, id=eid))


def unlock(s, eid):
    s.update("entries", {"locked_until": None}, id=eid)


def is_locked(row):
    return bool(row.get("locked_until") and row["locked_until"] > now())


def set_status(s, eid, status, code=None):
    s.update("entries", {"status": status, "error_code": code, "updated_at": now()}, id=eid)


def entries(s, limit=None, before=None, **eq):
    out = [{**r, "data": unseal(s, "entries", r["id"], r["enc"])}
           for r in s.rows("entries", order="written_at desc", limit=limit, lt={"written_at": before} if before else None, **eq)]
    for e in out:
        e["crisis"] = bool(e["data"].get("crisis"))
    return out


def delete_entry(s, vectors, eid):
    """기록과 그 생각 · 관계 · 한마디 · 피드백 · 벡터까지. 메모리 가짜에는 FK cascade 가 없어 직접 지운다.
    남은 기록이 모두 끝난 상태면 이 기록에만 쓰인 작은 별 · 자동 등록 사람도 정리한다
    (끊긴 기록의 단계 저장값이 그 id 를 들고 있을 수 있어 그때는 남긴다)."""
    if not s.rows("entries", id=eid):
        return False
    tids = [t["id"] for t in s.rows("thoughts", entry_id=eid)]
    rids = [r["id"] for r in s.rows("relations", from_thought=tids) + s.rows("relations", to_thought=tids)] if tids else []
    for table, col in (("thought_people", "thought_id"), ("aspiration_reached", "thought_id")):
        s.delete(table, **{col: tids})
    s.delete("relations", from_thought=tids)
    s.delete("relations", to_thought=tids)
    for st in s.rows("states"):   # 이 기록의 생각 · 관계로 시작된 상태(키에 생각 id 가 들어 있음)
        if any(t in st["key"] for t in tids):
            s.delete("states", key=st["key"])
    for table in ("thoughts", "messages", "aspiration_reached", "people_questions"):
        s.delete(table, entry_id=eid)
    s.delete("feedback", target_id=[eid, *tids, *rids])
    for f in s.rows("feedback", target="relation"):   # '아니에요'로 이미 지운 관계의 피드백(관계 id = 옛생각id>새생각id)
        if any(t in (f["target_id"] or "").split(">") for t in tids):
            s.delete("feedback", id=f["id"])
    s.delete("entries", id=eid)
    rest = entries(s)
    if all(e["status"] == "done" for e in rest):
        used = {t["star_id"] for t in s.rows("thoughts")} | {e["star_id"] for e in rest}
        for st in s.rows("stars"):
            if st["id"] not in used:
                s.delete("stars", id=st["id"])
        linked = {tp["person_id"] for tp in s.rows("thought_people")}
        texts = "\n".join(f"{e['data'].get('title', '')}\n{e['data'].get('text', '')}" for e in rest)
        for p in people(s):
            if p["auto"] and p["id"] not in linked and not any(n in texts for n in [p["name"], *p["nicknames"]]):
                s.delete("people", id=p["id"])
    vectors.delete(s.uid, entry_id=eid)
    return True


WIPE = ("aspiration_reached", "messages", "relations", "thought_people", "people_questions", "thoughts", "states",
        "entries", "stars", "suns", "people", "aspirations", "feedback", "runs", "profiles")


def wipe(s):
    """이 사용자의 모든 행(FK 순서). 계정 지우기 · 시드에서 쓴다."""
    for t in WIPE:
        s.delete(t)


def thoughts(s, **eq):
    out = []
    for r in s.rows("thoughts", order="created_at", **eq):
        d = unseal(s, "thoughts", r["id"], r["enc"])
        out.append({k: r[k] for k in ("id", "entry_id", "star_id", "sun_id", "position", "kind", "certainty", "value", "grateful")}
                   | d)
    people_of = {}
    for tp in s.rows("thought_people", thought_id=[t["id"] for t in out]) if out else []:
        people_of.setdefault(tp["thought_id"], []).append(tp["person_id"])
    for t in out:
        t["people"] = people_of.get(t["id"], [])
    return sorted(out, key=lambda t: (t["entry_id"], t["position"]))


def save_thought(s, eid, t):
    """t: 정리된 생각(graph 의 today 모양: id · thought · kind · certainty · value · quote · self_change · flags · original ·
    topic · star_id · sun_id · position · people(사람 id))."""
    s.insert("thoughts", {"id": t["id"], "entry_id": eid, "star_id": t["star_id"], "sun_id": t["sun_id"],
                          "position": t["position"], "kind": t["kind"], "certainty": t["certainty"],
                          "value": t["value"] or None, "grateful": "감사" in t["flags"],
                          "enc": seal(s, "thoughts", t["id"], {"text": t["thought"], "quote": t["quote"],
                                                               "self_change": t["self_change"] or None,
                                                               "other": t["original"].get("kind"), "topic": t["topic"],
                                                               "original": t["original"]})})
    for pid in t["people"]:
        s.insert("thought_people", {"thought_id": t["id"], "person_id": pid})


def relations(s, **eq):
    return [{"id": r["id"], "from": r["from_thought"], "to": r["to_thought"], "from_record": r["from_entry"],
             "to_record": r["to_entry"], "type": r["type"], "group": r["grp"], "line": r["line"],
             "cross_domain": r["cross_domain"], "needs_confirm": r["needs_confirm"], "vow_kept": r["vow_kept"],
             **unseal(s, "relations", r["id"], r["enc"])} for r in s.rows("relations", order="created_at", **eq)]


def save_relation(s, r):
    s.upsert("relations", {"id": r["id"], "from_thought": r["from"], "to_thought": r["to"], "from_entry": r["from_record"],
                           "to_entry": r["to_record"], "type": r["type"], "grp": r["group"], "line": r["line"],
                           "cross_domain": r["cross_domain"], "needs_confirm": r["needs_confirm"],
                           "vow_kept": r.get("vow_kept", False),
                           "enc": seal(s, "relations", r["id"], {k: r.get(k) for k in ("explanation", "quote", "axis", "topic", "notes", "color")})})


def states(s):
    return {r["key"]: unseal(s, "states", r["key"], r["enc"]) for r in s.rows("states")}


def save_states(s, new, old):
    for k, v in new.items():
        if old.get(k) != v:
            s.upsert("states", {"key": k, "kind": v["kind"], "state": v.get("state"), "updated_at": now(),
                                "enc": seal(s, "states", k, v)}, key=("user_id", "key"))
    for k in set(old) - set(new):
        s.delete("states", key=k)


def message(s, row):
    """messages 행 → {text, next_question, mode, check_in}. 위로 모드 · 안부 한 줄은 enc 안에만."""
    return {"mode": "normal", **unseal(s, "messages", row["id"], row["enc"])}


def aspirations(s):
    """판 순서(오래된 것 → 지금). 마지막이 지금 판."""
    out = []
    for r in s.rows("aspirations", order="version"):
        reached = [{"entry_id": x["entry_id"], "thought_id": x["thought_id"], "at": x["at"],
                    **unseal(s, "aspiration_reached", x["id"], x["enc"])}
                   for x in s.rows("aspiration_reached", order="at", aspiration_id=r["id"])]
        out.append({"id": r["id"], "version": r["version"], "values": list(r["values"] or []), "said_at": r["said_at"],
                    **unseal(s, "aspirations", r["id"], r["enc"]), "reached": reached})
    return out


def add_aspiration(s, now_text, said, obstacle, if_then, values):
    aid = new_id("a")
    version = len(s.rows("aspirations")) + 1
    s.insert("aspirations", {"id": aid, "version": version, "values": list(values), "said_at": now(),
                             "enc": seal(s, "aspirations", aid, {"now": now_text, "said": said, "obstacle": obstacle,
                                                                 "if_then": if_then})})
    return aid


def add_feedback(s, target, target_id, value, text=None, relation=None):
    """relation: '아니에요'로 지운 관계 {type, from, to}(오답 재료, 암호문에만)."""
    fid = new_id("f")
    mood = value in MOOD_FEEDBACK
    data = {k: v for k, v in {"text": text, "value": value if mood else None, "relation": relation}.items() if v}
    s.insert("feedback", {"id": fid, "target": target, "target_id": target_id, "value": MOOD_LABEL if mood else value,
                          "enc": seal(s, "feedback", fid, data) if data else None, "studio_config": run_config(s, target_id)})


def run_config(s, target_id):
    """버튼 대상(기록 · 생각 · 관계 id)을 처리한 실행의 Studio 설정 번호(누른 때의 설정이 아님). 처리한 기록이 없으면 None."""
    tid = (target_id or "").split(">")[-1]   # 관계 id = 옛 생각>새 생각. 관계는 새 생각의 기록을 처리할 때 생긴다
    t = s.rows("thoughts", id=tid)
    r = s.rows("runs", entry_id=t[0]["entry_id"] if t else tid, order="id desc", limit=1)
    return r[0]["studio_config"] if r else None


def feedback_counts(s):
    return Counter(unseal(s, "feedback", r["id"], r["enc"]).get("value", r["value"]) if r["value"] == MOOD_LABEL
                   else r["value"] for r in s.rows("feedback"))


def add_run(s, entry_id, step, ms=0, calls=0, est_usd=0.0, code=None, meta=None):
    s.insert("runs", {"entry_id": entry_id, "step": step, "ms": int(ms), "calls": calls, "est_usd": round(est_usd, 5),
                      "error_code": code, "meta": meta or {}, "studio_config": studio_config()})


def month_cost(s):
    start = datetime.now(TZ).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return float(sum(r["est_usd"] or 0 for r in s.rows("runs") if r["created_at"] >= start))


def processed_today(s):
    """오늘 처리를 시작한(또는 이어 한) 기록 id. 남은 행 수가 아니라 runs 로 세서 지워도 줄지 않고, 시드한 글은 세지 않는다."""
    start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return {r["entry_id"] for r in s.rows("runs", step=["start", "resume"]) if r["created_at"] >= start}


def resumes(s, eid):
    return len(s.rows("runs", entry_id=eid, step="resume"))
