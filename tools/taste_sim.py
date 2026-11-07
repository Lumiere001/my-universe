"""
tools/taste_sim.py — 취향 고리 모의 실험(LLM 없음, 무료). 2026-11-07

가상 사용자 1,000명: 세 방식(제안 · 지난 기록 · 짧게) 중 2~3개에 숨은 취향(켬/끔 무작위), 나머지는 상관없음. 한 사람당 한마디 20개.
반응: 0.6 확률로 누르고, 누르면 P(좋아요) = 0.15 + 0.75 × (취향 방식 중 이번 한마디가 맞춘 비율), 아니면 별로.
대조군 '취향 없음'은 누르면 늘 P(좋아요) = 0.5.
  A 지금: 제안은 옛 다이얼(ops.pref_suggestions: 제안 든 한마디 반응이 한쪽 3번 이상 · 2배 이상이면 한 칸, 옮긴 뒤 다시 셈;
         '가끔' = 지난번에 제안했으면 뺌), 지난 기록 · 길이는 정하지 않음(각 50%).
  B 취향 고리: taste.plan(방식별 톰슨 샘플링). 반응이 없는 방식은 A 와 같은 기본. 다이얼도 그대로 돌고 '안 함'이 먼저(voice._suggest).
  C 되고 싶은 모습까지(11/7 동규 「선호만이 아니라 되고 싶은 모습과 기준을 맞춰」): B + 한마디 뒤 다음 글이 되고 싶은 모습에
         다가갔나(다가감 = 좋아요 칸) · 멀어졌나(멀어짐 = 별로 칸)를 같이 센다(taste.goal_pairs 와 같은 셈).
  되고 싶은 모습 모형(가정): 사람마다 다가가게 돕는 방식 하나(무작위 · 켬/끔, 취향과 따로 뽑아 어긋나는 사람도 있음).
         한마디가 그 방식을 맞추면 다음 글이 다가갈 확률 0.40, 아니면 0.15. 다가가지 못한 글의 1/3에서 멀어진 근거가 잡힌다.
         A · B 의 사용자 · 반응 난수는 그대로(다른 씨앗)라 A · B 숫자는 예전 결과와 같다.
한계: 사람 반응 모형은 가정이다. 지시 따름은 '완벽'과 Solar 점검으로 잰 값 두 가지로 돌린다(제안 지시는 A · B 둘 다 받는다).
고리는 실제 한마디를 taste.ways 로 잰 방식으로 센다(지시가 아니라 나온 글 기준) — 여기서도 따른 뒤의 방식으로 센다.
uv run python -m tools.taste_sim            # A · B (좋아요 비율)
uv run python -m tools.taste_sim --goal     # A · B · C (좋아요 비율 + 다음 글이 다가간 비율)
"""
import json
import random
import sys
from pathlib import Path

from app.repository.ops import pref_suggestions
from app.service.voice import taste

STYLES = ("suggest", "recall", "short")
N_USERS, N_MSG, P_REACT, SEED = 1000, 20, 0.6, 20261107
WINDOWS = ((1, 5), (6, 10), (11, 20))
OUT = Path("eval/results/2026-11-07-taste-sim.json")
GOAL_OUT = Path("eval/results/2026-11-07-taste-goal-sim.json")
P_TOWARD, P_TOWARD_MISS, P_AWAY = 0.40, 0.15, 1 / 3
# 지시를 따르는 비율(켬 지시 → 켬, 끔 지시 → 끔). '완벽'과 Solar 점검으로 잰 값(taste-adherence 1 · 2판, 적은 수라 거친 값)
ADHERE = {"완벽": {k: (1.0, 1.0) for k in ("suggest", "recall", "short")},
          "잰 값": {"suggest": (0.25, 1.0), "recall": (0.75, 1.0), "short": (0.9, 0.9)}}
DIAL = {"적게": "안 함", "보통": "가끔", "많이": "자주"}


def user(rng, control):
    if control:
        return {}
    ks = rng.sample(STYLES, rng.choice((2, 3)))
    return {k: rng.random() < 0.5 for k in ks}


def p_like(pref, msg):
    return 0.5 if not pref else 0.15 + 0.75 * sum(msg[k] == v for k, v in pref.items()) / len(pref)


