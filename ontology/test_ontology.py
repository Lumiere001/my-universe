"""v8.json 자기 점검. 목록을 고치면 여기서 개수 · 참조 · 금지 숫자가 어긋나지 않는지 본다."""
import json
import re

import pytest

from ontology import choices, is_valid, load

O = load()

REQUIRED = ["about", "version", "source", "objects", "record_fields", "thought_fields", "kinds", "certainty",
            "certainty_rules", "values", "value_rules", "domains", "domain_rules", "topic_rules", "line_styles",
            "relations", "relation_rules", "cross_domain", "states", "state_buttons", "out_of_list_rule",
            "past_selection", "people", "aspiration", "weather", "weather_rules", "tones", "fact_bomb",
            "tone_rules", "addressee_handling", "feedback", "universe_symbols", "ops", "crisis", "limits"]


def test_required_keys():
    assert [k for k in REQUIRED if k not in O] == []


@pytest.mark.parametrize("name,n", [("objects", 7), ("record_fields", 3), ("thought_fields", 8), ("kinds", 9),
                                    ("certainty", 3), ("values", 10), ("domains", 9), ("weather", 6), ("tones", 4),
                                    ("relations", 6)])
def test_counts(name, n):
    assert len(O[name]) == n


def test_names_match_plan():
    assert choices("objects") == ["기록", "생각", "세부 주제", "삶의 영역", "관계", "사람", "되고 싶은 모습"]
    assert [f["key"] for f in O["record_fields"]] == ["summary", "addressee", "events"]
    assert [f["key"] for f in O["thought_fields"]] == ["thought", "kind", "certainty", "value", "quote",
                                                       "self_change", "topic", "people"]
    assert choices("certainty") == ["단정", "고민 중", "판단 보류"]
    assert choices("addressee") == ["나", "특정 인물", "신"]
    assert choices("tones") == ["다정하게", "담백하게", "고양이처럼", "팩폭"]
    assert choices("weather") == ["맑음", "구름 조금", "흐림", "비", "천둥", "안개"]


def _lists():
    """보기 목록(이름 있는 dict 목록) 전부."""
    for k, v in O.items():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "name" in v[0]:
            yield k, [x["name"] for x in v]
    for f in O["record_fields"]:
        if "choices" in f:
            yield f["key"], [x["name"] for x in f["choices"]]


def test_no_duplicate_names():
    for k, names in _lists():
        assert len(names) == len(set(names)), k


def test_reader():
    assert choices("kind") == choices("kinds")
    assert is_valid("kind", "소망") and not is_valid("kind", "반성")
    assert is_valid("value", "배려") and not is_valid("value", "성장")
    assert load() is load()                      # 캐시
    with pytest.raises(KeyError):
        choices("limits")


def test_relations_group_and_lines():
    lines = set(choices("line_styles"))
    assert lines == {"실선", "점선"}
    for r in O["relations"]:
        assert r["group"] in O["relation_groups"], r["name"]
        assert r["lines"] and set(r["lines"]) <= lines, r["name"]
    judge = {r["name"] for r in O["relations"] if r["group"] == "판단형"}
    assert judge == {"바뀜", "해소", "어긋남"}
    assert sorted(O["relation_priority"]) == sorted(choices("relations"))
    assert O["cross_domain"]["allowed_groups"] == ["영향형"]


def test_state_transitions_target_defined():
    for subject, s in O["states"].items():
        for t in s["transitions"]:
            assert t["to"] in s["states"], (subject, t)
            assert t["from"] is None or t["from"] in s["states"], (subject, t)
        assert s.get("initial") in (None, *s["states"])
    for b in O["state_buttons"]:
        assert b["to"] in O["states"][b["target"]]["states"], b
        assert b["name"] in choices("feedback")


def test_example_values_in_lists():
    kinds, values, domains = set(choices("kinds")), set(choices("values")), set(choices("domains"))
    n = 0
    for k in O["kinds"]:
        assert 1 <= len(k["examples"]) <= 2, k["name"]
        for ex in k["examples"]:
            n += 1
            assert ex.get("kind", k["name"]) in kinds
            assert ex.get("value", "") in values | {""}, ex
            assert ex.get("domain", "삶의 성취") in domains, ex
            assert ex.get("flag", "감사") in k.get("flags", ["감사"])
    for side in ("a", "b"):
        ex = O["cross_domain"]["example"][side]
        assert ex["kind"] in kinds and ex["domain"] in domains
    assert O["cross_domain"]["example"]["relation"] in choices("relations")
    assert O["aspiration"]["example"]["value"] in values
    assert n >= 9


def test_no_baseless_numbers():
    text = json.dumps(O, ensure_ascii=False)
    assert not re.search(r"(?<!\d)(7|14|30)일", text)
    for s in ("0.75", "0.35", "0.15", "0.05"):
        assert s not in text


def test_crisis_resources():
    text = json.dumps(O["crisis"], ensure_ascii=False)
    assert "109" in text and "마들랜" in text
    assert "24시간" in text


def test_limits_are_numbers_only():
    for k, v in O["limits"].items():
        assert k == "note" or isinstance(v, (int, float)), k


def test_values_and_weather_detail():
    assert all(v["definition"] and v["schwartz"] for v in O["values"])
    assert {w["name"] for w in O["weather"] if w.get("comfort_only")} == {"비", "천둥"}
    assert len(O["fact_bomb"]["never_cross"]) == 4
    assert len(O["aspiration"]["ask_steps"]) == 4
    assert [d["name"] for d in O["aspiration"]["declines"]] == ["이번엔 넘어가기", "그만 묻기"]
    assert len(O["people"]["ask_when"]) == 3

