"""
app/service/safety/pseudonym.py

가명 처리. 사용자별 사람 목록(v8.json people: name · nicknames · relation)이 곧 가명 표다.
외부 AI(Studio · Solar)로 보내기 전 mask → 보내기 직전 assert_no_real_names → 받은 뒤 unmask.
"""

import re

# 받침 갈래: 없음 / ㄹ / 그 밖. 원래 말과 같은 갈래의 가명을 써서 조사(이/가 · 은/는 · 으로/로 …)를 그대로 둔다.
# ponytail: 이름 같은 가명이라 외부 AI 답에 우연히 같은 글자가 나오면 이름으로 되돌린다. 낱말과 겹치는 이름(가온 → 다가온)은 뺐다.
POOL = {
    "none": ["서아", "하유", "채아", "다예", "로하", "시우", "주아", "윤아", "지호", "도유"],
    "l": ["다솔", "예솔", "하솔", "은솔", "지율", "서율", "하율", "도율", "시율", "아율"],
    "other": ["도윤", "하준", "서진", "지안", "예준", "윤호", "은찬", "시온", "태민", "주원"],
}
PREFIX = ["", "백", "소", "편", "석", "탁", "봉", "견", "옥", "빈"]  # 모자라면 성을 붙인다(끝 글자가 같아 갈래 유지)

HONOR = "선생님|형님|형|누나|오빠|언니|선배|후배|씨|쌤"
SUFFIX = "이가|이랑|이는|이한테|이도|이를|이와|이네|이의|이에게|이처럼|이하고"   # 받침 있는 이름 뒤에 붙는 '이' + 조사
# 호칭 · 조사 앞에 와도 이름이 아닌 말. 1차 gates.NOT_NAMES + 소속 · 장소 말.
# ponytail: 낱말 목록이라 빠진 말은 새 이름 후보로 잡힌다(그래도 가명으로 가려 안전한 쪽).
NOT_NAMES = {"사람", "마음", "우리", "친구", "동생", "부모", "가족", "선배", "후배", "모두", "다들", "누구",
             "이번", "그것", "생각", "하루", "자기", "나랑", "같이", "혼자", "형제", "자매", "조원", "팀원", "순원",
             "순장", "목사", "전도사", "간사", "교수", "선생", "엄마", "아빠", "언니", "누나", "오빠", "형님",
             "학교", "회사", "동네", "교회", "직장", "대학", "동기", "군대", "옆집", "사촌", "동아리", "아저", "아가",
             "하나", "고양", "어린", "젊은", "늙은", "꼬맹", "막둥", "바둑", "멍멍", "야옹", "아는", "그분", "저분"}
ENDINGS = set("에의을를는한던된와과서로고면며게")   # "오후에 선배", "졸업한 선배"처럼 이름이 아닌 말의 끝
# 사람 이름도 되고 보통 낱말도 되는 말 → 물어볼 것
WORDY = {"하늘", "봄", "별", "바다", "솔", "나래", "은하", "사랑", "보람", "슬기", "기쁨", "다솜", "한결", "소망",
         "진주", "구슬", "여름", "가을", "겨울", "노을", "새벽", "빛나", "이슬", "초롱", "마루", "누리", "송이",
         "단비", "나비", "햇살", "온유", "믿음", "샛별", "아름"}
CAND = re.compile(rf"(?<![가-힣])([가-힣]{{2,3}})(?:(?P<h>\s?(?:{HONOR}))|(?:{SUFFIX})(?![가-힣]))")

# 조사 짝: (원래 글에 나올 수 있는 꼴, 받침 있는 말 뒤, 받침 없는 말 뒤). 이름 뒤 '이'(민준이가)도 함께 뗀다.
JOSA = [
    (("이에게", "에게"), "에게", "에게"), (("이한테", "한테"), "한테", "한테"), (("이하고", "하고"), "하고", "하고"),
    (("이처럼", "처럼"), "처럼", "처럼"), (("이랑", "랑"), "이랑", "랑"), (("이네", "네"), "네", "네"),
    (("이의", "의"), "의", "의"), (("이도", "도"), "도", "도"), (("이를", "을", "를"), "을", "를"),
    (("이는", "은", "는"), "은", "는"), (("이와", "과", "와"), "과", "와"), (("이다", "다"), "이다", "다"),
    (("이가", "이", "가"), "이", "가"), (("으로", "로"), "으로", "로"), (("아", "야"), "아", "야"),
]
JOSA_ALT = "|".join(sorted({v for vs, _, _ in JOSA for v in vs}, key=len, reverse=True))


def _cls(word):
    c = word[-1] if word else ""
    if not "가" <= c <= "힣":
        return "none"
    j = (ord(c) - 0xAC00) % 28
    return "none" if j == 0 else "l" if j == 8 else "other"


