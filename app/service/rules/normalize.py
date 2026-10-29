"""
목록 밖 값(out_of_list_rule)과 기록 Agent 출력 한 편을 v8 형태로 바로잡기.

뜻이 하나면 바로잡고, 애매하면 "기타" + 원래 말. 자주 나오는 원래 말은 새 값 후보로 세어 사람이 정한다.
"""

import re
from collections import Counter

from app.core.ontology import choices, load

O = load()
FIELD = {"kind": "kinds", "kinds": "kinds", "certainty": "certainty", "value": "values", "values": "values",
         "type": "record_types", "record_type": "record_types", "record_types": "record_types",
         "addressee": "addressee"}
OTHER = "기타"

# 비슷한 말 표: 뜻이 하나로 정해지는 말만. 애매한 말(성장 · 깨달음 · 고민 …)은 넣지 않는다 → 기타 + 원래 말.
SYNONYMS = {
    "kinds": {"반성": "자기평가(부정)", "자책": "자기평가(부정)", "칭찬": "자기평가(긍정)", "자기인정": "자기평가(긍정)",
              "감사": "감정", "고마움": "감정", "신념": "신념·원칙", "원칙": "신념·원칙", "결심": "다짐", "약속": "다짐",
              "바람": "소망", "소원": "소망", "의문": "질문", "물음": "질문"},
    "certainty": {"확실함": "단정", "확실": "단정", "확신": "단정", "결론": "단정", "모르겠음": "판단 보류", "모름": "판단 보류",
                  "미정": "판단 보류", "보류": "판단 보류", "질문": "판단 보류", "고민": "고민 중", "흔들림": "고민 중"},
    "values": {"자기주도": "자율", "독립": "자율", "자극": "도전", "모험": "도전", "쾌락": "즐거움", "권력": "영향력",
               "안전": "안정", "순응": "규범", "전통": "전통·신앙", "신앙": "전통·신앙", "자비": "배려", "선행": "배려",
               "보편주의": "공익", "정의": "공익"},
    "record_types": {"경험": "경험 기록", "일상": "경험 기록", "성찰": "생각·성찰", "생각": "생각·성찰", "시": "창작"},
    "addressee": {"자신": "나", "나자신": "나", "본인": "나", "없음": "나", "하나님": "신", "하느님": "신", "주님": "신",
                  "예수님": "신", "편지": "특정 인물", "타인": "특정 인물"},
}
# 강조어만으로 단정을 매기지 않는다(certainty_rules). 강조어가 있는데 아래 말이 있으면 단정이 아니다.
EMPHASIS = ("정말", "진짜", "확실히", "너무", "완전", "엄청", "진심으로")
UNDECIDED = ("모르겠", "?", "일까", "할까", "는지 모르")
LEANING = ("것 같", "않을까", "듯하", "듯 하")
NEG, EMOTION = "자기평가(부정)", "감정"
THANKS = O["kinds"][[k["name"] for k in O["kinds"]].index(EMOTION)]["flags"][0]   # "감사"


def key(s):
    """띄어쓰기 · 가운뎃점 · 괄호를 빼고 비교한다."""
    return re.sub(r"[\s·・ㆍ/()\-_.,]", "", s or "")


def _first(raw):
    if isinstance(raw, list):   # Studio는 단일 값도 배열로 준다
        raw = raw[0] if raw else ""
    return str(raw or "").strip()


def _table(name):
    t = {key(s).lower(): v for s, v in SYNONYMS.get(name, {}).items()}
    for item in O.get(name, []) if isinstance(O.get(name), list) else []:
        for alias in (item.get("display"), item.get("schwartz")):   # 화면 이름(아쉬웠던 점) · Schwartz 이름
            if alias:
                t[key(alias).lower()] = item["name"]
    return t


def normalize(field, raw):
    """(값, 원래 말 또는 None). 목록 안 값 · 비슷한 말은 바로잡고, 애매하면 ("기타", 원래 말). 가치는 빈칸 허용."""
    name = FIELD.get(field, field)
    if name not in O["out_of_list_rule"]["applies_to"]:
        raise KeyError(f"목록 밖 값 규칙 대상이 아님: {field}")
    s = _first(raw)
    if not s:
        return ("", None) if name == "values" else (OTHER, "")
    k = key(s)
    for c in choices(name):
        if key(c) == k:
            return c, None
    hit = _table(name).get(k.lower())
    return (hit, None) if hit else (OTHER, s)


