"""
app/repository/edit.py

사용자가 우주를 고친다(WS16, PRD §4.2 · §8.7 · §9): 해 추가 · 기준 축 바꾸기, 작은 별을 다른 해로 옮기기 · 합치기,
생각 종류 · 가치 고치기, 사람을 지울 때 그 사람이 나온 생각 숨기기.
고친 내용은 feedback 표에 오답 재료로 남긴다(값 이름만 평문, 무엇을 무엇으로 고쳤는지는 암호문).
끝나지 않은 기록의 단계 저장값(steps_enc)도 같이 고친다 — 이어 하기 때 지운 별 · 생각 id 로 저장하지 않게.
"""

from app.repository import diary
from app.service.rules.relations import is_question
from app.service.rules.states import parse_due
from app.service.rules.topics import BASE

USER_AREA = "사용자 영역"   # 맞는 기준 축이 없을 때(PRD §9 '사용자 일기에서 태양계를 만들기')
AXES = [*BASE, USER_AREA]
DECLINED = "합치지 않음"


def lesson(s, target, target_id, value, **data):
    """고친 내용 한 줄(오답 재료, PRD §8.7 '고친 내용'). 버튼을 누른 때가 아니라 그 대상을 처리한 실행의 설정 번호를 붙인다."""
    fid = diary.new_id("f")
    s.insert("feedback", {"id": fid, "target": target, "target_id": target_id, "value": value,
                          "enc": diary.seal(s, "feedback", fid, data), "studio_config": diary.run_config(s, target_id)})


def busy(s):
    """정리 중인 기록이 있으면 True(그 기록은 지금 별 · 생각 id 를 메모리에 들고 있다)."""
    return any(diary.is_locked(e) for e in s.rows("entries"))


def _walk(x, fn):
    if isinstance(x, dict):
        return fn({k: _walk(v, fn) for k, v in x.items()})
    if isinstance(x, list):
        return [_walk(v, fn) for v in x]
    return x


def _fix_steps(s, fn):
    for r in s.rows("entries", status=["processing", "failed"]):
        if r.get("steps_enc"):
            old = diary.unseal(s, "entries.steps", r["id"], r["steps_enc"])
            new = fn(old)
            if new != old:
                s.update("entries", {"steps_enc": diary.seal(s, "entries.steps", r["id"], new)}, id=r["id"])


##################################################
# 해
##################################################

def _sun(r):
    return {"id": r["id"], "name": r["name"], "custom": r["custom"],
            "axis": r.get("axis") or (r["name"] if r["name"] in BASE else None)}


def suns(s):
    return [_sun(r) for r in s.rows("suns", order="created_at")]


def sun(s, sid):
    r = s.rows("suns", id=sid)
    return _sun(r[0]) if r else None


def add_sun(s, name, axis):
    """사용자가 추가한 해. 같은 이름의 해가 이미 있으면 사용자 해로 표시만 한다(우주에 뜸). 이미 사용자 해면 None."""
    hit = s.rows("suns", name=name)
    if hit and hit[0]["custom"]:
        return None
    if hit:
        s.update("suns", {"custom": True, "axis": hit[0].get("axis") or axis}, id=hit[0]["id"])
        return sun(s, hit[0]["id"])
    sid = diary.new_id("d")
    s.insert("suns", {"id": sid, "name": name, "custom": True, "axis": axis})
    return sun(s, sid)


def set_axis(s, sid, axis):
    old = sun(s, sid)
    if old and old["axis"] != axis:
        s.update("suns", {"axis": axis}, id=sid)
        lesson(s, "sun", sid, "축 고침", sun=old["name"], **{"from": old["axis"], "to": axis})
    return old and {**old, "axis": axis}


##################################################
# 작은 별
##################################################

def star(s, sid):
    return next((x for x in diary.stars(s) if x["id"] == sid), None)


def set_sun(s, sid, sun_id, to_name):
    """작은 별 하나의 해 바꾸기: 별 · 그 별의 생각 · 그 별이 주인인 기록 · 이어 하기 상태(묶음 해 고르기도 쓴다)."""
    s.update("stars", {"sun_id": sun_id}, id=sid)
    s.update("thoughts", {"sun_id": sun_id}, star_id=sid)
    s.update("entries", {"sun_id": sun_id}, star_id=sid)
    _fix_steps(s, lambda st_: _walk(st_, lambda d: {**d, "sun_id": sun_id, **({"domain": to_name} if "domain" in d else {})}
                                    if d.get("star_id") == sid else d))