def _terms(p):
    return [t for t in [p.get("name"), *(p.get("nicknames") or [])] if t]


def _alt(words):
    return "|".join(map(re.escape, sorted(words, key=len, reverse=True)))


##################################################
# 새 이름 찾기
##################################################

def _candidates(text, known=()):
    if known:   # 이미 목록에 있는 말(곰돌이가 → 곰돌 ✗)은 지우고 찾는다
        text = re.sub(_alt(known), "·", text)
    out = []
    for m in CAND.finditer(text or ""):
        n = m.group(1)
        if n in NOT_NAMES or n[-1] in ENDINGS or (not m.group("h") and _cls(n) == "none"):
            continue   # '이가 · 이랑'꼴은 받침 있는 이름만(서아이가 ✗)
        if n not in out:
            out.append(n)
    return out


def find_new_names(text, people):
    """사람 목록에 없는 이름 후보 → {"auto": [이름], "ask": [{"name", "reason"}]}.
    reason: 동명이인(목록에 같은 이름이 둘 이상) · 별명(이미 있는 이름과 겹침) · 이름인지 낱말인지."""
    known = {t for p in people for t in _terms(p)}
    names = [p.get("name") for p in people]
    ask = [{"name": n, "reason": "동명이인"} for n in sorted({n for n in names if n and names.count(n) > 1 and n in text})]
    auto = []
    for c in _candidates(text, known):
        base = c[:-1] if c.endswith("이") else c
        if c in known:
            continue
        if c in WORDY:
            ask.append({"name": c, "reason": "이름인지 낱말인지"})
        elif any(base in k or k in c for k in known):
            ask.append({"name": c, "reason": "별명"})
        else:
            auto.append(c)
    return {"auto": auto, "ask": ask}


##################################################
# 가리기 · 되돌리기
##################################################

def mask(text, people):
    """이름 · 별명 · 새 이름 후보를 가명으로 → (가명 글, 바꿈 표 {가명: 원래 말}).
    한 사람의 같은 받침 갈래 말은 같은 가명을 쓴다. 호칭 · 조사가 붙어도 글자째 바꾼다."""
    text = text or ""
    found = find_new_names(text, people)
    persons = [_terms(p) for p in people] + [[c] for c in found["auto"] + [a["name"] for a in found["ask"]]]
    real = {t for ts in persons for t in ts}
    pools = {c: iter([pre + n for pre in PREFIX for n in POOL[c]]) for c in POOL}
    table, sub = {}, {}
    for terms in persons:
        given = {}
        for t in terms:
            if t not in text or t in sub:
                continue
            c = _cls(t)
            if c not in given:
                given[c] = next(n for n in pools[c] if n not in text and not any(n in r or r in n for r in real))
                # ponytail: 같은 사람의 이름과 별명이 한 글에 같이 나오면 되돌릴 때 먼저 나온 말(이름)로 맞춘다.
                table[given[c]] = t
            sub[t] = given[c]
    if sub:
        text = re.sub(_alt(sub), lambda m: sub[m.group()], text)
    return text, {p: t for p, t in table.items() if p in text}   # 다른 이름 속에만 있던 말(민준이 속 '준이')의 가명은 뺀다


def unmask(text, table):
    """가명 → 원래 말. 가명과 원래 말의 받침 갈래가 같아 외부 AI가 붙인 조사(이는/은 …)도 그대로 맞는다."""
    if not table or not text:
        return text
    return re.sub(_alt(table), lambda m: table[m.group()], text)


class RealNameLeak(ValueError):
    """외부로 나가는 요청에 실명이 남아 있다."""


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(x, (list, tuple, set)):
        for v in x:
            yield from _strings(v)


def assert_no_real_names(payload, people):
    """외부 요청(문자열 · dict · list 어디든)에 이름 · 별명이 하나라도 있으면 RealNameLeak. 실명은 예외 글에도 넣지 않는다."""
    terms = {t for p in people for t in _terms(p)}
    hits = {t for s in _strings(payload) for t in terms if t in s}
    if hits:
        raise RealNameLeak(f"외부 요청에 실명 {len(hits)}개가 남아 있습니다")


##################################################
# 사람 지우기
##################################################

def forget(text, person):
    """그 사람의 이름 · 별명을 관계 말("친구")로 바꾸고 문장은 남긴다. 호칭은 떼고 조사는 관계 말 받침에 맞춘다."""
    rel = person.get("relation") or "그 사람"
    c = _cls(rel)

    def put(m):
        j = m.group("j")
        for vs, b, n in JOSA:
            if j in vs:
                return rel + (n if c == "none" or (c == "l" and b == "으로") else b)
        return rel

    terms = _terms(person)
    if not terms:
        return text
    return re.sub(rf"(?:{_alt(terms)})(?:\s?(?:{HONOR}|님))?(?P<j>{JOSA_ALT})?", put, text or "")
