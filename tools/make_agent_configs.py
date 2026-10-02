"""Generate Studio import files for 기록 Agent and 관측 Agent (agent_configs/*.json).

Studio's export format (kind: studio.agent-config-draft). After importing and tuning in Studio,
replace these with the files exported from Studio.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "agent_configs"

PARSE = {
    "modelName": "document-parse", "mode": "standard", "ocrMode": "auto", "lang": "",
    "outputFormats": ["html", "text"], "chartRecognition": False, "coordinates": False,
    "base64Encoding": [], "mergeMultipageTables": False,
}


def arr(desc, item_type="string"):
    # Studio returns every field as a list; single values are lists of one.
    return {"type": "array", "items": {"type": item_type, "description": desc}, "description": ""}


def table(desc, fields):
    return {"type": "array", "description": desc,
            "items": {"type": "object", "properties": {k: {"type": "string", "description": d} for k, d in fields.items()}}}


def classify(categories):
    return {"modelName": "", "schema": {"type": "json_schema", "json_schema": {
        "name": "document-classify",
        "schema": {"type": "string", "oneOf": [{"const": c, "description": d} for c, d in categories]}}}}


def extract_branches(categories, props, prefix):
    names = {c: f"{prefix}_{i + 1}" for i, (c, _) in enumerate(categories)}
    schemas = [{"type": "json_schema", "json_schema": {"name": names[c], "schema": {"type": "object", "properties": props}},
                "mode": "standard", "modelName": "", "nodeMode": "extract"} for c, _ in categories]
    edges = [{"id": "e0", "source": {"nodeType": "parse"}, "target": {"nodeType": "classify", "name": "Classify-1"}}]
    edges += [{"id": f"e{i + 1}", "source": {"nodeType": "classify", "name": "Classify-1"},
               "target": {"nodeType": "extract", "name": names[c]}, "condition": {"conditionName": c}}
              for i, (c, _) in enumerate(categories)]
    ie = {"modelName": "", "schemas": schemas, "categorySchemaMapping": names, "location": False}
    return ie, edges


def agent(name, categories, props, prefix):
    ie, edges = extract_branches(categories, props, prefix)
    return {"kind": "studio.agent-config-draft", "exportedAt": datetime.now(timezone.utc).isoformat(),
            "agentConfig": {"agent_name": name, "pipelineType": "classify-extract",
                            "documentParseConfiguration": PARSE,
                            "documentClassifyConfiguration": classify(categories),
                            "informationExtractConfiguration": ie, "pipelineEdges": edges}}


# ---------------- 기록 Agent ----------------
RECORD_TYPES = [
    ("경험 기록", "있었던 일과 일정을 주로 적은 글. 사건·장소·사람 위주이고, 생각이나 판단은 거의 없다."),
    ("생각·성찰", "생각, 깨달음, 신념, 질문, 다짐, 반성, 감정을 다루는 글. 말씀·책 묵상과 기도, 회고도 여기에 들어간다. 경험이 함께 있어도 생각을 다루는 부분이 있으면 이 유형이다."),
    ("창작", "시, 노래 가사, 짧은 소설처럼 비유와 형식을 갖춘 창작물이 중심인 글."),
    ("기타", "공지, 부탁, 한 줄 글, 사진 설명처럼 위 셋에 들지 않는 글."),
]
THOUGHT_KIND = ("생각의 종류. 다음 중 하나만: 해석 / 신념·원칙 / 질문 / 다짐 / 반성 / 감정. "
                "해석=무언가의 의미를 읽어 냄. 신념·원칙=일반적인 주장을 세움. 질문=답을 못 낸 물음. "
                "다짐=앞으로 하겠다는 약속. 반성=기준에 비춰 나를 평가함('~하지 못했다', '~했어야 했는데'). "
                "감정=평가 없이 마음 상태만 드러냄('무겁다', '기쁘다').")
RECORD_PROPS = {
    "summary": arr("글 전체를 1~2문장으로 요약. 사람을 평가하거나 단정하지 않는다."),
    "period": arr("글이 다루는 기간. 다음 중 하나: 하루 / 요즘 / 기간 회고"),
    "triggers": arr("생각을 부른 계기. 각 항목은 다음 중 하나: 경험 / 대화 / 읽은 글 / 콘텐츠 / 뉴스·사건"),
    "addressee": arr("글이 말을 거는 대상. 다음 중 하나: 나 / 독자 / 특정 인물 / 신"),
    "roles": arr("글에 등장한 사람의 관계나 역할(예: 선배, 친구, 가족, 팀원, 리더). 실명은 절대 쓰지 않는다."),
    "references": arr("인용하거나 참고한 것의 주소나 제목(예: 성경 구절 주소, 책·노래·영화 제목). 인용 본문은 쓰지 않는다."),
    "events": arr("있었던 일을 짧은 구절로. 생각이 아니라 사실만."),
    "thoughts": table(
        "글쓴이가 직접 적은 생각을 하나씩 나눈 목록. 인용한 구절이나 남의 말은 생각으로 만들지 않는다. 사건만 있고 생각이 없으면 비워 둔다.",
        {
            "topic": "삶의 영역 수준의 짧은 명사 하나(예: 진로, 관계, 건강, 배움, 신앙, 공동체). 너무 넓은 '삶'이나 너무 좁은 '6시 기상'은 피한다.",
            "thought": "원문에 가까운 한 문장으로 쓴 생각.",
            "kind": THOUGHT_KIND,
            "certainty": "확신 정도. 다음 중 하나: 단정 / 고민 중 / 질문",
            "quote": "이 생각의 근거가 되는 원문 문장. 고치지 말고 원문 그대로 복사한다.",
            "self_change": "글쓴이가 직접 생각이 바뀌었다고 쓴 경우에만 '예전 생각 → 지금 생각' 형식으로. 아니면 빈 문자열.",
            "value": "이 생각이 기대는 가치. 다음 중 하나: 자율 / 도전 / 즐거움 / 성취 / 영향력 / 안정 / 규범 / 전통·신앙 / 배려 / 공익",
        }),
}

# ---------------- 관측 Agent ----------------
OBS_STATES = [
    ("해소", "과거에 맞서던 두 생각(긴장)이나 오래 남은 질문이 오늘 글에서 하나의 결론으로 정리됐다."),
    ("바뀜", "같은 주제에 대한 과거의 신념·원칙·해석과 오늘의 생각이 반대이거나 기준이 달라졌다. 감정이 달라진 것만으로는 바뀜이 아니다."),
    ("긴장", "오늘 글 안에서, 또는 30일 안의 과거 생각과 서로 맞서는 두 생각이 함께 있고 아직 정리되지 않았다."),
    ("어긋남", "과거의 다짐과 오늘의 반성·행동 서술이 어긋나거나(말과 행동의 어긋남), 다른 주제의 두 다짐이 시간·에너지를 다툰다."),
    ("이어짐", "같은 주제의 과거 생각과 같은 방향의 생각이 다시 나왔다."),
    ("처음 쓰는 주제", "비교할 과거 생각이 없거나, 어떤 관계도 원문으로 확인되지 않는다. 다른 상태에 맞지 않으면 이것을 고른다."),
]
OBS_PROPS = {
    "state": arr("관측 상태 하나. 여러 개가 겹치면 해소 > 바뀜 > 긴장 > 어긋남 > 이어짐 > 처음 쓰는 주제 순으로 고른다."),
    "summary": arr("오늘 관측을 2문장 이내로. 사람을 평가하거나 '너는 ~한 사람이다'처럼 단정하지 않는다."),
    "question": arr("글쓴이가 다음에 써 볼 질문 하나. 비교에서 비어 있는 곳을 묻는다."),
    "relations": table(
        "오늘 생각과 과거 생각 사이의 관계 목록. 입력 문서에 있는 생각 ID만 쓴다. 근거가 원문으로 확인되지 않으면 만들지 않는다.",
        {
            "type": "다음 중 하나: 이어짐 / 바뀜 / 긴장 / 해소 / 어긋남 / 목표 충돌. 감정끼리 달라진 것은 바뀜으로 쓰지 않는다.",
            "today_id": "오늘 생각의 ID(예: T1).",
            "past_id": "과거 생각의 ID(예: P3). 같은 글 안의 긴장이면 오늘 생각 ID.",
            "topic": "두 생각이 함께 속한 주제.",
            "explanation": "관계를 한 문장으로. 두 생각의 차이나 공통점을 사실대로.",
            "author_stated": "글쓴이가 직접 변화나 정리를 썼으면 '예', 아니면 '아니오'.",
            "axis": "긴장이나 바뀜이면 두 생각이 오가는 양 끝의 이름(예: 혼자 ↔ 함께). 아니면 빈 문자열.",
        }),
}

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for fname, cfg in (("Record Agent.json", agent("나의 우주 기록 Agent", RECORD_TYPES, RECORD_PROPS, "Extract_Record")),
                       ("Observe Agent.json", agent("나의 우주 관측 Agent", OBS_STATES, OBS_PROPS, "Extract_Observe"))):
        (OUT / fname).write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print("wrote", OUT / fname)
