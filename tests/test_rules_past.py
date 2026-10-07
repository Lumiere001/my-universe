"""지난 생각 고르기: 같은 주제 먼저 · 낙폭 자르기 · 순위 합치기 · 운영 한도."""
from app.core.ontology import load
from app.service.rules import pick_past
from app.service.rules.past import cut_at_drop


def P(i, topic, emb, rid=None):
    return {"id": i, "record_id": rid or f"R{i}", "topic": topic, "day": "2026-03-01", "emb": emb}


def test_cut_at_drop():
    assert cut_at_drop([0.9, 0.88, 0.5, 0.48]) == 2
    assert cut_at_drop([0.9, 0.9, 0.9]) == 3      # 떨어짐이 없으면 전부
    assert cut_at_drop([0.4]) == 1 and cut_at_drop([]) == 0


def test_same_topic_first_and_drop_cut():
    today = [P("T1", "진로", [1, 0, 0], rid="R0")]
    past = [P("a", "진로", [0, 1, 0]),            # 같은 주제: 유사도가 낮아도 남음
            P("b", "배움", [1, 0.05, 0]),          # 비슷함
            P("c", "배움", [1, 0.1, 0]),           # 비슷함
            P("d", "건강", [0.1, 1, 0]),           # 크게 떨어진 뒤 → 잘림
            P("e", "진로", [1, 0, 0], rid="R0")]   # 오늘 글 자기 생각은 빼기
    got = pick_past(today, past)
    # 나머지(b · c · d)는 c 와 d 사이 낙폭에서 잘림, 순위 합: a 1+3, b 2+1, c 3+2
    assert [g["id"] for g in got] == ["b", "a", "c"]
    assert got[1]["same_topic"] and got[0]["rank"] == 1


def test_rank_fusion_not_score_sum():
    # 주제 순위: a(같은 주제) 1, b 2, c 3 / 유사도 순위: b 1, c 2, a 3 → 합 a 4, b 3, c 5 → b, a, c
    today = [P("T1", "진로", [1, 0, 0], rid="R0")]
    past = [P("a", "진로", [0.2, 1, 0]), P("b", "배움", [1, 0.02, 0]), P("c", "배움", [1, 0.03, 0]),
            P("d", "건강", [0, 0, 1])]
    assert [g["id"] for g in pick_past(today, past)] == ["b", "a", "c"]


def test_center_correction_changes_order():
    # 모두 한 방향으로 몰린 벡터: 평균 방향을 빼야 차이가 보인다
    today = [P("T1", "x", [1, 0.1], rid="R0")]
    past = [P("a", "x", [1, 0.3]), P("b", "x", [1, -0.05])]
    assert [g["id"] for g in pick_past(today, past)] == ["b", "a"]
    assert [g["id"] for g in pick_past(today, past, center=[1, 0])] == ["a", "b"]


def test_limit_from_ops_only():
    n = load()["limits"]["past_thoughts_max"]
    today = [P("T1", "진로", [1, 0], rid="R0")]
    past = [P(f"p{i}", "진로", [1, i / 100]) for i in range(n + 5)]
    assert len(pick_past(today, past)) == n
    assert pick_past([], past) == [] and pick_past(today, []) == []
