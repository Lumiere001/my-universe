"""
universe.py

우주 상태(= 정리된 기록 파일)와 코드가 하는 판단:
세부 주제 → 삶의 영역 연결, 관련 과거 생각 고르기, 관계 규칙(시간 · 감정 · 실선/점선), 별 자리 정하기.
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


# 삶의 영역: 온톨로지의 위층(닫힌 목록). 글에서 나온 세부 주제(열린 목록)는 이 중 하나에 붙는다.
# 근거: Personal Wellbeing Index(PWI, International Wellbeing Group)의 삶의 영역 7개 + 선택 영역 "영성·종교",
#       WHOQOL-100(WHO)의 환경 영역에 있는 "여가" 측면. 마음(감정)은 영역이 아니라 생각의 종류 "감정"으로 담는다.
DOMAINS = [
    ("삶의 성취", ["성취", "진로", "일", "직장", "취업", "커리어", "인턴", "면접", "배움", "공부", "학업", "시험", "독서", "기록"]),
    ("관계", ["관계", "인간관계", "가족", "부모", "부모님", "친구", "우정", "연애", "동생"]),
    ("공동체", ["공동체", "동아리", "리더십", "봉사", "모임", "교회", "지역"]),
    ("건강", ["건강", "운동", "습관", "자기관리", "수면", "걷기", "마음", "감정", "스트레스"]),
    ("생활 수준", ["생활", "돈", "소비", "살림", "집", "일상"]),
    ("미래 안정", ["미래", "불안", "노후", "준비"]),
    ("안전", ["안전", "위험", "사고"]),
    ("영성·신앙", ["영성", "신앙", "종교", "묵상", "기도", "믿음", "의미", "삶", "가치관"]),
    ("여가", ["여가", "취미", "여행", "휴식", "창작", "놀이"]),
]
_alias_embs = None


def new_state(owner=""):
    state = {"version": 2, "owner": owner, "records": {}, "order": [], "thoughts": {},
             "hubs": {}, "relations": [], "reports": {}, "names": [], "layout": {}}
    ensure_domains(state)
    return state


def ensure_domains(state):
    for i, (name, _) in enumerate(DOMAINS):
        state["hubs"].setdefault(f"D{i + 1}", {"id": f"D{i + 1}", "name": name, "topics": {}})


def _days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _h(s, mod):
    return int(hashlib.md5(s.encode()).hexdigest(), 16) % mod


##################################################
# 세부 주제 → 삶의 영역
##################################################

def _aliases():
    """영역마다 대표 낱말의 임베딩 (한 번만 계산해 data/ops에 둔다)."""
    global _alias_embs
    if _alias_embs is None:
        import json
        import embedder
        f = config.DATA_DIR / "ops" / f"domain_aliases_{config.EMBEDDING_MODEL}.json"
        words = [w for _, ws in DOMAINS for w in ws]
        cached = json.loads(f.read_text()) if f.exists() else {}
        if set(words) - set(cached):
            vecs = embedder.embed(words)
            cached = dict(zip(words, vecs))
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(cached))
        _alias_embs = [(f"D{i + 1}", [cached[w] for w in ws]) for i, (_, ws) in enumerate(DOMAINS)]
    return _alias_embs


def domain_of(vec, sim=None):
    sim = sim or topic_cos
    return max(_aliases(), key=lambda d: max(sim(vec, a) for a in d[1]))[0]


def link_hub(state, topic, topic_emb):
    """세부 주제를 삶의 영역 하나에 붙인다. 이름이 맞으면 그 영역, 아니면 (중심 보정) 임베딩이 가장 가까운 영역."""
    ensure_domains(state)
    hid = None
    for i, (_, words) in enumerate(DOMAINS):
        if topic in words or any(len(w) >= 2 and w in topic for w in words):
            hid = f"D{i + 1}"
            break
    hid = hid or domain_of(topic_emb)
    topics = state["hubs"][hid].setdefault("topics", {})
    topics[topic] = topics.get(topic, 0) + 1
    return hid


##################################################
# 관련 과거 생각 고르기
##################################################

def pick_past(state, today_thoughts, record_id):
    hubs_today = {t["hub"] for t in today_thoughts}
    topics_today = {t["topic"] for t in today_thoughts}
    scored = []
    for p in state["thoughts"].values():
        if p["record_id"] == record_id:
            continue
        sim = max((cos(t["emb"], p["emb"]) for t in today_thoughts), default=0.0)
        same_hub = p["hub"] in hubs_today
        if same_hub or sim >= config.SAME_STORY_THETA:
            # 같은 세부 주제가 먼저, 그다음 같은 영역 (영역이 넓어도 비교 대상이 흐려지지 않게)
            scored.append((sim + (0.15 if p["topic"] in topics_today else 0.0) + (0.05 if same_hub else 0.0), p))
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
        if pa["kind"] == "다짐" and rtype == "해소":
            notes.append("해소→이어짐(다짐은 풀리는 것이 아니라 지켜지는 것)")
            rtype = "이어짐"
        if pa["kind"] == "질문" and pb["kind"] == "신념·원칙" and same_hub and rtype in ("바뀜", "이어짐"):
            notes.append(f"{rtype}→해소(질문이 신념이 됨)")
            rtype = "해소"
        if rtype in ("바뀜", "해소") and "감정" in (pa["kind"], pb["kind"]):
            notes.append(f"버림(감정이 달라진 것은 {rtype}이 아님)")
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
    """삶의 영역을 고리 모양으로 고정 배치한다."""
    a = math.radians(-90 + i * 360 / len(DOMAINS))
    r = 330 if i < len(DOMAINS) else 330 + 90 * (1 + (i - len(DOMAINS)) // 10)
    return round(r * math.cos(a), 1), round(r * math.sin(a), 1)


def place(state, rid, summary_emb=None):
    if rid in state["layout"]:
        return
    hubs = list(state["hubs"])
    weights = {}
    for t in state["thoughts"].values():
        if t["record_id"] == rid:
            weights[t["hub"]] = weights.get(t["hub"], 0) + 1
    if not weights and summary_emb is not None:   # 생각 없는 글: 요약과 가장 가까운 영역 곁에
        best = domain_of(summary_emb, sim=cos)
        weights = {best: 1}
        state["records"][rid]["near_hub"] = best
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
