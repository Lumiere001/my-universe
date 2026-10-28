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
SURNAME = ["한", "윤", "오", "남", "강", "임", "장", "신", "권", "유", "문", "배"]   # 성 붙은 이름의 가명 성

# 직함 · 직분(민석 팀장님 · 지원 집사님). 낱말이기도 해서(오늘 이사 · 주일 대표 기도 · 간사해) '님' 없이는 이름다운 말만 잡는다.
TITLE = "팀장|과장|차장|부장|대리|사장|대표|실장|원장|주임|매니저|이사|본부장|교수|목사|전도사|간사|순장|집사|권사|장로"
HONOR = f"선생님|형님|형|누나|오빠|언니|선배|후배|씨|쌤|(?:{TITLE})님?"
SUFFIX = "이가|이는|이한테|이도|이를|이와|이의|이에게|이처럼|이하고"   # 받침 있는 이름 뒤에만 붙는 '이' + 조사(기간이가 ✗)
AMBI = "이랑|이네"   # 받침 있는 보통 낱말의 조사와 꼴이 같다(기간이랑 · 일정이네) → 이름다울 때만 자동 등록
# 호칭 · 조사 앞에 와도 이름이 아닌 말. 1차 gates.NOT_NAMES + 소속 · 장소 말.
# ponytail: 낱말 목록이라 빠진 말은 새 이름 후보로 잡힌다(그래도 가명으로 가려 안전한 쪽).
NOT_NAMES = {"사람", "마음", "우리", "친구", "동생", "부모", "가족", "선배", "후배", "모두", "다들", "누구",
             "이번", "그것", "생각", "하루", "자기", "나랑", "같이", "혼자", "형제", "자매", "조원", "팀원", "순원",
             "순장", "목사", "전도사", "간사", "교수", "선생", "엄마", "아빠", "언니", "누나", "오빠", "형님",
             "학교", "회사", "동네", "교회", "직장", "대학", "동기", "군대", "옆집", "사촌", "동아리", "아저", "아가",
             "하나", "고양", "어린", "젊은", "늙은", "꼬맹", "막둥", "바둑", "멍멍", "야옹", "아는", "그분", "저분",
             "다음", "담임"}
ENDINGS = set("에의을를는한던된와과서로고면며게")   # "오후에 선배", "졸업한 선배"처럼 이름이 아닌 말의 끝
# 사람 이름도 되고 보통 낱말도 되는 말 → 물어볼 것
WORDY = {"하늘", "봄", "별", "바다", "솔", "나래", "은하", "사랑", "보람", "슬기", "기쁨", "다솜", "한결", "소망",
         "진주", "구슬", "여름", "가을", "겨울", "노을", "새벽", "빛나", "이슬", "초롱", "마루", "누리", "송이",
         "단비", "나비", "햇살", "온유", "믿음", "샛별", "아름"}
CAND = re.compile(rf"(?<![가-힣])([가-힣]{{2,3}})(?:(?P<h>\s?(?:{HONOR}))|(?P<a>{AMBI})(?![가-힣])|(?:{SUFFIX})(?![가-힣]))")
# 받침 없는 이름 + 조사(지우가 · 지우는)는 "나무가 · 버스는"과 꼴이 같다. 같은 문장에 사람과 함께 쓰는 말이 있을 때만,
# 흔한 낱말을 빼고 "이름인지 낱말인지" 물을 후보로 올린다(가명으로는 가린다, 결정 3: 확실하지 않으면 가명).
# ponytail: 낱말 목록 · 동사 목록이라 빠진 말은 오탐(가명으로 가려짐)이 난다. 오탐이 거슬리면 COMMON 에 더한다.
LOOSE = re.compile(r"(?<![가-힣])([가-힣]{2,3})(?:가|는|랑|한테|에게|하고|도|를|와)(?![가-힣])")
PERSON_ACT = re.compile(r"연락|말을?\s?걸|말했|말해|물어|물었|얘기|이야기|전화|문자|카톡|만나|만났|웃었|웃어|울었|놀았|놀자"
                        r"|하자고|가자고|자고\s?했|싸웠|사과|고맙|고마워|고마운|미안|부탁|도와|챙겨|안아|칭찬|혼냈|화냈|약속|데리러|좋아해"
                        r"|보고\s?싶|생일|축하|위로|기다려|기다렸|불렀|답장")
