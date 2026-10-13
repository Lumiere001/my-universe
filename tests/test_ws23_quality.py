"""WS23 품질 루프 · 평가: E7 · E6 채점, 거짓 연결 판정, 표본 검토 양식, 재현율 · E4, E1, 드리프트, E5, E9,
골든셋 --check(CI 문지기), 흔들림 2판 도구, CI 워크플로. 모두 외부 호출 없음."""
import importlib.util
import json
from pathlib import Path

import pytest

from app.core.ontology import choices

ROOT = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


labels = _load("eval_labels", "eval/labels.py")
exp = _load("eval_experiments", "eval/experiments.py")
run = _load("eval_run_ws23", "eval/run.py")
stab = _load("tools_stability_v2", "tools/stability_v2.py")


# ---------------- 일치도 · E7 · E6 ----------------

def test_agreement_kappa():
    assert labels.agreement(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == {"n": 4, "agree": 1.0, "kappa": 1.0}
    k = labels.agreement(["a", "a", "b", "b"], ["a", "b", "a", "b"])   # 우연 수준: 일치 0.5, κ 0
    assert k["agree"] == 0.5 and k["kappa"] == 0.0
    assert labels.agreement([], [])["kappa"] is None


def G(i, day, quote, ka, va="", kb="", vb=""):
    return {"id": i, "day": day, "thought": quote, "quote": quote, "kind_a": ka, "value_a": va, "kind_b": kb, "value_b": vb}


def test_match_by_quote_across_splits():
    gold = [G("g1", "d1", "결국 직장은 안정이 제일이다.", "신념·원칙"), G("g2", "d1", "흔들리지 말고 공채 준비를 시작하자.", "다짐"),
            G("g3", "d2", "요즘 몸이 무겁다.", "감정")]
    pred = [{"id": "p1", "day": "d1", "thought": "", "quote": "직장은 안정이 제일이다", "kind": "해석", "value": "안정"},   # 일부 인용
            {"id": "p2", "day": "d1", "thought": "", "quote": "전혀 다른 문장", "kind": "다짐", "value": ""},
            {"id": "p3", "day": "d2", "thought": "", "quote": "흔들리지 말고 공채 준비를 시작하자.", "kind": "다짐", "value": ""}]   # 다른 날 → 짝 아님
    m = labels.match(gold, pred)
    assert set(m) == {"g1"} and m["g1"]["id"] == "p1"


def test_e7_score_consensus_missed_extra_and_e6():
    rows = [G("g1", "d1", "가나다라마바", "다짐", "성취", "다짐", "성취"),
            G("g2", "d1", "사아자차카타", "질문", "", "질문", ""),
            G("g3", "d1", "파하가나다라", "감정", "", "해석", "")]          # 두 사람이 다름 → 정답에서 빠짐
    pred = [{"id": "p1", "day": "d1", "thought": "", "quote": "가나다라마바", "kind": "다짐", "value": "안정"},
            {"id": "p9", "day": "d1", "thought": "", "quote": "전혀 다른 글", "kind": "해석", "value": ""}]
    s = labels.e7_score(rows, {"c2": pred})
    assert s["gold_source"] == "A · B 합의" and s["gold"] == 2
    assert s["annotators"]["kind"]["agree"] == round(2 / 3, 3)
    c = s["c2"]
    assert (c["matched"], c["missed"], c["extra"]) == (1, ["g2"], 1)
    assert c["kind_accuracy"] == 1.0 and c["value_agreement"] == 0.0 and c["value_agreement_when_shown"] == 0.0


def test_e7_score_only_days_the_config_ran():
    rows = [G("g1", "d1", "가나다라", "다짐"), G("g2", "d2", "마바사아", "질문")]
    s = labels.e7_score(rows, {"c": [{"id": "p", "day": "d2", "thought": "", "quote": "마바사아", "kind": "소망", "value": ""}]})
    assert s["gold_source"] == "A 한 벌" and s["c"]["gold"] == 1 and s["c"]["kind_accuracy"] == 0.0
    assert s["c"]["kind_confusion"] == [("질문 → 소망", 1)]


def test_virtual_gold_is_valid_and_scores():
    """가상 정답(하늘 61개)은 v8 목록 값만, 설정 #1 답으로 숫자가 나온다(사람 정답이 없어도 E7 · E6 을 잼)."""
    rows = labels.read_csv(ROOT / "eval/golden/e7_haneul.csv")
    assert len(rows) == 61 and all(r["kind_a"] in choices("kinds") for r in rows)
    assert all(r["value_a"] in choices("values") + [""] for r in rows)
    pred = labels.load_pred(ROOT / "eval/golden/e7_haneul_c1.json")
    assert all(p["kind"] in choices("kinds") for p in pred)   # v7 이름(반성)은 v8 로 바로잡음
    s = labels.e7_score(rows, {"c1": pred})["c1"]
    assert s["matched"] == 61 and 0 < s["kind_accuracy"] <= 1 and s["value_agreement"] is not None


def test_load_pred_from_stability_result(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"detail": [
        {"day": "d1", "runs": [{"thoughts": [{"thought": "t", "quote": "q", "kind": "반성", "value": "Benevolence"}]}]},
        {"day": "d2", "runs": []}]}), encoding="utf-8")   # 실패한 글은 건너뜀
    assert labels.load_pred(p) == [{"id": "d1-S1", "day": "d1", "thought": "t", "quote": "q", "kind": "자기평가(부정)", "value": "배려"}]


