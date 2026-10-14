"""
관계 규칙 v8. 관측 Agent가 낸 관계 후보를 거르고 굳힌다. 숫자(기간 · 유사도) 없이 종류 · 주제 · 영역 · 상태로만 판정한다.

- 판단형(바뀜 · 해소 · 어긋남)은 같은 세부 주제 안에서만.
- 영향형(이어짐 · 긴장 · 목표 충돌)은 근거가 있으면 영역을 넘는다
  (같은 글: 이어 쓴 흐름 + 원문 인용 → 실선 / 다른 날: 원문 설명 → 점선 + 사용자 확인 필요).
- 같은 두 생각 사이 관계는 하나(relation_priority). 감정끼리는 바뀜 · 해소가 아니다.
- 다짐(WS12): 열린 다짐 뒤 다른 글의 같은 주제 자기평가(긍정)가 이어지면 '지켜짐'(vow_kept),
  같은 주제의 그만둔다는 글이 이어지면 '그만둠'(vow_quit, 새 생각이 그 자체로 다짐이면 새 다짐이라 닫지 않음).
  상태는 states.advance 가 바꾼다.
- 설명 글은 G3(사람 판정 · 진단)를 거르고 관측 입력의 내부 번호(T1 · P3)를 지운다(gate.clean_text).
- 시 · 창작 글(글 유형 '창작')의 생각에는 관계를 잇지 않는다(품질 3판, 2026-10-14 동규 '전부 추천대로':
  설정 #2 틀린 연결 10개 중 7개가 4/26 시에 붙음). 비유를 생각으로 읽어 다른 글과 엮는 것을 막는다.
"""

import re

from app.core.ontology import load
from app.service.rules.gate import clean_text
from app.service.rules.normalize import EMOTION, NEG, key

O = load()
REL = {r["name"]: r for r in O["relations"]}
PRIORITY = O["relation_priority"]
# 같은 글 안에서 '이어 쓴 흐름'을 보여 주는 말(cross_domain.same_record의 '그래도 · 그래서 · 때문에'와 같은 무리)
FLOW = ("그래도", "그래서", "때문에", "그런데", "하지만", "그러니", "그러나", "그렇지만", "그러면서")
YES = (True, "예", "yes", "true", "1")
CREATIVE = "창작"   # 글 유형(v8.json record_types, 기록 Agent Classify 갈래)
POS = "자기평가(긍정)"
# 그만둔다는 글: 결정한 꼴만(그만두고 싶다 · 그만둘까 는 소망 · 질문이라 아님)
# ponytail: 낱말 꼴 목록이라 돌려 말한 그만둠은 놓친다. 놓치면 '그만둘래요' 버튼이 받친다.
QUIT = re.compile(r"그만\s?(두기로|두겠|뒀|두었|하기로|하겠|했)|관두기로|관뒀|관두겠|포기하기로|포기했|포기하겠"
                  r"|안\s?하기로|하지\s?않기로|접기로|접었|접겠")
# 그만두지 않는다는 글('포기하지 않기로' · '포기 안 하기로' · '안 그만두기로')은 QUIT 을 보기 전에 지운다
NOT_QUIT = re.compile(r"(포기|그만\s?두|그만|관두)\s?(하지\s?않|지\s?않|안\s?하)|(안|못)\s?(그만|포기|관두)")


def is_question(t):
    """열린 질문: 종류 '질문' 또는 확신 '판단 보류'."""
    return t.get("kind") == "질문" or t.get("certainty") == "판단 보류"


def _open(states, tid):
    s = (states or {}).get(tid)
    return s is None or s.get("state") == "열림"


def _yes(v):
    return (v.strip().lower() if isinstance(v, str) else v) in YES


