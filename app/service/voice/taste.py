"""
app/service/voice/taste

취향 고리(2026-11-07 동규 「좋다고 하면 더 좋은 쪽으로, 별로면 줄이는 구체적 방법」): 별지기 한마디마다 '말하는 방식' 세 가지를
코드로 재고(제안 · 지난 기록 떠올리기 · 길이), 그 사람이 누른 좋아요 · 별로를 방식별로 센다. 방식마다 '그렇게 쓴 한마디'와
'그렇지 않게 쓴 한마디'의 좋아요 비율을 베타 분포(사전 1:1)로 두고, 다음 한마디는 두 분포에서 하나씩 뽑아 큰 쪽으로 쓴다
(톰슨 샘플링: 좋아한 쪽을 더 자주 쓰되, 반응이 적을 땐 다른 쪽도 가끔 시험한다). 반응이 하나도 없는 방식은 정하지 않고 기본대로.
여기에 좋아요 받은 한마디의 끝부분을 '이 사람이 좋아한 결'로, 별로 받은 끝부분은 이미 있는 금지 목록으로 넣는다.
위기 · 무거운 날 · 쉼 권하기 · '제안 안 함' 설정은 이 고리보다 먼저다(voice._suggest · build_messages).
"""
import random
import re

from . import checks

RECALL = re.compile(r"\d{1,2}월\s?\d{1,2}일|지난번|지난\s?일기|지난\s?주|예전엔|예전에|전에도|그때|며칠\s?전")
SHORT_LEN = 80     # 이 글자 수 안이면 '짧게'(한두 문장). 기본 한마디는 두세 문장 120자 안팎
LIKE, DISLIKE = "좋아요", "별로"
# 방식: (이름, 그렇게 쓸 때 지시, 그렇지 않게 쓸 때 지시) — 제안은 voice._suggest 가 기존 문장으로 지시한다
WAYS = {
    "suggest": ("다음 걸음 제안", None, None),
    "recall": ("지난 기록 떠올리기", "message 에서 지난 기록(past_thoughts) 하나를 '7월 20일에는 ~'처럼 그 날짜를 넣어 한 번 떠올려 오늘 글과 잇는다.",
               "지난 기록은 꺼내지 않고 오늘 글에만 머문다."),
    "short": ("짧게", "message 는 한두 문장, 80자 안으로 짧게 쓴다(이 길이가 다른 길이 말보다 먼저).", "두세 문장으로 넉넉하게 쓴다."),
}


def ways(text):
    """한마디 한 개의 말하는 방식 → {"suggest": bool, "recall": bool, "short": bool}."""
    t = (text or "").strip()
    return {"suggest": checks.has_suggestion(t), "recall": bool(RECALL.search(t)), "short": 0 < len(t) <= SHORT_LEN}


def tally(pairs):
    """[(한마디 글, '좋아요' | '별로')] → {방식: {True: [좋아요, 별로], False: [좋아요, 별로]}}."""
    c = {k: {True: [0, 0], False: [0, 0]} for k in WAYS}
    for text, v in pairs:
        if v not in (LIKE, DISLIKE) or not text:
            continue
        for k, on in ways(text).items():
            c[k][on][0 if v == LIKE else 1] += 1
    return c


def plan(counts, rng=random):
    """방식마다 톰슨 샘플링: Beta(1+좋아요, 1+별로)를 '그렇게' · '그렇지 않게' 각각에서 뽑아 큰 쪽. 반응이 없으면 None(기본대로)."""
    out = {}
    for k, side in counts.items():
        if sum(side[True]) + sum(side[False]) == 0:
            out[k] = None
            continue
        on = rng.betavariate(1 + side[True][0], 1 + side[True][1])
        off = rng.betavariate(1 + side[False][0], 1 + side[False][1])
        out[k] = on > off
    return out


def lean(counts):
    """운영 · 설명용: 방식마다 좋아요 비율 추정(사후 평균) 차이 '그렇게 − 그렇지 않게'(+면 그렇게 쓴 쪽을 더 좋아함)."""
    m = lambda a, b: (1 + a) / (2 + a + b)   # noqa: E731
    return {k: round(m(*s[True]) - m(*s[False]), 3) for k, s in counts.items()}


def lines(p):
    """프롬프트에 넣을 지시(제안은 빼고 — 제안 문장은 voice 가 따로 쓴다)."""
    out = []
    for k, (_, yes, no) in WAYS.items():
        if k == "suggest" or p.get(k) is None:
            continue
        out.append(yes if p[k] else no)
    return out