def test_e7_form_hides_ai_answers(tmp_path):
    src = tmp_path / "pred.json"
    src.write_text(json.dumps([{"id": "a", "day": "d", "thought": "t", "quote": "q", "kind": "다짐", "value": "성취"}]), encoding="utf-8")
    form = tmp_path / "form.csv"
    labels.main(["e7-form", str(src), str(form)])
    rows = labels.read_csv(form)
    assert rows == [{"id": "a", "day": "d", "thought": "t", "quote": "q", "kind_a": "", "value_a": "", "kind_b": "", "value_b": "", "note": ""}]
    assert "다짐" not in form.read_text(encoding="utf-8-sig")


# ---------------- 거짓 연결 · 표본 검토 ----------------

def test_links_form_keeps_only_off_design_cross_record():
    result = {"relations_detail": [
        {"type": "바뀜", "from": "A-T1", "to": "B-T1", "same_target": "x", "topic": "진로", "explanation": "설계 안"},
        {"type": "이어짐", "from": "A-T1", "to": "A-T2", "same_target": "x", "topic": "진로", "explanation": "같은 글"},
        {"type": "긴장", "from": "C-T1", "to": "B-T2", "same_target": "y", "topic": "진로", "explanation": "설계 밖"}]}
    rows = labels.links_form_rows(result, {"A": "2026-03-14", "B": "2026-09-20", "C": "2026-05-30"})
    assert [r["id"] for r in rows] == ["L3"] and rows[0]["from_day"] == "2026-05-30"


def test_links_score_and_committed_judgement():
    s = labels.links_score([{"type": "바뀜", "verdict": "틀림"}, {"type": "이어짐", "verdict": "맞음"},
                            {"type": "해소", "verdict": "약함"}, {"type": "이어짐", "verdict": ""}])
    assert s["judged"] == 3 and s["false_rate"] == round(2 / 3, 3) and s["false_by_type"] == {"바뀜": 1, "해소": 1}
    done = labels.links_score(labels.read_csv(ROOT / "eval/golden/links_v2.csv"))
    assert done["off_design"] == done["judged"] == 33 and done["false_rate"] is not None


def test_review_form_takes_all_fails_and_ambiguous_then_samples():
    cases = [{"id": f"p{i}", "category": "crisis", "gate": False, "ambiguous": False, "status": "pass", "problems": [], "detail": {}}
             for i in range(30)]
    cases += [{"id": "f1", "category": "classify", "gate": False, "ambiguous": False, "status": "fail", "problems": ["x"], "detail": {}},
              {"id": "a1", "category": "crisis", "gate": False, "ambiguous": True, "status": "pass", "problems": [], "detail": {}},
              {"id": "s1", "category": "fact_bomb", "gate": True, "ambiguous": False, "status": "skip", "problems": [], "detail": {}}]
    rows = labels.review_rows({"cases": cases}, n=5)
    ids = [r["id"] for r in rows]
    assert ids[:2] == ["f1", "a1"] and len(rows) == 5 and "s1" not in ids
    assert ids == [r["id"] for r in labels.review_rows({"cases": cases}, n=5)]   # 같은 결과면 같은 표본
    s = labels.review_score([{**r, "human": h} for r, h in zip(rows, ["맞음", "틀림", "맞음", "", "애매"])])
    assert s["reviewed"] == 4 and s["machine_right"] == 0.5 and s["disputed"] == ["a1"]


