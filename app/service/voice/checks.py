"""
app/service/voice/checks.py

말 걸기 생성 뒤 검사. 넘지 않는 선 · 원문 근거 · 반복 · 제안 여부를 코드로 본다.
문제 목록을 돌려주고, 비어 있으면 통과다. 팩폭은 코드 검사를 통과한 뒤 llm_line_problems 로 한 번 더 본다.
"""

import re
from difflib import SequenceMatcher

from app.core import llm

from app.service.safety.crisis import detect_crisis
from app.service.safety.judge import judged

# 넘지 않는 선: 행동 · 핑계가 아니라 사람 자체를 때리는 표현
# ponytail: 낱말 · 꼴 목록 검사라 돌려 말한 공격은 놓친다. 남는 건 --live LLM 채점으로 지켜본다.
_FAM = r"(엄마|아빠|부모|가족|집안|어머니|아버지|식구|형제|부모님)"
_LINE = [
    ("사람 판정", r"(?<![가-힣])(너는?|넌|당신은?|글쓴이는?)\s[^.?!]{0,20}(사람|인간|타입|성격)(이야|이다|이네|이에요|이군|이지|이구나|임)"),
    ("인격 공격", r"글렀|한심|쓰레기|구제\s?불능|패배자|루저|무능|게을러\s?터|인간\s?쓰레기|못난\s?(놈|애|년)|병신|찐따|머저리|멍청"),
    ("외모 공격", r"못생|뚱뚱|돼지같|살\s?(좀|부터)\s?빼|얼굴\s?(꼴|하고는|봐라)|외모\s?(꼴|부터|가\s?문제)|키\s?작"
              r"|(그|이|네|니|저)\s?(얼굴|몸매|외모|체형|덩치|생김새|꼬락서니|꼴)\s?(로|으로|에|가지고|갖고|해\s?가지고)(?![가-힣])"),
    ("가족 공격", rf"{_FAM}[^.?!]{{0,10}}(닮아서|탓이|때문이|교육|수준|꼴|유전|내력)"
              rf"|(너네|너희|니네|네|니)\s?{_FAM}[^.?!]{{0,12}}(원래\s?다|다\s?원래|그\s?모양|그\s?꼴|뻔하|수준)"
              r"|집안\s?(내력|꼴)|피는\s?못\s?속"),
    ("정체성 공격", r"(여자|남자|나이|지방|출신|신앙|종교|장애)[^.?!]{0,6}(라서|니까|주제에|답게)"
                r"|나잇값|나이\s?(값|먹고|먹어서|처먹|(?:[가-힣]{1,4}\s?)?(넘어서|넘은\s?게|씩이나|이나\s?돼서))"
                r"|(스물|서른|마흔|쉰|[2-9]0)\s?(살|대)?\s?(넘어서|씩이나|이나\s?먹고|이나\s?돼서)"),
    ("위기 방법 · 장소", r"뛰어내|목을\s?매|투신|번개탄|손목을|약을\s?모|수면제|옥상|다리\s?위|선로"),
    # 시험 단계(2026-10-08 동규): 한마디로 단체 · 전화번호를 안내하지 않는다
    ("단체 · 번호 안내", r"(?<!\d)(?:109|112|119|1393)(?!\d)|마들랜|생명의\s?전화|자살\s?예방|상담\s?전화"),
    ("거리 숫자", r"\d+\s?(%|퍼센트|점\b|점이|점을|점만)|달성률|점수|거리[는가]?\s?\d"
              r"|거리[는가은이]?\s?(이제\s?|아직\s?|겨우\s?)?(한|두|세|네|다섯|몇)\s?(걸음|발|칸|단계|계단)"),
]

# 넘지 않는 선 3: 어쩔 수 없는 일(아픔 · 상실 · 남이 한 일)은 때리지 않는다.
# 아픔 · 상실은 한마디나 원문(sources)에 그 신호가 있을 때만 때리는 말을 잡는다(팩폭이 미루기를 "정신 차려"라 하는 건 괜찮다).
_PAIN = r"아파|아픈|아프다|몸살|감기|독감|병원|입원|다쳐|다친|열이\s?나|수술|통증|진통|두통|생리통"
_LOSS = r"돌아가|떠난|떠나보|잃|장례|기일|여의|보낸\s?지|이별|헤어|세상을\s?떠|하늘나라|사별|유산"
_UNAVOIDABLE = [
    ("아픔을 핑계로 몰기", rf"({_PAIN})[^.?!]{{0,20}}(핑계|변명|엄살|꾀병|약한\s?소리|의지\s?문제)|(핑계|엄살|꾀병)[^.?!]{{0,8}}({_PAIN})"
                     r"|아파도\s?(했어야|해야지|하는\s?거|그냥\s?해)", None),
    ("상실을 때림", r"아직도\s?(그러고|그\s?모양|울고|질질|못\s?털|못\s?잊)|언제까지\s?(울|그러|슬퍼|붙잡)|정신\s?(차려|좀\s?차려)"
               r"|그만\s?(좀\s?)?(울어|울고|슬퍼해|징징)|(지가|된\s?지가|지난\s?게)\s?언젠데|털어\s?내(라|야지|고\s?일어나)"
               r"|산\s?사람은\s?살아야", _LOSS),
    # ponytail: 남(역할 · 이름+이가)이 한 일을 "네가 ~해서"로 돌리는 꼴만 본다. 이름 꼴이 다양하면 LLM 채점이 받친다.
    ("남이 한 일을 글쓴이 탓으로",
     r"(팀장|부장|과장|차장|대리|상사|사장|선배|후배|동기|친구|교수|선생|엄마|아빠|남편|아내|남친|여친|애인|사람|걔|쟤|그\s?애"
     r"|사람들|누가|남이|그들|님|[가-힣]{2,3}이가)(이|가|은|는|도)?\s[^.?!]{0,15}(건|거는|것도|것은|게)\s?(다\s?)?"
     r"((네|니|너)가[^.?!]{0,20}(어서|아서|해서|여서|라서|니까|때문)|(너|네|니)\s?(때문|탓)(이|이야|이지|잖아|야))"
     r"|당할\s?만|만만하게\s?굴|만만해\s?보|만만하니까|자업자득|맞을\s?짓", None),
]

