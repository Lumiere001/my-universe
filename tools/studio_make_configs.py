"""Studio 기록 · 관측 Agent 설정을 v8 온톨로지에서 만든다 → agent_configs/* v2 · v3 · v3b.json

    uv run --frozen python tools/studio_make_configs.py

2판: 1판 파일(Studio 가 내보낸 모양, studio.workflow-config-draft)을 틀로 쓰고
Classify 갈래 · Extract 칸 설명만 v8.json 에서 다시 채운다. 목록 · 정의는 여기 적지 않는다.
3판(품질 3판, 2026-10-14 동규 '전부 추천대로'): Studio 가 내보낸 #2(`* v2.exported.json`, schemaVersion 4)를 틀로
2판 설명에 규칙 셋(① 시 · 창작 글에는 관계를 잇지 않기 ② 사건 서술은 생각에 넣지 않기 ③ 가치 이름을 주제로 쓰지 않기)을 더한다.
v3 = 모델 칸 비움(Studio 기본 전용 모델, 2판과 같음), v3b = v3 + Classify · Extract 모델 solar-pro4.
"""
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.core.ontology import load  # noqa: E402

OUT = ROOT / "agent_configs"
O = load()


def _list(items, key="definition"):
    return " ".join(f"{x['name']}={x[key]}" for x in items)


def _field(fields, key):
    return next(f for f in fields if f["key"] == key)


def arr(desc):
    # Studio 는 모든 칸을 목록으로 돌려준다. 값 하나도 길이 1 목록.
    return {"type": "array", "items": {"type": "string", "description": desc}, "description": ""}


def table(desc, fields):
    return {"type": "array", "description": desc,
            "items": {"type": "object", "properties": {k: {"type": "string", "description": d} for k, d in fields.items()}}}


OUT_OF_LIST = ("목록에 없는 값은 쓰지 않는다. 뜻이 하나로 정해지면 목록의 값으로 바로잡고, "
               "애매하면 '기타(원래 말)'로 쓴다(예: 기타(성장)).")

# ---------------- 기록 Agent ----------------
RF, TF = O["record_fields"], O["thought_fields"]
addressee = _field(RF, "addressee")
domain_names = " / ".join(d["name"] for d in O["domains"])
kinds = " ".join(f"{k['name']}={k['definition']} 경계: {k['boundary']}" for k in O["kinds"])

RECORD_TYPES = [(t["name"], t["definition"]) for t in O["record_types"]]
RECORD_PROPS = {
    "summary": arr(_field(RF, "summary")["definition"]),
    "addressee": arr(f"{addressee['definition']} 다음 중 하나: {_list(addressee['choices'])}"),
    "events": arr(_field(RF, "events")["definition"] + " 짧은 구절 하나씩."),
    "thoughts": table(
        "글쓴이가 직접 적은 생각을 하나씩 나눈 목록. 인용한 구절이나 남의 말은 생각으로 만들지 않는다. "
        "'참고: 기존 작은 별' 절은 일기 내용이 아니므로 생각으로 만들지 않는다. 사건만 있고 생각이 없으면 비워 둔다.",
        {
            "thought": _field(TF, "thought")["definition"],
            "kind": (f"생각의 종류. 다음 중 하나만: {kinds} 고마움을 드러낸 감정이면 '감정(감사)'로 쓴다. " + OUT_OF_LIST),
            "certainty": (f"{_field(TF, 'certainty')['definition']} 다음 중 하나: {_list(O['certainty'])} "
                          + " ".join(O["certainty_rules"]) + " " + OUT_OF_LIST),
            "value": (f"{_field(TF, 'value')['definition']} 다음 중 하나: "
                      + " ".join(f"{v['name']}={v['definition']}" for v in O["values"])
                      + " " + " ".join(O["value_rules"][:1]) + " " + OUT_OF_LIST),
            "quote": _field(TF, "quote")["definition"].replace("(관문 G1이 대조)", "") + " 원문 그대로 복사한다.",
            "self_change": _field(TF, "self_change")["definition"] + " 형식: '예전 생각 → 지금 생각'. 없으면 빈 문자열.",
            "topic": (" ".join(O["topic_rules"][:4]) + f" 해 이름(쓰지 않는다): {domain_names}. "
                      "입력의 '참고: 기존 작은 별' 목록에 뜻이 맞는 이름이 있으면 글자 그대로 다시 쓴다."),
            "people": ("이 생각에 나오는 사람을 글에 쓰인 이름 · 호칭 그대로(예: 사람1, 엄마). "
                       "여러 명이면 쉼표로 나눈다. 없으면 빈 문자열. 사람을 평가하지 않는다."),
        }),
}

