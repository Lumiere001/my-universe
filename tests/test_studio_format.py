"""WS2: Studio 설정 2판(agent_configs/* v2.json)과 입출력 형식(app/service/studio_format.py) 점검."""
import json
from pathlib import Path

from app.core.ontology import choices, load
from app.service import studio_format as sf

ROOT = Path(__file__).resolve().parents[1]


def _cfg(name):
    return json.loads((ROOT / "agent_configs" / name).read_text(encoding="utf-8"))


def _props(cfg):
    return cfg["workflowConfig"]["informationExtractConfiguration"]["schemas"][0]["json_schema"]["schema"]["properties"]


# ---------------- 설정 파일 ----------------

def test_v2_files_match_generator():
    # 파일을 손으로 고치지 않았는지: 생성기 결과와 같아야 한다(내보낸 시각만 다름)
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "studio_make_configs.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    for fname, cfg in gen.build().items():
        saved = _cfg(fname)
        saved.pop("exportedAt"), cfg.pop("exportedAt")
        assert saved == cfg, fname


def test_v2_keeps_v1_shape_and_drops_config_number():
    for v1, v2 in (("Record Agent.json", "Record Agent v2.json"), ("Observe Agent.json", "Observe Agent v2.json")):
        a, b = _cfg(v1), _cfg(v2)
        assert a["kind"] == b["kind"] and a["schemaVersion"] == b["schemaVersion"]
        assert set(a["workflowConfig"]) == set(b["workflowConfig"])
        assert b["exportedFrom"]["workflowId"] == a["exportedFrom"]["workflowId"]
        assert "configId" not in b["exportedFrom"]   # 1판 번호를 덮어쓰지 않게
        w = b["workflowConfig"]
        cats = [x["const"] for x in w["documentClassifyConfiguration"]["schema"]["json_schema"]["schema"]["oneOf"]]
        names = w["informationExtractConfiguration"]["categorySchemaMapping"]
        assert set(names) == set(cats) and len(w["pipelineEdges"]) == len(cats) + 1
        cols = [c["name"] for c in w["informationExtractConfiguration"]["schemas"][0]["schemaLayout"]["columns"]]
        assert len(cols) == len(set(cols))


def _keys(o, path=""):
    """키 구조(값 · 설명 글은 빼고)."""
    if isinstance(o, dict):
        return {f"{path}.{k}" for k in o} | {x for k, v in o.items() for x in _keys(v, f"{path}.{k}")}
    if isinstance(o, list):
        return {x for v in o for x in _keys(v, f"{path}[]")}
    return set()


def test_v3_follows_exported_v2_shape_and_adds_rules():
    """품질 3판: Studio 가 내보낸 #2 와 키 구조가 같고(설정 번호만 없음) 규칙 ① ② ③ 이 설명에 들어감. v3b 는 모델만 다름."""
    for agent in ("Record", "Observe"):
        ex = _cfg(f"{agent} Agent v2.exported.json")
        ex["exportedFrom"].pop("configId"), ex["exportedFrom"].pop("configVer")
        for v, model in (("v3", ""), ("v3b", "solar-pro4")):
            c = _cfg(f"{agent} Agent {v}.json")
            assert (c["kind"], c["schemaVersion"]) == (ex["kind"], ex["schemaVersion"]) and _keys(c) == _keys(ex), (agent, v)
            w = c["workflowConfig"]
            models = {w["documentClassifyConfiguration"]["modelName"], w["informationExtractConfiguration"]["modelName"],
                      *(x["modelName"] for x in w["informationExtractConfiguration"]["schemas"])}
            assert models == {model} and w["documentParseConfiguration"]["modelName"] == "document-parse"
    rec = _props(_cfg("Record Agent v3.json"))["thoughts"]
    assert "사건(events)에 넣는다" in rec["description"]                                         # ②
    assert all(v["name"] in rec["items"]["properties"]["topic"]["description"] for v in load()["values"])   # ③
    cats = _cfg("Record Agent v3.json")["workflowConfig"]["documentClassifyConfiguration"]["schema"]["json_schema"]["schema"]["oneOf"]
    assert "짧은 시 한 편" in next(x["description"] for x in cats if x["const"] == "창작")         # ①
    assert "글 유형: 창작" in _props(_cfg("Observe Agent v3.json"))["relations"]["description"]     # ①
    assert "글 유형: 창작" in sf.observe_html("d", [{"id": "x", "topic": "봄", "kind": "해석", "certainty": "단정",
                                                    "quote": "q", "record_type": "창작"}], [])[0]


def test_record_v2_fields():
    p = _props(_cfg("Record Agent v2.json"))
    assert set(p) == {"summary", "addressee", "events", "thoughts"}   # 글 정보 3칸 (계기 · 기간 · 참고 · 관계 삭제)
    t = p["thoughts"]["items"]["properties"]
    assert set(t) == {"thought", "kind", "certainty", "value", "quote", "self_change", "topic", "people"}
    for k in choices("kinds"):
        assert k in t["kind"]["description"]
    for k in choices("certainty"):
        assert k in t["certainty"]["description"]
    for v in load()["values"]:
        assert f"{v['name']}={v['definition']}" in t["value"]["description"]   # 뜻풀이까지
    assert "강조어" in t["certainty"]["description"]
    assert "기타(원래 말)" in t["kind"]["description"]
    for d in choices("domains"):
        assert d in t["topic"]["description"]       # 해 이름 금지 목록
    assert "기존 작은 별" in t["topic"]["description"]
    for a in choices("addressee"):
        assert a in p["addressee"]["items"]["description"]