def filter_relations(cands, thoughts, states=None):
    """cands: [{a, b (또는 past_id · today_id), type, explanation, quoted, author_stated, axis, topic}]
    thoughts: {id: {record_id, day, kind, certainty, topic, domain, quote, thought, self_change, (record_type)}}
    states: 상태 모델(다짐이 열려 있는지 볼 때). 없으면 모두 열림으로 본다.
    돌려줌: (남은 관계들, 버린 것 [{cand, reason}])."""
    kept, dropped = [], []
    for c in cands:
        rtype = (c.get("type") or "").strip()
        a, b = thoughts.get(c.get("a") or c.get("past_id")), thoughts.get(c.get("b") or c.get("today_id"))
        if rtype not in REL or not a or not b or a is b:
            dropped.append({"cand": c, "reason": "ID · 종류 확인 안 됨"})
            continue
        if CREATIVE in (a.get("record_type"), b.get("record_type")):
            dropped.append({"cand": c, "reason": "시 · 창작 글에는 관계를 잇지 않음"})
            continue
        pa, pb = sorted([a, b], key=lambda t: (t["day"], t["id"]))   # 옛 생각 → 새 생각
        same_topic = key(pa.get("topic")) == key(pb.get("topic"))
        notes, vow_kept = [], False

        def drop(reason, c=c):
            dropped.append({"cand": c, "reason": reason})

        # 종류로 정해지는 바로잡기
        vow_quit = False
        later = pa["kind"] == "다짐" and pa["record_id"] != pb["record_id"] and same_topic and _open(states, pa["id"])
        said_quit = later and QUIT.search(NOT_QUIT.sub("", f"{pb.get('thought', '')} {pb.get('quote', '')}"))
        if said_quit and pb["kind"] == "다짐":
            # 새 생각이 그 자체로 다짐('주중엔 야근을 안 하기로 했다')이면 앞 다짐을 그만둔 게 아니라 새 다짐. 닫지 않는다
            notes.append("그만두는 꼴의 새 다짐(앞 다짐은 닫지 않음)")
            if rtype == "해소":
                rtype = "이어짐"
        elif said_quit and pb["kind"] not in (NEG, "소망", "질문") and not is_question(pb):
            notes.append("그만둔다는 글(다짐 → 그만둠)")
            vow_quit = True
            if rtype == "해소":
                rtype = "이어짐"
        elif rtype == "해소" and pa["kind"] == "다짐":
            notes.append("해소→이어짐(다짐은 풀리는 것이 아니라 지켜지는 것)")
            rtype, vow_kept = "이어짐", True
        elif later and pb["kind"] == POS and rtype in ("이어짐", "바뀜"):
            notes.append(f"{rtype}→이어짐(열린 다짐 뒤 같은 주제의 자기평가(긍정) = 다짐이 지켜짐)")
            rtype, vow_kept = "이어짐", True
        if pa["kind"] == "다짐" and pb["kind"] == NEG and same_topic and _open(states, pa["id"]) and rtype != "어긋남":
            notes.append(f"{rtype}→어긋남(열린 다짐 뒤 같은 주제의 반성)")
            rtype = "어긋남"
        if (is_question(pa) and pb["kind"] in ("신념·원칙", "해석") and pb.get("certainty") == "단정" and same_topic
                and rtype in ("바뀜", "이어짐")):
            notes.append(f"{rtype}→해소(열린 질문이 같은 주제의 단정으로 정리됨)")
            rtype = "해소"
        # 금지
        if rtype in ("바뀜", "해소") and pa["kind"] == pb["kind"] == EMOTION:
            drop(f"감정끼리는 {rtype}이 아님")
            continue
        if rtype == "해소" and pb.get("certainty") != "단정":
            drop("해소인데 새 생각이 단정이 아님")
            continue
        if rtype == "어긋남" and not (pa["kind"] == "다짐" and pb["kind"] == NEG and _open(states, pa["id"])):
            drop("어긋남은 열린 다짐 뒤의 반성만")
            continue
        if rtype == "목표 충돌" and not (pa["kind"] == pb["kind"] == "다짐"
                                       and _open(states, pa["id"]) and _open(states, pb["id"])):
            drop("목표 충돌은 둘 다 열린 다짐만")
            continue
        group = REL[rtype]["group"]
        if group == "판단형" and not same_topic:
            drop(f"판단형({rtype})인데 다른 주제")
            continue
        # 선: 관측 Agent가 '작성자가 직접 씀' + 기록 Agent도 새 생각에서 스스로 쓴 변화를 뽑았을 때만 실선
        line = "실선" if _yes(c.get("author_stated")) and pb.get("self_change") else "점선"
        # 설명은 G3 · 내부 번호를 거른 뒤의 글로 판정하고 보여 준다(사람 판정 · 진단 문장만이었으면 빈 설명)
        explanation = clean_text(c.get("explanation"), " ".join(f"{t.get('quote', '')} {t.get('thought', '')}" for t in (pa, pb)))
        cross = bool(pa.get("domain") and pb.get("domain") and pa["domain"] != pb["domain"])
        if cross:
            if group not in O["cross_domain"]["allowed_groups"]:
                drop(f"{group}은 영역을 넘지 않음")
                continue
            quoted = _yes(c.get("quoted"))
            if pa["record_id"] == pb["record_id"]:
                text = f"{pb.get('quote', '')} {pb.get('thought', '')}"
                if not (quoted and any(w in text for w in FLOW)):
                    drop("영역 넘는 같은 글 관계인데 이어 쓴 흐름 · 원문 인용이 없음")
                    continue
                line = "실선"
            else:
                if not (quoted and explanation):
                    drop("영역 넘는 다른 날 관계인데 원문 설명이 없음")
                    continue
                line = "점선"
        kept.append({
            "id": f"{pa['id']}>{pb['id']}", "type": rtype, "group": group, "color": REL[rtype]["color"],
            "from": pa["id"], "to": pb["id"], "from_record": pa["record_id"], "to_record": pb["record_id"],
            "topic": (c.get("topic") or pb.get("topic") or "").strip(), "line": line,
            # 점선 = AI 추정 → 사용자 확인(맞아요 → 실선 / 아니에요 → 지움, v8.json line_styles). 영역 안 점선도 같다.
            "cross_domain": cross, "needs_confirm": line == "점선", "vow_kept": vow_kept, "vow_quit": vow_quit,
            "explanation": explanation,
            "axis": (c.get("axis") or "").strip(),
            "notes": notes,
        })
    # 같은 두 생각 사이에는 하나만: 우선순위 앞의 것
    best = {}
    for k in kept:
        if k["id"] not in best or PRIORITY.index(k["type"]) < PRIORITY.index(best[k["id"]]["type"]):
            best[k["id"]] = k
    for k in kept:
        if best[k["id"]] is not k:
            dropped.append({"cand": k, "reason": f"같은 두 생각 사이 관계는 하나({best[k['id']]['type']} 우선)"})
    return [k for k in kept if best[k["id"]] is k], dropped