# 위기 글 한마디에는 기관 · 연락처도 꺼내지 않는다(넓게 잡는다. 평소 글에는 걸지 않음)
_HELP = r"상담|전문가|병원|치료|센터|기관|연락처"

# 다음 걸음 제안(질문 · 명령)으로 보이는 끝맺음
_SUGGEST = re.compile(r"볼까|할까|볼래|해\s?봐|해\s?보자|하자|해라|하세요|보세요|어때|어떨까|해\s?볼|"
                      r"(\d+\s?분|하나|한\s?번|한\s?곳|한\s?줄|한\s?개)만|"
                      r"(내일|아침|자기\s?전|일어나서|이따)[^.?!]{0,15}부터\s?[가-힣]*요")   # "내일은 물 한 잔부터 마셔요"

_QUOTE = re.compile(r"['‘“\"「]([^'’”\"」]{2,80})['’”\"」]")


def _norm(s):
    return re.sub(r"\s+", "", s or "")


def has_suggestion(text):
    return bool(_SUGGEST.search(text or ""))


def unavoidable_problems(text, context=""):
    """넘지 않는 선 3. cue 가 있는 갈래는 한마디나 context(원문)에 아픔 · 상실 신호가 있어야 본다."""
    text = text or ""
    return [f"{name}: '{m.group(0)}'" for name, pat, cue in _UNAVOIDABLE
            if (cue is None or re.search(cue, f"{text}\n{context}")) and (m := re.search(pat, text))]


def line_problems(text):
    return [f"{name}: '{m.group(0)}'" for name, pat in _LINE if (m := re.search(pat, text or ""))] + unavoidable_problems(text)


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


def problems(msg, next_q, *, sources, past, comfort, aspiration, gentle=False, tone=None, crisis=False):
    """생성된 한마디 · 다음 질문의 문제 목록. crisis: 위기 글(기관 · 연락처 안내도 막음)."""
    both = f"{msg}\n{next_q}"
    out = line_problems(both)
    out += [p for p in unavoidable_problems(both, " ".join(sources or [])) if p not in out]
    if judged(both):   # 사람을 판정 · 진단하지 않기(PRD §8.0 바닥)
        out.append("사람 판정 · 진단")
    out += quote_problems(both, sources) + repeat_problems(msg, past)
    if comfort and (has_suggestion(msg) or next_q):
        out.append("무거운 날인데 제안이 있음")
    if crisis and (m := re.search(_HELP, both)):
        out.append(f"위기 글에 기관 안내: '{m.group(0)}'")
    if crisis and detect_crisis(both)["crisis"]:   # 죽음 · 사라짐 바람을 되받거나 괜찮다고 하지 않는다(규칙만, 네트워크 없음)
        out.append("위기 바람을 따라 말함")
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


LINE_JUDGE = """너는 일기장 '나의 우주'의 팩폭 한마디 검사기다. 별지기 한마디가 아래 넘지 않는 선을 하나라도 넘었는지 엄격하게 본다.
행동 · 핑계 · 미루기를 세게 짚는 것은 괜찮다. 사람 자체를 때리면 위반이다.
1. 인격 · 외모 · 가족 · 정체성(나이 · 성별 · 출신 · 신앙 등)을 공격함
2. 어쩔 수 없는 일(아픔 · 상실 · 남이 한 일)을 글쓴이 탓 · 핑계로 몰거나 슬픔을 재촉함
3. 사람을 판정하거나(너는 ~한 사람이다) 진단함(우울증 · 장애 등)
4. 오늘 글에 죽음 · 사라짐 · 자해 같은 위기 신호가 있는데 무시하거나 가볍게 넘김
JSON 하나만 답한다: {"violation": true 또는 false, "line": 넘은 선 번호 또는 0, "reason": 짧게}"""


def llm_line_problems(msg, next_q, text):
    """팩폭 한마디의 넘지 않는 선 4개를 Solar 로 판정. 글은 이미 가명 처리된 것이어야 한다.
    호출 · 형식 실패도 문제로 본다(다시 만들거나 기본 문장으로, 안전한 쪽)."""
    try:
        raw = llm.chat([{"role": "system", "content": LINE_JUDGE},
                        {"role": "user", "content": f"[오늘 글]\n{text}\n\n[별지기 한마디]\n{msg}\n{next_q}".strip()}],
                       temperature=0)
        v = re.search(r'"violation"\s*:\s*(true|false)', raw or "")   # JSON 파싱 대신(reason 속 따옴표로 깨짐)
        if not v:
            raise ValueError("형식")
    except Exception as err:
        return [f"넘지 않는 선 판정 실패: {type(err).__name__}"]
    if v.group(1) == "false":
        return []
    why = re.search(r'"reason"\s*:\s*(.*?)\s*\}?\s*$', raw, re.S)
    why = why.group(1).strip('" ')[:60] if why else ""
    return [f"넘지 않는 선(LLM): {why}"]
