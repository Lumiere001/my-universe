"""가상 인물 시험 도구(tools/persona_eval.py)의 채점 · 시뮬레이션: 네트워크 없이."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("persona_eval", Path(__file__).resolve().parent.parent / "tools/persona_eval.py")
pe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pe)


def test_personas_follow_rules():
    for k in "ABCD":
        assert pe.check(pe.load(k)) == []


def test_pair_f1_counts_entry_pairs():
    gt = {1: {"t1"}, 2: {"t1"}, 3: {"t2"}}
    assert pe.pair_f1({1: {"a"}, 2: {"a"}, 3: {"b"}}, gt) == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert pe.pair_f1({1: {"a"}, 2: {"b"}, 3: {"b"}}, gt) == {"precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_simulate_joins_new_name_only_when_close():
    seq = [[{"name": "회사 고르기", "sun_id": "d1", "vec": [1.0, 0.0]}],
           [{"name": "직장 기준", "sun_id": "d1", "vec": [0.95, 0.05]}],
           [{"name": "부모님", "sun_id": "d1", "vec": [0.0, 1.0]}]]
    assert pe.simulate(seq, None, None) == [["회사 고르기"], ["직장 기준"], ["부모님"]]   # 끄면 이름대로
    assert pe.simulate(seq, 0.9, None) == [["회사 고르기"], ["회사 고르기"], ["부모님"]]