def group_of(s, sid):
    """작은 별 sid 와 같은 묶음의 별들(sid 가 머리면 묶음 전체, 아니면 sid 하나). 화면은 묶음 머리 id 로 고친다(rules.groups)."""
    all_ = diary.stars(s)
    heads = diary.star_heads(all_)
    return [x for x in all_ if heads[x["id"]]["id"] == sid] or [x for x in all_ if x["id"] == sid]


def move_star(s, sid, sun_id):
    """작은 별(묶음이면 묶음 전체)을 다른 해로: 별 · 그 별의 생각 · 그 별이 주인인 기록의 해를 바꾸고, 사용자가 고른 해라고
    표시(pin)해 다음 묶기가 해를 바꾸지 않게 한다. 다음 글의 같은 주제도 이 해로 간다(graph.record_input 이 작은 별의 해를 넘김)."""
    st, to = star(s, sid), sun(s, sun_id)
    if not st or not to:
        return None
    if st["sun_id"] != sun_id or not st.get("pin"):
        frm = sun(s, st["sun_id"]) if st["sun_id"] else None
        for x in group_of(s, sid):
            set_sun(s, x["id"], sun_id, to["name"])
            diary.set_star(s, x, pin=True)
        if st["sun_id"] != sun_id:
            lesson(s, "star", sid, "옮김", topic=st["name"], **{"from": frm and frm["name"], "to": to["name"]})
    return {**st, "sun_id": sun_id}


def _rename_topic(s, table, old, new):
    for r in s.rows(table):
        rid = r["key"] if table == "states" else r["id"]
        d = diary.unseal(s, table, rid, r["enc"])
        if d.get("topic") == old:
            s.update(table, {"enc": diary.seal(s, table, rid, {**d, "topic": new})}, **({"key": rid} if table == "states" else {"id": rid}))


def merge_stars(s, from_id, into_id):
    """작은 별 from(묶음이면 묶음 전체)을 into 로 합친다(사용자가 확인한 뒤 — 사람이 정한 것이라 실제로 합친다, rules.groups)."""
    a, b = star(s, from_id), star(s, into_id)
    if not a or not b or from_id == into_id:
        return None
    for x in group_of(s, from_id):
        if x["id"] != into_id:
            _merge_one(s, x["id"], into_id)
    lesson(s, "star", into_id, "합침", **{"from": a["name"], "into": b["name"]})
    return b


def _merge_one(s, from_id, into_id):
    """생각은 into 의 이름 · 해로 옮기고, 관계 · 상태의 주제 이름도 바꾼다.
    다음 글에서 기록 Agent 가 옛 이름을 다시 내도 into 로 가게 비슷한 말(topic_aliases)로 남긴다."""
    a, b = star(s, from_id), star(s, into_id)
    to = sun(s, b["sun_id"]) if b["sun_id"] else None
    for r in s.rows("thoughts", star_id=from_id):
        d = diary.unseal(s, "thoughts", r["id"], r["enc"])
        s.update("thoughts", {"star_id": into_id, "sun_id": b["sun_id"],
                              "enc": diary.seal(s, "thoughts", r["id"], {**d, "topic": b["name"]})}, id=r["id"])
    s.update("entries", {"star_id": into_id, "sun_id": b["sun_id"]}, star_id=from_id)
    for table in ("relations", "states"):
        _rename_topic(s, table, a["name"], b["name"])

    def fix(d):
        if d.get("star_id") != from_id:
            return d
        d = {**d, "star_id": into_id, "sun_id": b["sun_id"], "topic": b["name"]}
        return {**d, "domain": to["name"]} if "domain" in d and to else d
    _fix_steps(s, lambda st_: _walk(st_, fix))
    # ponytail: 벡터 메타의 star_id 는 그대로 둔다(읽는 곳 없음). 별로 벡터를 거르게 되면 여기서 같이 고친다.
    s.delete("stars", id=from_id)
    st, _ = diary.profile(s)
    aliases = {k: (b["name"] if v == a["name"] else v) for k, v in (st.get("topic_aliases") or {}).items() if k != b["name"]}
    diary.save_profile(s, settings={"topic_aliases": {**aliases, a["name"]: b["name"]}})