def run(policy, control, seed, adhere=ADHERE["완벽"]):
    rng = random.Random(seed)          # 같은 씨앗 → A · B 가 같은 사용자 · 같은 반응 난수를 받는다
    users = [user(rng, control) for _ in range(N_USERS)]
    out = []                           # (사용자, 몇 번째, 맞춘 비율, 반응 또는 None)
    for u, pref in enumerate(users):
        r = random.Random(seed * 7919 + u)      # 반응 · 기본 동전
        pick = random.Random(seed * 104729 + u)  # 톰슨 뽑기(B 만 씀)
        obey = random.Random(seed * 31337 + u)   # 지시 따름
        gr = random.Random(seed * 1299709 + u)   # 되고 싶은 모습 쪽(돕는 방식 · 다음 글) — A · B 난수와 따로
        hs, hv = gr.choice(STYLES), gr.random() < 0.5
        counts = {k: {True: [0, 0], False: [0, 0]} for k in STYLES}
        dial, sig, prev = "보통", [0, 0], None
        for i in range(1, N_MSG + 1):
            freq = DIAL[dial]
            old_suggest = freq == "자주" or (freq == "가끔" and not (prev and prev["suggest"]))
            coin = {k: r.random() < 0.5 for k in ("recall", "short")}
            msg, told = {"suggest": old_suggest, **coin}, {"suggest"}   # 제안은 두 정책 모두 지시한다
            if policy in ("B", "C"):
                p = taste.plan(counts, pick)
                msg = {k: msg[k] if p[k] is None else p[k] for k in STYLES}
                told |= {k for k in STYLES if p[k] is not None}
                if freq == "안 함":
                    msg["suggest"] = False
            msg = {k: v if k not in told or obey.random() < adhere[k][0 if v else 1] else not v for k, v in msg.items()}
            roll, like_roll = r.random(), r.random()
            v = None
            if roll < P_REACT:
                v = taste.LIKE if like_roll < p_like(pref, msg) else taste.DISLIKE
                for k in STYLES:
                    counts[k][msg[k]][0 if v == taste.LIKE else 1] += 1
                if msg["suggest"]:   # 옛 다이얼은 제안 든 한마디의 반응만 센다
                    sig[0 if v == taste.LIKE else 1] += 1
                    mv = pref_suggestions({"suggestions": dial}, {"suggestions": tuple(sig)})
                    if mv:
                        dial, sig = mv[0]["to"], [0, 0]
            toward = gr.random() < (P_TOWARD if msg[hs] == hv else P_TOWARD_MISS)
            away = not toward and gr.random() < P_AWAY
            if policy == "C" and (toward or away):
                for k in STYLES:
                    counts[k][msg[k]][0 if toward else 1] += 1
            match = sum(msg[k] == val for k, val in pref.items()) / len(pref) if pref else None
            out.append((u, i, match, v, toward))
            prev = msg
    return out


def summary(rows):
    res = {}
    for a, b in WINDOWS:
        w = [x for x in rows if a <= x[1] <= b]
        rx = [x[3] for x in w if x[3]]
        likes = sum(v == taste.LIKE for v in rx)
        m = [x[2] for x in w if x[2] is not None]
        p = likes / len(rx)
        res[f"{a}-{b}"] = {"reactions": len(rx), "like_share": round(p, 3), "ci95": round(1.96 * (p * (1 - p) / len(rx)) ** 0.5, 3),
                           "style_match": round(sum(m) / len(m), 3) if m else None,
                           "toward_share": round(sum(x[4] for x in w) / len(w), 3)}
    return res


def main():
    table = {}
    for group, control, adh in (("취향 있음", False, "완벽"), ("취향 있음 · 따름 잰 값", False, "잰 값"),
                                ("취향 없음(대조군)", True, "완벽")):
        table[group] = {pol: summary(run(pol, control, SEED + control, ADHERE[adh])) for pol in ("A", "B")}
    print(f"{'group':<12} {'window':<6} {'A like':>8} {'B like':>8} {'B-A':>7} {'A match':>8} {'B match':>8}")
    for g, t in table.items():
        for w in t["A"]:
            a, b = t["A"][w], t["B"][w]
            print(f"{g:<12} {w:<6} {a['like_share']:>8} {b['like_share']:>8} {b['like_share'] - a['like_share']:>+7.3f} "
                  f"{a['style_match'] or '-':>8} {b['style_match'] or '-':>8}")
    OUT.write_text(json.dumps({"date": "2026-11-07", "seed": SEED, "users": N_USERS, "messages": N_MSG, "p_react": P_REACT,
                               "model": "P(좋아요|누름)=0.15+0.75×맞춘 비율, 대조군 0.5", "policies": {
                                   "A": "옛 다이얼(제안만, 3번 · 2배) + 지난 기록 · 길이 50%",
                                   "B": "taste.plan 방식별 톰슨 샘플링(반응 없으면 A 기본, 다이얼 '안 함' 먼저)"},
                               "adherence": ADHERE, "results": table},
                              ensure_ascii=False, indent=1))
    print("→", OUT)


def main_goal():
    table = {}
    for group, adh in (("취향 있음", "완벽"), ("취향 있음 · 따름 잰 값", "잰 값")):
        table[group] = {pol: summary(run(pol, False, SEED, ADHERE[adh])) for pol in ("A", "B", "C")}
    print(f"{'group':<14} {'window':<6} " + " ".join(f"{p + ' like':>8} {p + ' 다가감':>8}" for p in "ABC"))
    for g, t in table.items():
        for w in t["A"]:
            print(f"{g:<14} {w:<6} " + " ".join(f"{t[p][w]['like_share']:>8} {t[p][w]['toward_share']:>8}" for p in "ABC"))
    GOAL_OUT.write_text(json.dumps({"date": "2026-11-07", "seed": SEED, "users": N_USERS, "messages": N_MSG, "p_react": P_REACT,
                                    "model": {"좋아요": "P(좋아요|누름)=0.15+0.75×취향 맞춘 비율",
                                              "되고 싶은 모습": f"돕는 방식 하나(취향과 따로), 맞추면 다음 글 다가감 {P_TOWARD}, 아니면 {P_TOWARD_MISS}, "
                                                          f"다가가지 못한 글의 {P_AWAY:.2f}에서 멀어짐"},
                                    "policies": {"A": "옛 다이얼 + 50%", "B": "취향 고리(좋아요 · 별로만)",
                                                 "C": "취향 고리 + 다가감 · 멀어짐(좋아요 · 별로와 같은 무게)"},
                                    "adherence": ADHERE, "results": table}, ensure_ascii=False, indent=1))
    print("→", GOAL_OUT)


if __name__ == "__main__":
    main_goal() if sys.argv[1:] == ["--goal"] else main()
