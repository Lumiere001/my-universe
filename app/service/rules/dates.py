"""
G2(PRD §8.2): 제목 · 본문 첫 줄 속 날짜 → 글이 다루는 날. 순수 함수.

날짜가 하나로 읽히면 확실, 날짜처럼 보이는데 못 읽거나(13/45 · 2/30) 서로 다른 날짜가 둘 이상이면(3/27~3/29)
추정 + '날짜 확인 필요'. 날짜가 없으면 사용자가 고른 날(확실) 또는 쓴 날(추정).
"""

import re
from datetime import date

# 앞의 것부터 찾고, 찾은 자리는 지워 다음 모양이 그 안을 다시 읽지 않게 한다(2026.3.27 의 3.27).
_PATTERNS = [
    re.compile(r"(?<!\d)(?P<y>\d{4}|\d{2})\s*(?:[-./]|년)\s*(?P<m>\d{1,2})\s*(?:[-./]|월)\s*(?P<d>\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(?P<y>\d{4}|\d{2})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"),          # 20260327 · 260327
    re.compile(r"(?<![\d.])(?P<m>\d{1,2})\s*(?:/|월\s*)(?P<d>\d{1,2})(?!\d)"),         # 3/27 · 3월 27일
    re.compile(r"(?<![\d.])(?P<m>\d{1,2})\.(?P<d>\d{1,2})(?![\d.]|[A-Za-z%])"),       # 3.27 (3.5km · 3.5% 는 아님)
]
# ponytail: 본문은 첫 줄이 짧을 때만 본다(손글씨 · 사진 일기의 날짜 머리줄). 긴 첫 문장 속 날짜는 다른 일의 날짜일 수 있다.
FIRST_LINE_MAX = 30


def _near(m, d, written):
    """연도가 없는 날짜: 쓴 날과 같거나 앞선 날 중 가장 최근 해(10월에 쓴 3/27 은 올해, 1월에 쓴 12/31 은 지난해).
    그해에 없는 날(2/29 등)은 ValueError → 못 읽음."""
    y = written.year if date(written.year, m, d) <= written else written.year - 1
    return date(y, m, d)


def _dates(s, written):
    """→ (읽은 날짜 집합, 못 읽은 날짜 모양이 있는지)."""
    found, bad = set(), False
    for p in _PATTERNS:
        for m in p.finditer(s):
            y = m.groupdict().get("y")
            try:
                if y:
                    found.add(date(int(y) + (2000 if len(y) == 2 else 0), int(m["m"]), int(m["d"])))
                else:
                    found.add(_near(int(m["m"]), int(m["d"]), written))
            except ValueError:
                bad = True
        s = p.sub(lambda x: " " * len(x.group()), s)
    return found, bad


def read_day(title, text, written, picked=None):
    """(글이 다루는 날, '확실'|'추정', 날짜 확인 필요). written: 쓴 날(date), picked: 사용자가 고른 날(date|None)."""
    if picked:
        return picked, "확실", False
    first = next((x.strip() for x in (text or "").splitlines() if x.strip()), "")
    for s in (title or "", first if len(first) <= FIRST_LINE_MAX else ""):
        found, bad = _dates(s, written)
        if len(found) == 1 and not bad:
            return found.pop(), "확실", False
        if found or bad:
            return written, "추정", True
    return written, "추정", False