def pair_id(a, b):
    return ">".join(sorted((a, b)))


def decline_merge(s, a, b):
    sa, sb = star(s, a), star(s, b)
    if not sa or not sb:
        return False
    lesson(s, "star", pair_id(a, b), DECLINED, a=sa["name"], b=sb["name"])
    return True


def declined(s):
    return {r["target_id"] for r in s.rows("feedback", target="star", value=DECLINED)}


##################################################
# 생각
##################################################

def _open_kind(kind, certainty):
    return "다짐" if kind == "다짐" else "질문" if is_question({"kind": kind, "certainty": certainty}) else None


def fix_thought(s, tid, patch):
    """patch: {kind?, value?}. 고친 칸마다 오답 재료 한 줄. 종류가 바뀌면 다짐 · 질문 상태도 맞춘다
    (다짐이 아니게 되면 금빛 고리를 거두고, 다짐 · 질문이 되면 열림으로 시작)."""
    r = s.rows("thoughts", id=tid)
    if not r:
        return None
    r = r[0]
    values = {k: v for k, v in patch.items() if v != r[k]}
    if "kind" in values and values["kind"] != "감정":
        values["grateful"] = False   # '감사'는 감정에만 붙는 표시
    if not values:
        return r
    s.update("thoughts", values, id=tid)
    for k in ("kind", "value"):
        if k in values:
            lesson(s, "thought", tid, "고침", field=k, **{"from": r[k], "to": values[k]})
    if "kind" in values:
        old = diary.states(s)
        new, want = dict(old), _open_kind(values["kind"], r["certainty"])
        if tid in new and new[tid]["kind"] in ("다짐", "질문") and new[tid]["kind"] != want:
            del new[tid]
        if want and tid not in new:
            d = diary.unseal(s, "thoughts", tid, r["enc"])
            e = s.rows("entries", id=r["entry_id"])[0]
            day = str(e["day"]) if e.get("day") else diary.local_day(e["written_at"])
            new[tid] = {"kind": want, "state": "열림", "topic": d.get("topic"),
                        "history": [{"to": "열림", "why": "사용자가 종류를 고침", "day": day, "thought": tid}],
                        **({"marks": [], "due": parse_due(f"{d.get('text', '')} {d.get('quote', '')}", day)}
                           if want == "다짐" else {})}
        diary.save_states(s, new, old)
    return {**r, **values}


##################################################
# 사람을 지울 때 그 사람이 나온 생각 숨기기
##################################################

def person_thought_ids(s, pid):
    return [x["thought_id"] for x in s.rows("thought_people", person_id=pid)]


def hide_thoughts(s, tids):
    """생각 · 그 생각의 관계 · 상태 · 닿은 순간 · 피드백을 지운다(벡터는 부르는 쪽이 먼저 지움). 글 본문은 남긴다.
    지우는 방식은 diary.delete_entry 와 같다(메모리 가짜에는 FK cascade 가 없어 직접)."""
    if not tids:
        return 0
    rids = [r["id"] for r in s.rows("relations", from_thought=tids) + s.rows("relations", to_thought=tids)]
    for table, col in (("thought_people", "thought_id"), ("aspiration_reached", "thought_id")):
        s.delete(table, **{col: tids})
    s.delete("relations", from_thought=tids)
    s.delete("relations", to_thought=tids)
    for st in s.rows("states"):
        if any(t in st["key"] for t in tids):
            s.delete("states", key=st["key"])
    s.delete("feedback", target_id=[*tids, *rids])
    for f in s.rows("feedback", target="relation"):
        if any(t in (f["target_id"] or "").split(">") for t in tids):
            s.delete("feedback", id=f["id"])
    n = s.delete("thoughts", id=tids)
    gone = set(tids)

    def drop(st_):
        out = dict(st_)
        if "past" in out:
            out["past"] = [p for p in out["past"] if p.get("id") not in gone]
        if "relations" in out:
            out["relations"] = [r for r in out["relations"] if not {r.get("from"), r.get("to")} & gone]
        return out
    _fix_steps(s, drop)
    return n
