"""
universe.py

우주 상태(= 정리된 기록 파일)와 코드가 하는 판단:
주제 → 성운 연결, 관련 과거 생각 고르기, 관계 규칙(시간 · 감정 · 실선/점선), 별 자리 정하기.
"""

import hashlib
import math
from datetime import date

import config
from embedder import cos, topic_cos

KINDS = ["해석", "신념·원칙", "질문", "다짐", "반성", "감정"]
REL_TYPES = ["이어짐", "바뀜", "긴장", "해소", "어긋남", "목표 충돌"]
CONFLICT = {"긴장", "어긋남", "목표 충돌"}
PRIORITY = ["해소", "바뀜", "어긋남", "목표 충돌", "긴장", "이어짐"]   # 같은 두 글 사이에 여러 관계가 나오면 앞의 것


def new_state(owner=""):
    return {"version": 1, "owner": owner, "records": {}, "order": [], "thoughts": {},
            "hubs": {}, "relations": [], "reports": {}, "names": [], "layout": {}}


def _days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _h(s, mod):
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % mod


##################################################
# 주제 → 성운
##################################################

def link_hub(state, topic, topic_emb):
    """같은 이름이거나 (중심 보정) 유사도 θ₂ 이상인 성운에 붙이고, 아니면 새 성운을 만든다."""
    for h in state["hubs"].values():
        if h["name"] == topic or topic in h.get("aliases", []):
            return h["id"]
    for h in state["hubs"].values():   # "관계"와 "인간관계"처럼 한쪽이 다른 쪽을 품으면 같은 성운
        if len(h["name"]) >= 2 and len(topic) >= 2 and (h["name"] in topic or topic in h["name"]):
            h.setdefault("aliases", []).append(topic)
            return h["id"]
    best, best_sim = None, -1.0
    for h in state["hubs"].values():
        s = topic_cos(topic_emb, h["emb"])
        if s > best_sim:
            best, best_sim = h, s
    if best and best_sim >= config.NEW_HUB_THETA:
        best.setdefault("aliases", []).append(topic)
        return best["id"]
    hid = f"H{len(state['hubs']) + 1}"
    state["hubs"][hid] = {"id": hid, "name": topic, "emb": topic_emb, "aliases": []}
    return hid


##################################################
# 관련 과거 생각 고르기
##################################################

def pick_past(state, today_thoughts, record_id):
    hubs_today = {t["hub"] for t in today_thoughts}
    scored = []
    for p in state["thoughts"].values():
        if p["record_id"] == record_id:
            continue
        sim = max((cos(t["emb"], p["emb"]) for t in today_thoughts), default=0.0)
        same_hub = p["hub"] in hubs_today
        if same_hub or sim >= config.SAME_STORY_THETA:
            scored.append((sim + (0.15 if same_hub else 0.0), p))
    scored.sort(key=lambda x: -x[0])
    return sorted([p for _, p in scored[:config.PAST_LIMIT]], key=lambda p: p["day"])


##################################################
# 관계 규칙 (PRD §8.4)
##################################################

def apply_rules(state, raw, ids, record_id):
    """관측 Agent가 낸 관계를 규칙으로 거른다. (남은 관계, 규칙으로 바뀐 내역)"""
    th = state["thoughts"]
    kept, notes, seen = [], [], set()
    for r in raw:
        rtype = (r.get("type") or "").strip()
        a, b = ids.get((r.get("past_id") or "").strip()), ids.get((r.get("today_id") or "").strip())
        if rtype not in REL_TYPES or not a or not b or a == b:
            notes.append(f"버림(ID·종류 확인 안 됨): {rtype}")
            continue
        pa, pb = sorted([th[a], th[b]], key=lambda t: (t["day"], t["id"]))   # 옛 생각 → 새 생각
        gap = _days(pa["day"], pb["day"])
        same_hub = pa.get("hub") == pb.get("hub") or pa["record_id"] == pb["record_id"]
        if pa["kind"] == "다짐" and pb["kind"] == "반성" and same_hub and gap <= config.VOW_WINDOW_DAYS and rtype != "어긋남":
            notes.append(f"{rtype}→어긋남(다짐 뒤 {gap}일 안의 반성)")
            rtype = "어긋남"
        if pa["kind"] == "질문" and pb["kind"] == "신념·원칙" and same_hub and rtype in ("바뀜", "이어짐"):
            notes.append(f"{rtype}→해소(질문이 신념이 됨)")
            rtype = "해소"
        if rtype == "바뀜" and "감정" in (pa["kind"], pb["kind"]):
            notes.append("버림(감정이 달라진 것은 바뀜이 아님)")
            continue
        if rtype in ("이어짐", "바뀜", "긴장", "해소", "어긋남") and not same_hub:
            notes.append(f"버림({rtype}인데 다른 성운)")
            continue
        if rtype == "바뀜" and gap < config.CHANGE_MIN_DAYS:
            rtype = "긴장"
            notes.append(f"바뀜→긴장(시간 차 {gap}일)")
        if rtype == "긴장" and gap > config.TENSION_MAX_DAYS:
            notes.append(f"버림(긴장인데 시간 차 {gap}일, 같은 시기가 아님)")
            continue
        if rtype == "목표 충돌" and (gap > config.GOAL_CONFLICT_DAYS or pa["kind"] != "다짐" or pb["kind"] != "다짐"):
            notes.append(f"버림(목표 충돌은 {config.GOAL_CONFLICT_DAYS}일 안의 다짐 둘, {gap}일)")
            continue
        key = (rtype, pa["record_id"], pb["record_id"])   # 같은 두 글 사이 같은 관계는 하나만
        if key in seen:
            continue
        seen.add(key)
        # 실선 = 원문으로 확인: 관측 Agent가 "작성자가 직접 씀"이라 하고, 기록 Agent도 새 생각에서 스스로 쓴 변화를 뽑았을 때만
        stated = (r.get("author_stated") or "").strip() == "예" and bool(pb.get("self_change"))
        kept.append({
            "id": f"L{len(state['relations']) + len(kept) + 1}",
            "type": rtype, "from": pa["id"], "to": pb["id"],
            "from_record": pa["record_id"], "to_record": pb["record_id"],
            "topic": (r.get("topic") or pb["topic"]).strip(),
            "line": "실선" if stated and rtype in ("바뀜", "해소", "이어짐") else "점선",
            "explanation": (r.get("explanation") or "").strip(),
            "axis": (r.get("axis") or "").strip(),
            "gap_days": gap, "observed_in": record_id, "status": "ai",
        })
    # 같은 두 글 사이에는 관계 하나만 남긴다. 규칙으로 확인되는 구체적인 종류를 먼저 고른다.
    best = {}
    for k in kept:
        pair = (k["from_record"], k["to_record"])
        if pair not in best or PRIORITY.index(k["type"]) < PRIORITY.index(best[pair]["type"]):
            best[pair] = k
    dropped = len(kept) - len(best)
    if dropped:
        notes.append(f"같은 두 글 사이 관계 {dropped}개를 우선순위로 정리")
    kept = [k for k in kept if best[(k["from_record"], k["to_record"])] is k]
    for i, k in enumerate(kept):
        k["id"] = f"L{len(state['relations']) + i + 1}"
    return kept, notes