def other_candidates(items):
    """정리한 생각 · 기록들의 original({칸: 원래 말})을 세어 새 값 후보를 많은 순으로. 정하는 것은 사람."""
    c = Counter((f, w) for it in items for f, w in (it.get("original") or {}).items()
                if w and f != "topic")   # topic = 작은 별에 맞추기 전 기록 Agent 가 낸 이름(목록 밖 값이 아님)
    return [{"field": f, "original": w, "count": n} for (f, w), n in sorted(c.items(), key=lambda x: (-x[1], x[0]))]


def no_emphasis(certainty, text):
    """강조어로 매긴 단정을 문장 뜻으로 되돌린다: 미정 표현 → 판단 보류, 기운 표현 → 고민 중."""
    if certainty != "단정" or not any(w in text for w in EMPHASIS):
        return certainty
    if any(w in text for w in UNDECIDED):
        return "판단 보류"
    if any(w in text for w in LEANING):
        return "고민 중"
    return certainty


def people_of(raw, people=()):
    """사람 칸을 이름 목록으로. 별명은 사람 목록의 이름으로 바꾼다. (이름들, 새 이름들)"""
    if isinstance(raw, str):
        raw = re.split(r"[,、·]", raw)
    alias = {}
    for p in people or ():
        for n in [p["name"], *(p.get("nicknames") or [])]:
            alias[key(n)] = p["name"]
    names, new = [], []
    for w in raw or []:
        w = str(w).strip()
        if not w:
            continue
        n = alias.get(key(w), w)
        if n not in names:
            names.append(n)
        if key(w) not in alias and n not in new:
            new.append(n)
    return names, new


def clean_record(raw, people=(), topics=None, suns=(), aliases=None):
    """기록 Agent 출력 한 편 → v8 형태.
    raw: {summary, addressee, (addressee_original), (record_type), events,
          thoughts: [{thought, kind, certainty, value, quote, self_change, topic, people}]}
    people: 사용자 사람 목록 [{name, nicknames, relation}], topics: 기존 작은 별 {이름: 해}, suns: 사용자가 추가한 해 이름.
    돌려줌: {summary, addressee, record_type, events, original, thoughts: [...], new_people}.
    original = 목록 밖 원래 말 {addressee, record_type}. 생각마다 flags(감사) · problems(해 이름) · original.
    record_type 은 Classify 결과가 없으면 None.
    """
    from app.service.rules.topics import link_domain, match_topic, one_topic
    topics = topics or {}
    addressee, a_orig = normalize("addressee", raw.get("addressee_original") or raw.get("addressee"))
    rtype, r_orig = normalize("record_type", raw["record_type"]) if _first(raw.get("record_type")) else (None, None)
    out = {"summary": _first(raw.get("summary")), "addressee": addressee, "record_type": rtype,
           "events": [e for e in (raw.get("events") or []) if str(e).strip()],
           "original": {k: v for k, v in {"addressee": a_orig, "record_type": r_orig}.items() if v},
           "thoughts": [], "new_people": []}
    for t in raw.get("thoughts") or []:
        text = f"{_first(t.get('thought'))} {_first(t.get('quote'))}"
        orig, row = {}, {}
        for f in ("kind", "certainty", "value"):
            row[f], o = normalize(f, t.get(f))
            if o:
                orig[f] = o
        flags = []
        if row["kind"] == EMOTION and (key(_first(t.get("kind"))) in ("감사", "고마움") or re.search("고마|감사", text)):
            flags.append(THANKS)
        topic, problem = match_topic(one_topic(_first(t.get("topic")), text), topics, suns, aliases)
        names, new = people_of(t.get("people"), people)
        out["new_people"] += [n for n in new if n not in out["new_people"]]
        out["thoughts"].append({
            "thought": _first(t.get("thought")), "kind": row["kind"],
            "certainty": no_emphasis(row["certainty"], text), "value": row["value"],
            "quote": _first(t.get("quote")), "self_change": _first(t.get("self_change")),
            "topic": topic, "domain": topics.get(topic) or link_domain(topic, suns=suns),
            "people": names, "flags": flags, "problems": [problem] if problem else [], "original": orig,
        })
    return out