# ---------------- 관측 Agent ----------------
REL = {r["name"]: r for r in O["relations"]}
rel_desc = " ".join(f"{r['name']}({r['group']})={r['definition']} {r['rule']}" for r in O["relations"])
groups = " ".join(f"{k}: {v}" for k, v in O["relation_groups"].items())
reached = O["aspiration"]["reached"]


def _state_desc(name, v1):
    # 관측 상태는 관계 이름과 같다. '처음 쓰는 주제'는 v8.json 에 정의가 없어 1판 설명을 쓴다.
    return REL[name]["definition"] if name in REL else v1[name]


def observe_states():
    v1 = json.loads((OUT / "Observe Agent.json").read_text(encoding="utf-8"))
    one_of = v1["workflowConfig"]["documentClassifyConfiguration"]["schema"]["json_schema"]["schema"]["oneOf"]
    v1d = {x["const"]: x["description"] for x in one_of}
    return [(n, _state_desc(n, v1d)) for n in O["observation_states"]["names"]]


OBS_PROPS = {
    "state": arr("관측 상태 하나. 여러 개가 겹치면 " + " > ".join(O["observation_states"]["priority"]) + " 순으로 고른다."),
    "summary": arr("오늘 관측을 2문장 이내로. 사람을 평가하거나 '너는 ~한 사람이다'처럼 단정하지 않는다."),
    "question": arr("글쓴이가 다음에 써 볼 질문 하나. 비교에서 비어 있는 곳을 묻는다."),
    "relations": table(
        "오늘 생각과 과거 생각(또는 오늘 생각끼리) 사이의 관계 목록. 입력 문서에 있는 생각 ID만 쓴다. "
        "두 생각이 같은 대상(같은 일 · 같은 사람 · 같은 결정)을 직접 말할 때만 관계를 만든다. "
        "분위기나 낱말이 비슷한 것만으로는 잇지 않는다. 근거가 원문으로 확인되지 않으면 만들지 않는다. "
        + " ".join(O["relation_rules"][:3]),
        {
            "type": f"다음 중 하나: {rel_desc} {groups}",
            "today_id": "오늘 생각의 ID(예: T1).",
            "past_id": "과거 생각의 ID(예: P3). 같은 글 안의 관계면 다른 오늘 생각 ID(예: T2).",
            "same_target": "두 생각이 함께 직접 말하는 대상을 짧은 말로(예: 아침 운동, 진로 결정). 이것을 못 쓰면 관계를 만들지 않는다.",
            "topic": "두 생각이 함께 속한 세부 주제(입력에 적힌 주제 이름).",
            "evidence": ("두 생각을 잇는 근거. 입력의 원문 인용을 글자 그대로 옮긴다. 해(영역)가 다른 두 생각이면: "
                         + O["cross_domain"]["same_record"] + " " + O["cross_domain"]["other_day"]),
            "explanation": "관계를 한 문장으로. 두 생각의 차이나 공통점을 사실대로. 사람을 단정하지 않는다.",
            "author_stated": "글쓴이가 직접 변화나 정리를 썼으면 '예', 아니면 '아니오'.",
            "axis": "긴장이나 바뀜이면 두 생각이 오가는 양 끝의 이름(예: 혼자 ↔ 함께). 아니면 빈 문자열.",
        }),
    "reached": table(
        "입력의 '되고 싶은 모습'에 오늘 생각이 닿은 순간. " + " ".join(reached[:2])
        + " 되고 싶은 모습이 없거나 원문 근거가 없으면 비워 둔다.",
        {
            "thought_id": "닿은 오늘 생각의 ID(예: T1).",
            "quote": "닿았다는 근거가 되는 원문 인용을 글자 그대로.",
            "note": "무엇이 되고 싶은 모습에 닿았는지 한 문장. 거리 · 점수 · 달성률은 쓰지 않는다.",
        }),
}


def layout(props):
    cols = []
    for k, p in props.items():
        if p["items"]["type"] == "object":
            cols += [{"name": f, "source": "group_table", "groupTableKey": k} for f in p["items"]["properties"]]
        else:
            cols.append({"name": k, "source": "root"})
    return {"version": 1, "columns": cols}