##################################################
# 별의 자리 (한 번 정하면 고정)
##################################################

def hub_xy(i):
    a = math.radians(i * 137.508)
    r = 120 + 70 * math.sqrt(i)
    return round(r * math.cos(a), 1), round(r * math.sin(a), 1)


def place(state, rid, summary_emb=None):
    if rid in state["layout"]:
        return
    hubs = list(state["hubs"])
    weights = {}
    for t in state["thoughts"].values():
        if t["record_id"] == rid:
            weights[t["hub"]] = weights.get(t["hub"], 0) + 1
    if not weights and summary_emb is not None and state["hubs"]:   # 생각 없는 글: 요약과 가장 가까운 성운 곁에
        best = max(state["hubs"].values(), key=lambda h: cos(summary_emb, h["emb"]))
        weights = {best["id"]: 1}
        state["records"][rid]["near_hub"] = best["id"]
    if weights:
        tot = sum(weights.values())
        x = sum(hub_xy(hubs.index(h))[0] * w for h, w in weights.items()) / tot
        y = sum(hub_xy(hubs.index(h))[1] * w for h, w in weights.items()) / tot
    else:
        x, y = 0.0, 0.0
    a = math.radians(_h(rid, 360))
    d = 38 + _h(rid + "d", 5) * 9 + (0 if len(weights) > 1 else 10)
    state["layout"][rid] = [round(x + d * math.cos(a), 1), round(y + d * math.sin(a), 1)]


if __name__ == "__main__":
    s = new_state()
    for i, (tid, day, kind) in enumerate([("A-T1", "2026-05-02", "감정"), ("B-T1", "2026-08-28", "감정"),
                                          ("C-T1", "2026-03-14", "신념·원칙"), ("D-T1", "2026-09-20", "해석"),
                                          ("E-T1", "2026-04-05", "신념·원칙"), ("F-T1", "2026-04-09", "신념·원칙")]):
        s["thoughts"][tid] = {"id": tid, "record_id": tid[0], "day": day, "kind": kind, "topic": "진로", "hub": "H1", "self_change": "예전 → 지금" if tid == "D-T1" else ""}
    s["thoughts"]["G-T1"] = {"id": "G-T1", "record_id": "G", "day": "2026-04-20", "kind": "다짐", "topic": "건강", "hub": "H2"}
    s["thoughts"]["H-T1"] = {"id": "H-T1", "record_id": "H", "day": "2026-05-01", "kind": "반성", "topic": "건강", "hub": "H2"}
    raw = [{"type": "바뀜", "past_id": "P1", "today_id": "T1", "author_stated": "아니오"},
           {"type": "바뀜", "past_id": "P2", "today_id": "T2", "author_stated": "예"},
           {"type": "바뀜", "past_id": "P3", "today_id": "T3", "author_stated": "아니오"},
           {"type": "해소", "past_id": "P9", "today_id": "T3"},
           {"type": "긴장", "past_id": "P4", "today_id": "T4"},
           {"type": "이어짐", "past_id": "P2", "today_id": "T4"}]
    kept, notes = apply_rules(s, raw, {"P1": "A-T1", "T1": "B-T1", "P2": "C-T1", "T2": "D-T1", "P3": "E-T1", "T3": "F-T1", "P4": "G-T1", "T4": "H-T1"}, "X")
    assert [(k["type"], k["line"]) for k in kept] == [("바뀜", "실선"), ("긴장", "점선"), ("어긋남", "점선")], kept
    assert any("다른 성운" in n for n in notes)
    assert any("감정" in n for n in notes) and any("ID" in n for n in notes)
    print("universe rules ok")