def test_observe_v2_fields():
    p = _props(_cfg("Observe Agent v2.json"))
    assert {"state", "summary", "question", "relations", "reached"} <= set(p)
    r = p["relations"]
    for name in choices("relations"):
        assert name in r["items"]["properties"]["type"]["description"]
    assert "같은 대상" in r["description"]                    # 거짓 별자리 줄이기
    assert "same_target" in r["items"]["properties"] and "evidence" in r["items"]["properties"]
    assert "판단형" in r["items"]["properties"]["type"]["description"]
    assert "멀어진 순간" in p["reached"]["description"]


# ---------------- 입력 HTML ----------------

def test_record_html_escapes_and_lists_known_topics():
    h = sf.record_html("10/3 <토>", "첫 줄\n\n둘째 & 줄", ["진로 결정", "혼자와 함께"])
    assert "&lt;토&gt;" in h and "둘째 &amp; 줄" in h and h.count("<p>") == 2
    assert "참고: 기존 작은 별" in h and "<li>혼자와 함께</li>" in h


def test_record_html_without_known_topics_has_no_reference_section():
    assert "기존 작은 별" not in sf.record_html("t", "본문")


def test_observe_html_ids_and_aspiration():
    today = [{"id": "R2-T1", "topic": "진로 결정", "kind": "다짐", "certainty": "단정", "quote": "메일을 보내겠다", "domain": "삶의 성취"}]
    past = [{"id": "R1-T3", "day": "2026-09-20", "topic": "진로 결정", "kind": "신념·원칙", "certainty": "단정",
             "quote": "배우는 느낌이 중요하다", "self_change": "큰 회사 → 배움"}]
    h, ids = sf.observe_html("2026-10-03", today, past, {"said": "약속을 지키는 사람", "value": "규범"})
    assert ids == {"T1": "R2-T1", "P1": "R1-T3"}
    assert "해: 삶의 성취" in h and "2026-09-20" in h and "스스로 쓴 변화" in h and "약속을 지키는 사람 · 가치: 규범" in h
    h2, _ = sf.observe_html("2026-10-03", today, [], None)
    assert h2.count("<li>없음</li>") == 2   # 과거 없음 · 되고 싶은 모습 없음


# ---------------- 출력 읽기 ----------------

def test_parse_record_first_values_and_people():
    data = {"summary": ["요약 한 줄"], "addressee": ["나"], "events": ["메일 못 보냄", ""],
            "thoughts": [{"thought": "또 미뤘다", "kind": "자기평가(부정)", "certainty": "단정", "value": "",
                          "quote": "바쁘다는 핑계로 또 미뤘다.", "self_change": "", "topic": "진로 결정", "people": "사람1, 엄마"},
                         {"thought": "", "quote": ""}]}
    r = sf.parse_record(data)
    assert r["summary"] == "요약 한 줄" and r["addressee"] == "나" and r["events"] == ["메일 못 보냄"]
    assert len(r["thoughts"]) == 1            # 빈 줄은 버림
    t = r["thoughts"][0]
    assert t["kind"] == "자기평가(부정)"       # 이름에 괄호가 든 정상 값은 그대로
    assert t["people"] == ["사람1", "엄마"] and t["value"] == ""


def test_parse_record_out_of_list_tags():
    t = sf.parse_record({"thoughts": [{"thought": "x", "kind": "기타(맺음말)", "value": "기타(성장)", "certainty": "확실함"}]})["thoughts"][0]
    assert t["kind"] == "기타" and t["kind_original"] == "맺음말"
    assert t["value"] == "기타" and t["value_original"] == "성장"
    assert t["certainty"] == "확실함"          # 뜻 바로잡기는 rules 몫: 여기선 그대로 둔다
    g = sf.parse_record({"thoughts": [{"thought": "x", "kind": "감정(감사)"}]})["thoughts"][0]
    assert g["kind"] == "감정" and g["flags"] == ["감사"]
    bad = sf.parse_record({"thoughts": [{"thought": "x", "kind": "감정(분노)"}]})["thoughts"][0]
    assert bad["kind"] == "감정(분노)" and "flags" not in bad   # 없는 표시는 만들지 않음


