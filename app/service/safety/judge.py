"""
app/service/safety/judge.py

사람 판정 문장 검사(1차 gates.judged 옮김). 말 걸기(WS7)가 내보내기 전에 부른다.
"""

import re

JUDGE = re.compile(
    r"(너는|넌|당신은|글쓴이는|작성자는|이 사람은)[^.。!?]{0,30}(사람이다|사람입니다|사람이야|사람이네|성격이다|성격입니다|성격이야|타입이다|타입이야)"
    r"|우울증|불안장애|성격 ?장애|조울증|문제가 있는 사람|의지가 약한 사람|게으른 사람|글러 먹었|넌 글렀"
)


def judged(text):
    """사람을 판정 · 진단하는 문장이면 True."""
    return bool(JUDGE.search(text or ""))