# ---------------- 재현율 · E4 · E1 · 드리프트 · E5 · E9 ----------------

def U(i, day, emb, topic=None):
    return {"id": i, "record_id": f"R{day}", "day": day, "topic": topic or i, "emb": emb}


def test_recall_fixed_vs_adaptive():
    """정답 지난 글이 유사도 7위면 고정 5 는 놓치고 고정 10 · 적응형(서비스 pick_past)은 잡는다."""
    today = [U("t", "d9", [1.0, 0.0, 0.0])]
    near = [U(f"n{i}", f"d1{i}", [1.0, 0.02 * i, 0.0]) for i in range(1, 7)]   # 더 가까운 6개(정답 아님)
    gold = [U("g", "d0", [1.0, 0.2, 0.0])]
    far = [U(f"f{i}", f"d0{i}", [0.0, 0.0, 1.0]) for i in range(1, 4)]
    rows, s = exp.recall_e4(today + near + gold + far, [{"past": "d0", "today": "d9", "type": "이어짐"}], ks=(5, 10))
    assert rows[0]["sim_rank"] == 7
    assert s["fixed5"]["recall"] == "0/1" and s["fixed10"]["recall"] == "1/1" and s["adaptive"]["recall"] == "1/1"
    assert s["adaptive"]["mean_size"] < s["fixed10"]["mean_size"]   # 크게 떨어지는 곳에서 잘라 입력이 작다


def test_e1_vector_vs_judge(monkeypatch):
    monkeypatch.setattr(exp, "EXPECTED", {"relations": [{"type": "바뀜", "past": "a", "today": "c"}],
                                          "not_relations": [{"type": "바뀜", "past": "a", "today": "b"}]})
    ts = [{"id": "1", "day": "a", "emb": [1.0, 0.0]}, {"id": "2", "day": "b", "emb": [1.0, 0.05]},
          {"id": "3", "day": "c", "emb": [0.5, 1.0]}]
    rels = [{"type": "바뀜", "from_record": "Ra", "to_record": "Rc"}]
    r = exp.e1(ts, rels, {"Ra": "a", "Rb": "b", "Rc": "c"})
    assert r["decoy"][0]["rank"] < r["gold_change"][0]["rank"]   # 감정만 달라진 쌍이 벡터로는 더 가깝다
    assert r["vector_precision_at_k"] == "0/1" and r["judge_recall"] == "1/1" and r["judge_decoy"] == 0


def test_drift_total_variation_and_domain_count():
    items = [{"day": "2026-03-01", "domain": "건강"}, {"day": "2026-03-02", "domain": "관계"},
             {"day": "2026-04-01", "domain": "건강"}, {"day": "2026-04-02", "domain": "건강"}, {"day": "2026-04-03", "domain": None}]
    d = exp.drift(items)
    assert [(r["window"], r["n"], r["domains"]) for r in d] == [("2026-03", 2, 2), ("2026-04", 2, 1)]
    assert d[0]["tv_prev"] is None and d[1]["tv_prev"] == 0.5 and d[1]["moved"][0] in (("건강", 0.5), ("관계", -0.5))


def test_e5_steps_entries_failures_and_ledger():
    logs = [{"event": "step", "step": "record_agent", "entry_id": "e1", "ms": 30000, "est_usd": 0.05},
            {"event": "step", "step": "voice", "entry_id": "e1", "ms": 2000, "est_usd": 0.001},
            {"event": "step", "step": "record_agent", "entry_id": "e2", "ms": 40000, "est_usd": 0.05},
            {"event": "external", "what": "studio_record", "ok": True}, {"event": "external", "what": "studio_record", "ok": False},
            {"event": "http", "ms": 5}]
    r = exp.e5(logs, [{"ws": "WS23", "calls": 9, "est_usd": 0.45}, {"ws": "WS2", "calls": 1, "est_usd": 0.05}])
    assert r["steps"]["record_agent"]["median_ms"] == 35000 and r["entry"]["n"] == 2
    assert r["external_fail"] == {"studio_record": "1/2"} and r["ledger_total_usd"] == 0.5
    assert list(r["ledger"]) == ["WS23", "WS2"]