def test_parse_observe_maps_ids_and_drops_unknown():
    ids = {"T1": "R2-T1", "T2": "R2-T2", "P1": "R1-T3"}
    data = {"state": ["바뀜"], "summary": ["관측"], "question": ["질문?"],
            "relations": [
                {"type": "바뀜", "today_id": "T1", "past_id": "P1", "same_target": "진로 결정", "author_stated": "예"},
                {"type": "긴장", "today_id": "T1", "past_id": "T2", "author_stated": "아니오"},   # 같은 글 안
                {"type": "이어짐", "today_id": "T1", "past_id": "P9"},                            # 없는 ID
                {"type": "이어짐", "today_id": "T1", "past_id": "T1"}],                           # 자기 자신
            "reached": [{"thought_id": "T2", "quote": "메일을 보냈다"}, {"thought_id": "P1"}]}
    o = sf.parse_observe(data, ids)
    assert o["state"] == "바뀜" and o["question"] == "질문?"
    assert [(r["type"], r["from"], r["to"]) for r in o["relations"]] == [("바뀜", "R1-T3", "R2-T1"), ("긴장", "R2-T2", "R2-T1")]
    assert o["relations"][0]["author_stated"] is True and o["relations"][1]["author_stated"] is False
    assert o["relations"][0]["same_target"] == "진로 결정"
    assert o["reached"] == [{"thought": "R2-T2", "evidence": "메일을 보냈다", "explanation": ""}]   # 지난 생각은 닿은 순간 아님
    assert o["dropped_unknown_id"] == 3


def test_parse_record_strips_quote_marks():
    quotes = ['"또 미뤘다"', "'또 미뤘다'", "“또 미뤘다”", "‘또 미뤘다’", "「또 미뤘다」", " 또 미뤘다 "]
    r = sf.parse_record({"thoughts": [{"thought": "x", "quote": q} for q in quotes]})
    assert [t["quote"] for t in r["thoughts"]] == ["또 미뤘다"] * len(quotes)
    inner = sf.parse_record({"thoughts": [{"thought": "x", "quote": "엄마가 \"괜찮아\"라고 했다"},
                                          {"thought": "x", "quote": "그건 '맞다'"}]})["thoughts"]
    assert [t["quote"] for t in inner] == ["엄마가 \"괜찮아\"라고 했다", "그건 '맞다'"]   # 안쪽 따옴표는 원문 그대로


def test_parse_observe_cleans_evidence_and_author_stated():
    ids = {"T1": "R2-T1", "P1": "R1-T3"}
    rel = lambda **kw: {"type": "이어짐", "today_id": "T1", "past_id": "P1", **kw}   # noqa: E731
    o = sf.parse_observe({"relations": [rel(evidence=["“잠을 줄였다”"], author_stated=["예(직접 씀)"]),
                                        rel(author_stated=True), rel(author_stated=["아니오"]), rel()]}, ids)
    assert o["relations"][0]["evidence"] == "잠을 줄였다"
    assert [r["author_stated"] for r in o["relations"]] == [True, True, False, False]


def test_parse_observe_reached_dedup_and_limit():
    ids = {"T1": "R2-T1", "T2": "R2-T2", "T3": "R2-T3"}
    reached = [{"thought_id": "T1", "quote": "“메일을 보냈다”"}, {"thought_id": "T2", "quote": "메일을  보냈다"},   # 같은 인용
               {"thought_id": "T2", "quote": ""},                                                            # 근거 없음
               {"thought_id": "T2", "quote": "먼저 물어봤다"}, {"thought_id": "T3", "quote": "끝까지 들었다"}]   # 한도 밖
    o = sf.parse_observe({"reached": reached}, ids)
    assert [(r["thought"], r["evidence"]) for r in o["reached"]] == [("R2-T1", "메일을 보냈다"), ("R2-T2", "먼저 물어봤다")]
    assert len(o["reached"]) == sf.REACHED_MAX == 2


def test_parse_observe_empty():
    o = sf.parse_observe({}, {})
    assert o["relations"] == [] and o["reached"] == [] and o["state"] == ""


# ---------------- 비교 실행기(tools/studio_run_v2.py) ----------------

def _runner():
    import importlib.util
    spec = importlib.util.spec_from_file_location("runner", ROOT / "tools" / "studio_run_v2.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_runner_pick_past_same_topic_first_then_recent():
    past = [{"id": "a", "topic": "진로 결정"}, {"id": "b", "topic": "수면"}, {"id": "c", "topic": "진로 결정"}, {"id": "d", "topic": "수면"}]
    got = _runner().pick_past(past, [{"topic": "진로 결정"}], 3)
    assert [p["id"] for p in got] == ["c", "a", "d"]


def test_runner_metrics_counts_domain_name_topics_and_expected_pairs():
    r = _runner()
    e = r.EXPECTED["relations"][0]
    days = {"R1": e["past"], "R2": e["today"], "R3": "2026-01-01"}
    m = r.metrics(days, [{"topic": "관계", "kind": "반성"}, {"topic": "혼자와 함께", "kind": "다짐"}],
                  [{"type": e["type"], "from_record": "R1", "to_record": "R2", "same_target": "x"},
                   {"type": "이어짐", "from_record": "R3", "to_record": "R2", "same_target": ""}])
    assert m["topics_domain_name"] == ["관계"] and m["kinds_out_of_list"] == 1   # 해 이름 주제 · v7 종류 '반성'은 위반
    assert m["expected_type"].startswith("1/") and m["relations_off_design"] == 1 and m["relations_without_same_target"] == 1
