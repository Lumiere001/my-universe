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
    assert g({**base, "category": "fact_bomb", "input": {"check": "care"}, "expected": {"mode": "care"}})
    assert not g({**base, "category": "relations", "expected": {}})
    assert g({**base, "gate": True, "category": "voice_safety", "input": {"check": "problems"}, "expected": {"flagged": True}})
    assert not g({**base, "category": "voice_safety", "input": {"check": "problems"}, "expected": {"flagged": True}})
    assert not g({**base, "ambiguous": True, "category": "safety_pseudonym", "expected": {}})
