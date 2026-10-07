"""골든셋 파일 형식 검사(WS8). 사례 내용이 맞는지는 eval/run.py 가 잰다."""
import json
import re
from pathlib import Path

import pytest

GOLDEN = Path(__file__).resolve().parents[1] / "eval/golden"
CATEGORIES = ["safety_pseudonym", "crisis", "fact_bomb", "voice_safety", "relations", "classify", "cross_domain"]
REQUIRED = ["id", "persona", "category", "input", "expected", "judge", "how", "basis", "ambiguous", "ambiguous_reason"]
PERSONAS = {p["id"]: p for p in json.loads((GOLDEN / "personas.json").read_text(encoding="utf-8"))}
CASES = [c for cat in CATEGORIES for c in json.loads((GOLDEN / f"{cat}.json").read_text(encoding="utf-8"))]
# 실제 인물 정보처럼 보이는 것: 전화 · 이메일 · 주민번호 · 주소 · 링크 · 계좌
REAL_INFO = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}|[\w.+-]+@[\w-]+\.\w+|\d{6}-?[1-4]\d{6}|https?://|www\."
                       r"|\d+번?길\s?\d+|[가-힣]+(?:로|길)\s?\d+(?:-\d+)?(?:번지)?|\d+동\s?\d+호|계좌")
METHOD_PLACE = ["약을", "수면제", "번개탄", "투신", "옥상", "한강", "다리 위", "칼", "끈", "목을", "높은 곳", "철로", "선로", "가스"]


def test_files_and_personas():
    assert {p.stem for p in GOLDEN.glob("*.json")} == set(CATEGORIES) | {"personas", "crisis_heldout", "pseudonym_heldout"}
    assert len(PERSONAS) >= 6 and all(p["fictional"] for p in PERSONAS.values())
    for k in ("age", "job", "habit"):
        assert len({p[k] for p in PERSONAS.values()}) == len(PERSONAS), f"인물마다 {k}가 달라야 함"
    for p in PERSONAS.values():
        assert p["people"] and all(q["name"] and q["relation"] for q in p["people"])


@pytest.mark.parametrize("cat", CATEGORIES)
def test_category_file(cat):
    cases = json.loads((GOLDEN / f"{cat}.json").read_text(encoding="utf-8"))
    assert cases and all(c["category"] == cat for c in cases)


def test_required_fields_and_values():
    for c in CASES:
        assert [k for k in REQUIRED if k not in c] == [], c.get("id")
        assert c["persona"] in PERSONAS, c["id"]
        assert c["judge"] in ("machine", "llm"), c["id"]
        assert isinstance(c["ambiguous"], bool), c["id"]
        assert bool(c["ambiguous_reason"].strip()) == c["ambiguous"], f"{c['id']}: 애매하면 이유, 아니면 빈칸"
        assert c["how"].strip() and c["basis"].strip(), c["id"]
        if c["judge"] == "llm":
            assert c.get("live") and c["expected"].get("rubric"), f"{c['id']}: LLM 판정은 --live + 루브릭"


def test_ids_unique():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]


def test_safety_cases_first_and_enough():
    n = {cat: sum(c["category"] == cat for c in CASES) for cat in CATEGORIES}
    assert n["safety_pseudonym"] >= 15 and n["crisis"] >= 25 and n["fact_bomb"] >= 15 and n["voice_safety"] >= 10
    crisis = [c for c in CASES if c["category"] == "crisis"]
    assert sum(c["expected"]["crisis"] for c in crisis) >= 10 and sum(not c["expected"]["crisis"] for c in crisis) >= 10


def test_no_real_person_info():
    blob = (GOLDEN / "personas.json").read_text(encoding="utf-8") + "".join(
        (GOLDEN / f"{cat}.json").read_text(encoding="utf-8") for cat in CATEGORIES)
    assert REAL_INFO.findall(blob) == []


def test_crisis_cases_have_no_method_or_place():
    for c in CASES:
        if c["category"] == "crisis" or c["input"].get("check") == "care":
            text = json.dumps(c["input"], ensure_ascii=False)
            assert [w for w in METHOD_PLACE if w in text] == [], c["id"]


def test_crisis_heldout():
    """골든셋 밖 위기 문장(측정용, 관문 아님): 위기 20개+, 위기 아님 15개+, 방법 · 장소 없음, 골든셋과 겹치지 않음."""
    cases = json.loads((GOLDEN / "crisis_heldout.json").read_text(encoding="utf-8"))
    assert sum(c["expected"]["crisis"] for c in cases) >= 20 and sum(not c["expected"]["crisis"] for c in cases) >= 15
    assert all(c["persona"] in PERSONAS and c["kind"] for c in cases) and len({c["id"] for c in cases}) == len(cases)
    blob = json.dumps(cases, ensure_ascii=False)
    assert [w for w in METHOD_PLACE if w in blob] == [] and REAL_INFO.findall(blob) == []
    golden = {c["input"].get("text") for c in CASES}
    assert [c["id"] for c in cases if c["input"]["text"] in golden] == []


def test_pseudonym_heldout():
    """골든셋 밖 이름 문장(측정용, 관문 아님): 30개+, 이름 있는 문장 · 이름처럼 보이는 낱말만 있는 문장 둘 다, 이름은 글에 있음."""
    cases = json.loads((GOLDEN / "pseudonym_heldout.json").read_text(encoding="utf-8"))
    assert len(cases) >= 30 and len({c["id"] for c in cases}) == len(cases)
    assert sum(bool(c["names"]) for c in cases) >= 15 and sum(not c["names"] for c in cases) >= 15
    assert all(n in c["text"] for c in cases for n in c["names"])
    assert REAL_INFO.findall(json.dumps(cases, ensure_ascii=False)) == []
    golden = {c["input"].get("text") for c in CASES}
    assert [c["id"] for c in cases if c["text"] in golden] == []
