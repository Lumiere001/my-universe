"""골든셋 실행기가 외부 호출 없이 끝까지 도는지(WS8). 골든셋 실패는 테스트 실패가 아니다."""
import importlib.util
from pathlib import Path

from app.core import llm

_spec = importlib.util.spec_from_file_location("eval_run", Path(__file__).resolve().parents[1] / "eval/run.py")
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)


def test_offline_run_makes_no_external_calls(monkeypatch):
    calls = []

    def boom(*a, **k):
        calls.append(a)
        raise RuntimeError("외부 호출")

    monkeypatch.setattr(llm, "chat", boom)
    monkeypatch.setattr(llm, "embed", boom)
    monkeypatch.setattr(llm, "client", boom)
    rows = run.run(run.CATEGORIES, live=False)
    assert calls == []
    assert len(rows) == len(run.load_cases())
    for r in rows:
        assert r["status"] in ("pass", "fail", "skip")
        assert not any(p.startswith("오류") for p in r["problems"]), (r["id"], r["problems"])
    cases = {c["id"]: c for c in run.load_cases()}
    assert {r["id"] for r in rows if r["status"] == "skip"} == {i for i, c in cases.items() if c.get("live")}


def test_summary_and_gate():
    rows = [{"id": "a", "category": "crisis", "gate": True, "ambiguous": False, "status": "pass", "problems": [], "detail": {}},
            {"id": "b", "category": "crisis", "gate": False, "ambiguous": False, "status": "fail", "problems": ["x"], "detail": {}},
            {"id": "c", "category": "crisis", "gate": False, "ambiguous": True, "status": "fail", "problems": ["y"], "detail": {}}]
    s = run.summarize(rows, baseline={"crisis": ["a", "b"]})
    assert s["categories"]["crisis"] == {"passed": 1, "total": 2, "gate_passed": 1, "gate_total": 1, "ambiguous": 1, "skipped": 0}
    assert s["gate_ok"] and s["regressions"] == ["b"]
    rows[0]["status"] = "fail"
    assert not run.summarize(rows)["gate_ok"]
    assert "불합격" in run.report_md(rows, run.summarize(rows), live=False)


def test_gate_rule():
    g = run.is_gate
    base = {"ambiguous": False, "input": {}}
    assert g({**base, "category": "safety_pseudonym", "expected": {}})
    assert g({**base, "category": "crisis", "expected": {"crisis": True}})
    assert not g({**base, "category": "crisis", "expected": {"crisis": False}})
    assert g({**base, "category": "fact_bomb", "input": {"check": "line"}, "expected": {"flagged": True}})
    assert not g({**base, "category": "fact_bomb", "input": {"check": "line"}, "expected": {"flagged": False}})
    assert g({**base, "category": "fact_bomb", "input": {"check": "crisis"}, "expected": {"mode": "comfort"}})
    assert not g({**base, "category": "relations", "expected": {}})
    assert g({**base, "gate": True, "category": "voice_safety", "input": {"check": "problems"}, "expected": {"flagged": True}})
    assert not g({**base, "category": "voice_safety", "input": {"check": "problems"}, "expected": {"flagged": True}})
    assert not g({**base, "ambiguous": True, "category": "safety_pseudonym", "expected": {}})


def test_heldout_offline_rules_only(monkeypatch):
    monkeypatch.setattr(llm, "chat", run.blocked)
    rows, s = run.heldout(live=False)
    assert rows and "rules+llm" not in s and s["cost"]["calls"] == 0
    assert "| rules |" in run.heldout_md(rows, s, live=False)


def test_crisis_llm_mode_records_both(monkeypatch):
    """--crisis-llm: 서비스처럼 detect_crisis(llm=True)로 판정하고, 규칙만 결과도 같이 센다(가짜 판정기, 외부 호출 없음)."""
    calls = []

    def fake(text, people=None, llm=False):
        calls.append(llm)
        return {"crisis": llm, "signals": []}

    monkeypatch.setattr(run.safety, "detect_crisis", fake)
    monkeypatch.setitem(run.MODE, "crisis_llm", True)
    rows = run.run(["crisis"], live=True)
    m = run.crisis_modes(rows)
    pos = sum(c["expected"]["crisis"] for c in run.load_cases(["crisis"]) if not c["ambiguous"])
    assert m["rules"]["recall"] == f"0/{pos}" and m["rules+llm"]["recall"] == f"{pos}/{pos}"
    assert True in calls and False in calls
    s = {**run.summarize(rows), "crisis_modes": m}
    assert "규칙 + LLM 재현율" in run.report_md(rows, s, live=True)


def test_llm_judge_reads_word_not_json(monkeypatch):
    """채점 답의 JSON 이 깨져도(why 따옴표 빠짐, 2026-10-08 fb-34) "pass" 낱말로 읽는다. 낱말이 없으면 불합격."""
    for raw, want in [('{"pass": true, "why": 소리 지른 행동만 짚었다.}', True), ('{"pass": false, "why": "x"}', False),
                      ("모르겠다", False)]:
        monkeypatch.setattr(llm, "chat", lambda *a, _r=raw, **k: _r)
        assert run.llm_judge("루브릭", "글", "한마디")[0] is want, raw


def test_pseudonym_heldout_offline(monkeypatch):
    monkeypatch.setattr(llm, "chat", run.blocked)
    rows, s = run.pseudonym_heldout()
    assert len(rows) >= 30 and s["recall"].endswith("/22") and "놓침" in run.pseudonym_heldout_md(rows, s)