def agent(template, categories, props, prefix, model=""):
    """Studio 가 내보낸 파일을 틀로 갈래 · 칸만 바꾼다. 틀의 설정 번호(configId · configVer)는 지운다(덮어쓰지 않게).
    model: Classify · Extract 단계 모델 이름(빈 문자열 = Studio 기본)."""
    cfg = copy.deepcopy(json.loads((OUT / template).read_text(encoding="utf-8")))
    cfg["exportedAt"] = datetime.now(timezone.utc).isoformat()
    for k in ("configId", "configVer"):
        cfg["exportedFrom"].pop(k, None)
    w = cfg["workflowConfig"]
    w["documentClassifyConfiguration"]["schema"]["json_schema"]["schema"]["oneOf"] = [
        {"const": c, "description": d} for c, d in categories]
    names = {c: f"{prefix}_{i + 1}" for i, (c, _) in enumerate(categories)}
    template = w["informationExtractConfiguration"]["schemas"][0]
    schemas = []
    for c, _ in categories:
        s = copy.deepcopy(template)
        s["json_schema"] = {"name": names[c], "schema": {"type": "object", "properties": props}}
        s["schemaLayout"] = layout(props)
        schemas.append(s)
    w["informationExtractConfiguration"].update(schemas=schemas, categorySchemaMapping=names)
    if model:
        for c in [w["documentClassifyConfiguration"], w["informationExtractConfiguration"], *schemas]:
            c["modelName"] = model
    edges = [e for e in w["pipelineEdges"] if e["source"]["nodeType"] == "parse"]
    edges += [{"id": f"e{i + 1}", "source": {"nodeType": "classify", "name": "Classify-1"},
               "target": {"nodeType": "extract", "name": names[c]}, "condition": {"conditionName": c}}
              for i, (c, _) in enumerate(categories)]
    w["pipelineEdges"] = edges
    return cfg


# ---------------- 3판: 2판 + 규칙 셋 ----------------
V3_CREATIVE = "줄을 나눈 짧은 시 한 편(계절 · 비 · 꽃 · 풍경을 노래한 시)도 창작이다."                       # ①
V3_EVENTS = ("있었던 일만 적은 문장(예: '오늘 시험이 끝났다', '저녁에 친구를 만났다')은 생각이 아니라 사건(events)에 넣는다. "
             "그 일에 대한 해석 · 판단 · 다짐 · 감정이 함께 적혀 있을 때만 생각으로 만든다.")                     # ②
V3_VALUES = f"가치 이름(쓰지 않는다): {' / '.join(v['name'] for v in O['values'])}."                          # ③
V3_NO_LINK = "'글 유형: 창작'이 붙은 생각(시 · 가사 · 소설)은 어떤 생각과도 잇지 않는다(비유는 글쓴이의 생각이 아니다)."   # ①


def _add(props, path, text):
    """props 의 한 칸 설명 끝에 text 를 붙인 새 props. path: ('thoughts',) 는 표 설명, ('thoughts', 'topic') 은 표 안 칸."""
    props = copy.deepcopy(props)
    node = props[path[0]]
    node = node["items"]["properties"][path[1]] if len(path) > 1 else node
    node["description"] += " " + text
    return props


RECORD_TYPES_V3 = [(n, f"{d} {V3_CREATIVE}" if n == "창작" else d) for n, d in RECORD_TYPES]
RECORD_PROPS_V3 = _add(_add(RECORD_PROPS, ("thoughts",), V3_EVENTS), ("thoughts", "topic"), V3_VALUES)
OBS_PROPS_V3 = _add(OBS_PROPS, ("relations",), V3_NO_LINK)


def build():
    out = {"Record Agent v2.json": agent("Record Agent.json", RECORD_TYPES, RECORD_PROPS, "Extract_Record"),
           "Observe Agent v2.json": agent("Observe Agent.json", observe_states(), OBS_PROPS, "Extract_Observe")}
    for v, model in (("v3", ""), ("v3b", "solar-pro4")):
        out[f"Record Agent {v}.json"] = agent("Record Agent v2.exported.json", RECORD_TYPES_V3, RECORD_PROPS_V3,
                                              "Extract_Record", model)
        out[f"Observe Agent {v}.json"] = agent("Observe Agent v2.exported.json", observe_states(), OBS_PROPS_V3,
                                               "Extract_Observe", model)
    return out


if __name__ == "__main__":
    for fname, cfg in build().items():
        (OUT / fname).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", OUT / fname)