def test_e9_groups_by_setting_and_suggestion():
    rows = [{"suggest_setting": "자주", "suggested": True, "reaction": "별로", "reason": "설교 같음", "wrote_next_day": False},
            {"suggest_setting": "자주", "suggested": True, "reaction": "좋아요", "reason": None, "wrote_next_day": True},
            {"suggest_setting": "안 함", "suggested": False, "reaction": None, "reason": None, "wrote_next_day": True}]
    g = {(r["setting"], r["suggested"]): r for r in exp.e9(rows)}
    assert g[("자주", "제안 있음")] == {"setting": "자주", "suggested": "제안 있음", "n": 2, "next_day": 0.5, "dislike": 0.5, "preachy": 0.5}
    assert g[("안 함", "제안 없음")]["next_day"] == 1.0 and exp.e9([]) == []


# ---------------- 골든셋 --check (CI) ----------------

@pytest.fixture
def keep_llm(monkeypatch):
    """--check 는 llm.chat · embed 를 막아 둔다. 다른 시험에 새지 않게 끝나면 되돌린다."""
    monkeypatch.setattr(run.llm, "chat", run.llm.chat)
    monkeypatch.setattr(run.llm, "embed", run.llm.embed)


def test_check_passes_offline_without_writing(monkeypatch, tmp_path, keep_llm):
    monkeypatch.setattr(run, "DOC", tmp_path / "doc.md")
    before = sorted(p.name for p in run.RESULTS.iterdir())
    assert run.main(["--check"])["regressions"] == []
    assert not (tmp_path / "doc.md").exists() and sorted(p.name for p in run.RESULTS.iterdir()) == before


def test_check_fails_on_gate_failure(monkeypatch, keep_llm):
    real = run.JUDGES["safety_pseudonym"]
    monkeypatch.setitem(run.JUDGES, "safety_pseudonym", lambda c, p: (["실명 샘"], {}) if c["id"] == "pn-01" else real(c, p))
    with pytest.raises(SystemExit) as e:
        run.main(["--check", "--category", "safety_pseudonym"])
    assert e.value.code == 1


def test_ci_workflow_runs_tests_and_golden_on_push_and_pr():
    wf = (ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    assert "push:" in wf and "pull_request:" in wf
    assert "uv run --frozen pytest -q" in wf and "uv run --frozen python eval/run.py --check" in wf
    assert "secrets." not in wf   # 키 없이 돈다


# ---------------- 흔들림 2판 ----------------

def _run(kinds, quotes, rtype="생각·성찰"):
    return {"record_type": rtype, "thoughts": [{"kind": k, "quote": q, "value": "", "topic": "진로", "thought": q, "certainty": "단정"}
                                               for k, q in zip(kinds, quotes)]}


def test_stability_compare():
    same = stab.compare([_run(["다짐", "질문"], ["a b", "c"])] * 3)
    assert same["type_same"] and same["kinds_same"] and same["quote_overlap_vs_first"] == [1.0, 1.0]
    diff = stab.compare([_run(["다짐", "질문"], ["a", "c"]), _run(["다짐"], ["a"], "경험 기록")])
    assert not diff["type_same"] and not diff["kinds_same"] and diff["thought_counts"] == [2, 1]
    assert diff["quote_overlap_vs_first"] == [0.5]


def test_stability_main_ledgers_every_run_and_stops_after_two_failures(monkeypatch, tmp_path):
    lines = []
    monkeypatch.setattr(stab, "targets", lambda: [{"title": f"t{i}", "body": "b", "day": f"d{i}"} for i in range(3)])
    monkeypatch.setattr(stab, "spent_so_far", lambda: 0.0)
    monkeypatch.setattr(stab, "ledger", lambda what, calls, usd: lines.append((what, calls, usd)))
    monkeypatch.setattr(stab, "ROOT", tmp_path)
    (tmp_path / "eval/results").mkdir(parents=True)
    seq = iter([(_run(["다짐"], ["a"]), 1, 0.05, None)] * 3 + [(None, 2, 0.1, "studio_timeout")] * 2)
    monkeypatch.setattr(stab, "once", lambda rec, n: next(seq))
    out = stab.main()
    assert len(lines) == 5 and "실패 studio_timeout" in lines[-1][0]          # 실패한 실행도 원장에
    assert out["records"] == 1 and out["records_failed"] == 1 and out["failed_runs"] == 2   # 연달아 2번 실패 → 멈춤
    assert out["est_usd"] == 0.35 and out["kind_agreement"] == "1/1"