COMMON = set("""아이 애기 아기 아내 여보 이모 고모 조카 부부 커플 기사 의사 교사 가수 배우 작가 기자 주부 아버지 어머니 할머니
아저씨 아줌마 할매 할배 고양이 강아지 냥이 오후 오전 어제 모레 요새 하루 과제 회의 휴가 나도 너도 저도 그녀 그대 얘기 이야기
소리 노래 커피 버스 기차 택시 문자 전화 메시지 부탁 사과 서로 아무 그게 이게 저게 거기 여기 저기 그거 이거 저거 나머지
차라리 혹시 제발 대리 교수 매니저 시누 그애 다시 바로 우선 그때 이때 처음 오래 자주 가끔 나중 이제 아마 정말 진짜 너무 조금
그냥 동료 상사 가게 남자 여자 먼저 많이 카페 서류 메모 리더 파트너 크루 스터디 파티 데이트 투어 우유 두유 고구마 과자 피자 쿠키 케이크 치즈 주스 바나나 토마토 지금""".split())
# 이름다움: 흔한 이름 글자(GIVEN) 두 개, 또는 성 + 그 두 글자. 보통 낱말에 잘 쓰는 글자(간 · 학 · 실 · 화 · 제 …)는 뺐다.
# ponytail: 글자 목록이라 드문 이름 글자는 놓친다(그 이름은 호칭 · '이가'꼴 · 행동 낱말 조사로만 잡힘). 놓치면 GIVEN 에 더한다.
GIVEN = set("가건겸경결규균근금길나남다단담대덕도동두라란람랑려련령로록루류륜률리린림만명무문미민범별병보봄봉비빈빛산상새샘"
            "서석선설섭성세소솔송수숙순슬승시신아안애양언연열영예옥온완우욱웅원월위유윤율은음인재정조종주준중지진찬창채천철"
            "청초춘충태하한해헌혁현형혜호홍환효후훈휘희흠")
SURNAMES = set("김이박최정강조윤장임한오서신권황안송류유전홍고문양손배백허남심노하곽성차주우구민진나지엄채원천방공현함변염여"
               "추도소석선설마길연위표명기반라왕금옥육인맹제모탁국어은편용예경봉사부")
# 조사 없이 이름 바로 뒤에 오는 사람 행동 낱말(오늘 철수 만났다 · 영희 생일)
ACT_NEAR = r"\s(?:만나|만났|생일|연락|전화|카톡|문자|말했|말해|얘기|이야기|답장)"
BARE = re.compile(rf"(?<![가-힣A-Za-z])([가-힣]{{2,3}})(?={ACT_NEAR})")
# 받침 있는 이름 + 보통 조사(수빈과 · 도현한테). 한테 · 에게는 사람에게만 쓰니 행동 낱말이 없어도 본다.
LOOSE_B = re.compile(r"(?<![가-힣])([가-힣]{2,3})(과|하고|한테|에게|의)(?![가-힣])")
# 영문 이름: 대문자로 시작하는 낱말 + 사람에게 붙는 조사 · 호칭, 또는 보통 조사 + 행동 낱말, 또는 바로 뒤 행동 낱말
EN = re.compile(rf"(?<![A-Za-z])([A-Z][a-z]{{1,14}})(?![A-Za-z])(?:(?P<p>이랑|랑|한테|에게|하고|이가|이는|이도|이네|\s?(?:{HONOR}|님))"
                rf"|(?P<g>[가는와과도를을의이은])(?![가-힣])|(?P<n>{ACT_NEAR}))?")

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

def _name_like(w):
    if w[-1] in ENDINGS | set("가다지요해"):   # 하다가 · 고민을 · 대해: 낱말 끝(조사 · 어미)
        return False
    if len(w) == 3:
        return w[0] in SURNAMES and _name_like(w[1:])
    return len(w) == 2 and w[0] in GIVEN and w[1] in GIVEN and w not in NOT_NAMES | COMMON


def _sentence(text, i):
    a = max(text.rfind(c, 0, i) for c in ".!?。\n") + 1
    b = min([j for j in (text.find(c, i) for c in ".!?。\n") if j >= 0] or [len(text)])
    return text[a:b]


def _candidates(text, known=()):
    """→ {이름: 확실한가}. 확실하면 자동 등록, 아니면 물어볼 것(가명으로는 가린다)."""
    text = text or ""
    if known:   # 이미 목록에 있는 말(곰돌이가 → 곰돌 ✗)은 지우고 찾는다
        text = re.sub(_alt(known), "·", text)
    out = {}
    for m in CAND.finditer(text):
        n = m.group(1)
        if n in NOT_NAMES or n[-1] in ENDINGS or (not m.group("h") and _cls(n) == "none"):
            continue   # '이가 · 이랑'꼴은 받침 있는 이름만(서아이가 ✗)
        if re.fullmatch(TITLE, (m.group("h") or "").strip()) and not _name_like(n):
            continue   # 님 없는 직함 앞의 이름답지 않은 말(오늘 이사 · 영업 팀장이)
        sure = _name_like(n) or not (m.group("h") or m.group("a"))
        if not sure and m.group("a") and n not in WORDY and not PERSON_ACT.search(_sentence(text, m.start())):
            continue   # 기간이랑 · 일정이네: 이름답지 않고 사람 행동 낱말도 없으면 낱말
        out[n] = out.get(n, False) or sure
    return out


