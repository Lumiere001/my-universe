"""
관문 G3(사람 판정 · 진단)와 내부 번호 지우기(WS12). 요약 · 관계 설명 · 닿은 순간 설명에 쓴다.

- G3: 판정 · 진단하는 문장은 뺀다. 그 말이 글쓴이 원문(source)에 있으면 글쓴이 말이라 둔다("우울증 진단을 받았다").
- 내부 번호: 관측 입력의 T1(오늘 생각) · P3(지난 생각)은 사용자에게 뜻이 없어 '오늘 생각' · '지난 생각'으로 바꾼다.
"""

import re

from app.service.safety.judge import JUDGE

_ID = re.compile(r"\(?(?<![A-Za-z0-9])([TP]\d{1,2})(?![A-Za-z0-9])\)?(와|는|가|를|로)?")
# 받침 있는 '생각' 뒤로 조사를 맞춘다(T1와 → 오늘 생각과)
_JOSA = {"와": "과", "는": "은", "가": "이", "를": "을", "로": "으로", None: ""}


def strip_ids(text, source=""):
    """내부 번호를 바꾼다. 글쓴이 원문(source)에 그 글자가 있으면('T1 경기') 글쓴이 말이라 둔다."""
    out = _ID.sub(lambda m: m.group(0) if m.group(1) in (source or "") else
                  ("오늘 생각" if m.group(1)[0] == "T" else "지난 생각") + _JOSA[m.group(2)], text or "")
    return re.sub(r"[^\S\n]{2,}", " ", out).strip()   # 이어진 공백만 줄이고 줄바꿈은 둔다(요약의 줄 나눔)


def clean_text(text, source=""):
    """G3 + 내부 번호. 판정 · 진단 문장은 빼고(원문에 있는 말이면 둠) 남은 문장을 돌려준다(다 빠지면 빈 글).
    문장 사이 띄어쓰기 · 줄바꿈은 원래대로 둔다."""
    parts = re.split(r"(?<=[.?!。])(\s+)", strip_ids(text, source))
    out = ""
    for s, gap in zip(parts[::2], parts[1::2] + [""]):
        m = JUDGE.search(s)
        if m and m.group(0) not in (source or ""):
            continue
        out += s + gap
    return out.strip()
