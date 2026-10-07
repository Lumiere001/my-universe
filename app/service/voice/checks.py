"""
app/service/voice/checks.py

말 걸기 생성 뒤 검사(코드, LLM 아님). 넘지 않는 선 · 원문 근거 · 반복 · 제안 여부를 본다.
문제 목록을 돌려주고, 비어 있으면 통과다.
"""

import re
from difflib import SequenceMatcher

# 넘지 않는 선: 행동 · 핑계가 아니라 사람 자체를 때리는 표현
# ponytail: 낱말 목록 검사라 돌려 말한 공격은 놓친다. 골든셋(WS8)에서 새는 표현이 보이면 여기에 더한다.
_LINE = [
    ("사람 판정", r"(?<![가-힣])(너는?|넌|당신은?|글쓴이는?)\s[^.?!]{0,20}(사람|인간|타입|성격)(이야|이다|이네|이에요|이군|이지|이구나|임)"),
    ("인격 공격", r"글렀|한심|쓰레기|구제\s?불능|패배자|루저|무능|게을러\s?터|인간\s?쓰레기|못난\s?(놈|애|년)|병신|찐따|머저리|멍청"),
    ("외모 공격", r"못생|뚱뚱|돼지같|살\s?(좀|부터)\s?빼|얼굴\s?(꼴|하고는|봐라)|외모\s?(꼴|부터|가\s?문제)|키\s?작"),
    ("가족 공격", r"(엄마|아빠|부모|가족|집안|어머니|아버지)[^.?!]{0,10}(닮아서|탓이|때문이|교육|수준|꼴|유전)"),
    ("정체성 공격", r"(여자|남자|나이|지방|출신|신앙|종교|장애)[^.?!]{0,6}(라서|니까|주제에|답게)"),
    ("위기 방법 · 장소", r"뛰어내|목을\s?매|투신|번개탄|손목을|약을\s?모|수면제|옥상|다리\s?위|선로"),
    ("거리 숫자", r"\d+\s?(%|퍼센트|점\b|점이|점을|점만)|달성률|점수|거리[는가]?\s?\d"),
]

# 다음 걸음 제안(질문 · 명령)으로 보이는 끝맺음
_SUGGEST = re.compile(r"볼까|할까|볼래|해\s?봐|해\s?보자|하자|해라|하세요|보세요|어때|어떨까|해\s?볼|"
                      r"(\d+\s?분|하나|한\s?번|한\s?곳|한\s?줄|한\s?개)만")

_QUOTE = re.compile(r"['‘“\"「]([^'’”\"」]{2,80})['’”\"」]")


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def has_suggestion(text):
    return bool(_SUGGEST.search(text or ""))


def line_problems(text):
    return [f"{name}: '{m.group(0)}'" for name, pat in _LINE if (m := re.search(pat, text or ""))]


def quote_problems(text, sources):
    """따옴표로 인용한 말이 원문(오늘 글 · 닿은 순간 · 되고 싶은 모습 · 다짐)에 있어야 한다."""
    src = _norm(" ".join(sources))
    return [f"원문에 없는 인용: '{q}'" for q in _QUOTE.findall(text or "") if _norm(q) not in src]


def _sentences(s):
    return [x for x in re.split(r"(?<=[.?!~])\s+", s.strip()) if len(_norm(x)) >= 8]


def repeat_problems(text, past):
    """지난 한마디 전체와 비교: 통째로 비슷하거나(0.6) 한 문장이 거의 같으면(0.8) 반복."""
    out = []
    for p in past or []:
        if SequenceMatcher(None, _norm(text), _norm(p)).ratio() >= 0.6:
            out.append(f"지난 한마디와 비슷함: '{p[:30]}'")
            continue
        for a in _sentences(text):
            if any(SequenceMatcher(None, _norm(a), _norm(b)).ratio() >= 0.8 for b in _sentences(p)):
                out.append(f"지난 한마디와 같은 문장: '{a[:30]}'")
                break
    return out


MAX_LEN = 300  # 한마디는 짧게(2~4문장)


def problems(msg, next_q, *, sources, past, comfort, aspiration, gentle=False, tone=None):
    """생성된 한마디 · 다음 질문의 문제 목록."""
    both = f"{msg}\n{next_q}"
    out = line_problems(both) + quote_problems(both, sources) + repeat_problems(msg, past)
    if comfort and (has_suggestion(msg) or next_q):
        out.append("무거운 날인데 제안이 있음")
    if aspiration and (m := re.search(r"멀어\S*|되고\s?싶다(면서|며|더니)", both)):
        out.append(f"멀어진 순간을 말함: '{m.group(0)}'")
    if gentle and re.search(r"(^|\s)야[,!]", msg):
        out.append("오늘은 살살인데 거친 부름")
    if tone == "고양이처럼" and "냥" not in msg:
        out.append("고양이 말끝(냥) 없음")
    if len(msg) > MAX_LEN:
        out.append(f"너무 김({len(msg)}자, {MAX_LEN}자 안으로)")
    if not msg.strip():
        out.append("빈 한마디")
    return out
