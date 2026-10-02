"""
gates.py

관문 4개 (PRD §8.2). 평가 때만이 아니라 모든 실행에서 결과를 화면에 내보내기 전에 거른다.

G1 원문에 없는 인용      → 그 생각은 화면에 올리지 않는다
G2 추정 표시 없는 틀린 날짜 → 제목 속 날짜를 놓쳤으면 걸린다
G3 사람을 단정하는 표현   → 그 문장을 중립 문장으로 바꾼다
G4 다른 사람 실명 노출    → 이름을 ○○로 가린다
"""

import re

from importer import TITLE_DATE

##################################################
# G1 원문 인용
##################################################

def _squash(s):
    return re.sub(r"[\s\"'“”‘’]+", "", s or "")


def quote_in_source(quote, source):
    q = _squash(quote)
    return bool(q) and q in _squash(source)


##################################################
# G2 날짜
##################################################

def date_ok(rec):
    """제목에 날짜가 있는데 '추정'으로 남았다면 날짜를 놓친 것이다."""
    return not (TITLE_DATE.search(rec["title"]) and rec["day_basis"] == "추정")


##################################################
# G3 사람 단정
##################################################

JUDGE = re.compile(
    r"(너는|당신은|글쓴이는|작성자는)[^.。!?]{0,30}(사람이다|사람입니다|성격이다|성격입니다)"
    r"|우울증|불안장애|성격 장애|문제가 있는 사람|의지가 약한 사람|게으른 사람"
)
NEUTRAL = "이 부분은 사람을 단정하지 않도록 표현을 바꿨습니다."


def judged(text):
    return bool(JUDGE.search(text or ""))


##################################################
# G4 실명
##################################################

# ponytail: 호칭이 붙은 두세 글자 이름만 잡는 단순 규칙. 호칭 없는 이름은 놓친다 → 사용자 이름 목록 입력으로 보완.
NAME = re.compile(r"(?<![가-힣])([가-힣]{2,3})(?=\s?(?:형|누나|오빠|언니|선배|후배|씨)|(?:이가|이랑|이는|이한테|이도|이를|이와|이네)(?![가-힣]))")
ENDINGS = set("에의을를는한던된와과서로고면며게")   # "오후에 선배", "졸업한 선배"처럼 이름이 아닌 말의 끝
NOT_NAMES = {"사람", "마음", "우리", "친구", "동생", "부모", "가족", "선배", "후배", "모두", "다들", "누구",
             "이번", "그것", "생각", "하루", "자기", "나랑", "같이", "혼자", "형제", "자매", "조원", "팀원", "순원",
             "순장", "목사", "전도사", "간사", "교수", "선생", "엄마", "아빠", "언니", "누나", "오빠", "형님"}


def find_names(text, extra=()):
    found = {m.group(1) for m in NAME.finditer(text or "") if m.group(1)[-1] not in ENDINGS} - NOT_NAMES
    found |= {n for n in extra if n and n in (text or "")}
    return sorted(found, key=lambda n: (-len(n), n))


def mask(text, names):
    for n in names:
        text = re.sub(re.escape(n), "○○", text or "")
    return text


if __name__ == "__main__":
    assert quote_in_source("배움은 기록할 때 비로소\n내 것이 된다.", "해 보니 확실히 다르다. 배움은 기록할 때 비로소 내 것이 된다.")
    assert not quote_in_source("배움은 기록이다", "배움은 기록할 때 내 것이 된다")
    names = find_names("민수 형이랑 밥을 먹었다. 지은이가 짚어 줬다. 마음이 무겁다. 선배랑 이야기했다. "
                       "오후에 선배랑 카페에 갔다. 졸업한 선배를 만났다. 하나님, 제가 가진 것을 먼저 보게 해 주세요.")
    assert names == ["민수", "지은"], names
    assert mask("민수 형은 먼저 물어봐 줬다", names) == "○○ 형은 먼저 물어봐 줬다"
    assert judged("글쓴이는 의지가 약한 사람이다") and not judged("다짐이 두 번 나왔고, 이후 반성이 한 번 나왔다.")
    assert not date_ok({"title": "3/27 금요일 일기", "day_basis": "추정"}) and date_ok({"title": "봄비", "day_basis": "추정"})
    print("gates ok")