def _loose(text, known=()):
    if known:
        text = re.sub(_alt(known), "·", text)
    out = []

    def add(n):
        if n not in out and n not in NOT_NAMES | COMMON:
            out.append(n)

    for sent in re.split(r"[.!?。\n]", text or ""):
        act = bool(PERSON_ACT.search(sent))
        for m in LOOSE.finditer(sent):
            n = m.group(1)
            if n.endswith("이") and _cls(n[:-1]) != "none":
                continue   # 받침 있는 이름 + '이'(서윤이가)는 CAND 가 맡는다
            if not (act or (m.group(0)[len(n):] in ("한테", "에게") and _name_like(n))):
                continue   # 행동 낱말이 없으면 사람에게만 쓰는 조사(한테 · 에게) + 이름다운 말만
            if _cls(n) == "none" and n[-1] not in ENDINGS | set("다요죠") and (len(n) == 2 or _name_like(n)):
                add(n)
        for m in LOOSE_B.finditer(sent):
            n, j = m.groups()
            if _cls(n) != "none" and _name_like(n) and (act or j in ("한테", "에게")):
                add(n)
        for m in BARE.finditer(sent):
            if _name_like(m.group(1)) and not PERSON_ACT.search(m.group(1)):
                add(m.group(1))
        for m in EN.finditer(sent):
            if m.group("p") or m.group("n") or (m.group("g") and act):
                add(m.group(1))
    return out


def find_new_names(text, people):
    """사람 목록에 없는 이름 후보 → {"auto": [이름], "ask": [{"name", "reason"}]}.
    reason: 동명이인(목록에 같은 이름이 둘 이상) · 별명(이미 있는 이름과 겹침) · 이름인지 낱말인지."""
    known = {t for p in people for t in _terms(p)}
    names = [p.get("name") for p in people]
    ask = [{"name": n, "reason": "동명이인"} for n in sorted({n for n in names if n and names.count(n) > 1 and n in text})]
    auto = []
    for c, sure in _candidates(text, known).items():
        base = c[:-1] if c.endswith("이") else c
        if c in known:
            continue
        if c in WORDY or not sure:
            ask.append({"name": c, "reason": "이름인지 낱말인지"})
        elif any(base in k or k in c for k in known):
            ask.append({"name": c, "reason": "별명"})
        else:
            auto.append(c)
    seen = set(auto) | {a["name"] for a in ask}
    ask += [{"name": n, "reason": "이름인지 낱말인지"} for n in _loose(text, known) if n not in seen]
    return {"auto": auto, "ask": ask}


##################################################
# 가리기 · 되돌리기
##################################################

def mask(text, people):
    """이름 · 별명 · 새 이름 후보를 가명으로 → (가명 글, 바꿈 표 {가명: 원래 말}).
    말 꼴마다 따로 가명을 줘서 되돌리면 글자째 같다(왕복 일치 우선). 받침 갈래는 원래 말과 같게(조사 유지).
    성 붙은 이름은 '가명 성 + 이름 가명'(고민석 → 한도윤, 민석 → 도윤)으로 이어 보이게 한다."""
    text = text or ""
    found = find_new_names(text, people)
    persons = [_terms(p) for p in people] + [[c] for c in found["auto"] + [a["name"] for a in found["ask"]]]
    real = {t for ts in persons for t in ts}
    pools = {c: iter([pre + n for pre in PREFIX for n in POOL[c]]) for c in POOL}
    sub = {}

    def fresh(cands):
        return next(n for n in cands if n not in text and n not in sub.values() and not any(n in r or r in n for r in real))

    for terms in persons:
        for t in sorted(terms, key=len):   # 짧은 말부터: 성 붙은 이름이 이름의 가명을 이어 받는다
            if t not in text or t in sub:
                continue
            base = next((b for b in terms if len(t) == len(b) + 1 and t.endswith(b) and b in sub), None)
            sub[t] = fresh(f + sub[base] for f in SURNAME if f != t[0]) if base else fresh(pools[_cls(t)])
    if sub:
        text = re.sub(_alt(sub), lambda m: sub[m.group()], text)
    return text, {p: t for t, p in sub.items() if p in text}   # 다른 이름 속에만 있던 말(민준이 속 '준이')의 가명은 뺀다


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

# 이름 자체가 가족을 부르는 말이면(엄마를 '엄마'로 바꾸면 그대로 남는다) 묶음 말로 바꾼다(2026-10-28 동규).
KIN = {"부모": ("엄마", "어머니", "어머님", "아빠", "아버지", "아버님"), "조부모": ("할머니", "할아버지"),
       "형제자매": ("형", "오빠", "누나", "언니", "동생", "남동생", "여동생")}


def forget_word(person):
    """지울 때 이름 · 별명 자리에 넣을 말: 가족을 부르는 이름이면 묶음 말, 아니면 관계 말, 관계가 비었거나 이름과 같으면 '그 사람'."""
    terms = set(_terms(person))
    rel = (person.get("relation") or "").strip()
    kin = next((g for g, ws in KIN.items() if terms & set(ws)), None)
    return kin or (rel if rel and rel not in terms else "그 사람")


def forget(text, person):
    """그 사람의 이름 · 별명을 forget_word 로 바꾸고 문장은 남긴다. 호칭은 떼고 조사는 바꾼 말의 받침에 맞춘다."""
    rel = forget_word(person)
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
