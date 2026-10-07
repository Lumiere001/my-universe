"""
app/service/safety/crisis.py

위기 감지와 돌봄 응답. 놓치지 않는 쪽(재현율)을 우선한다: 애매하면 위기로 본다.
다만 "배고파 죽겠다 · 과제가 날 죽인다" 같은 관용 표현과 남 이야기 · 뉴스 · 영화 줄거리는 거른다.
감지 낱말은 여기에만 둔다(v8.json 에 넣지 않음, v8.json crisis.trigger).
llm=True 면 규칙이 놓친 글을 Solar 로 한 번 더 본다(가명 처리한 글만 보낸다).
"""

import re

from app.core import llm as _llm
from app.service.safety.pseudonym import assert_no_real_names, mask, unmask

# 강한 신호: 하나만 있어도 위기. 띄어쓰기 · 문장부호 · 숫자를 지운 글(_squash)에 건다.
STRONG = {
    "직접 표현": r"자살|자해|죽(?:고|구|꼬)(?:싶|십|시퍼|시프|파)|주꼬싶|죽어버리(?:고|구)싶|죽어야겠|죽으려고|죽을까(?!봐|바)"
             r"|죽는게나을|죽는편이나|목숨을?끊|생을마감|스스로목숨|극단적인?선택|극단선택|손목을?긋"
             r"|뛰어내리(?:고싶|려고)|뛰어내릴까|뒤지고싶|디지고싶|뒤져버리고|유서",
    "삶을 끝내고 싶음": r"살고싶지않|살기싫|그만살고|더는?살고싶지|살아있기싫|살아서뭐해|살아야할이유|살이유가없|사는게싫"
                  r"|사는게의미없|사는게무의미|삶을끝내|인생을끝내|생을끝내|모든걸끝내|모든것을끝내|전부끝내고싶"
                  r"|(?:삶|인생|모든것|모든게|이모든게)이?끝(?:났|나버렸)으면",
    "사라지고 싶음": r"사라지고싶|없어지고싶|증발하고싶|소멸하고싶|영원히잠들|깨어나지않았으면|눈을?뜨지않았으면|내일이안왔으면"
                r"|안태어났으면|태어나지말았|태어나지않았으면|(?:저를|나를|날)데려가",
    # 돌려 말한 죽음 바람: 깨지 않기 · 눈 감기 · 사고라도 나기를 바람
    "수동적 죽음 바람": r"(?:안|못)(?:깼|깨어났|깨났|깨었)으면(?:좋|하|싶|바|해)|눈(?:이|을)?안(?:떠졌|떴)으면|깨(?:어나)?지(?:않|말)았으면(?:좋|하|싶|바|해)"
                   r"|(?:그만|영원히|영영|이대로|편히|아예)눈을?감(?:고싶|고파|았으면|아버리|고말)"
                   r"|차라리[가-힣]{0,15}(?:났으면|생겼으면|생겨서|다쳤으면|사라졌으면|없어졌으면|끝났으면)"
                   r"|(?:사고|큰일)(?:이|가)?라도(?:났|나버렸|당했)으면",
    # 떠난 사람에게 가고 싶음(편지 · 기도에 자주 나온다)
    "떠난 사람 곁으로": r"(?:곁|옆|품)(?:으로|에)가(?:고싶|고파|고만싶|야겠|려고|면좋|고프)"
                   r"|(?:하늘나라|천국|저세상|저승)(?:으로|에|로)?(?:가고싶|가고파|가야겠|가면좋|가려고|따라가)",
    "자해": r"(?:나를|날|나자신을|스스로를?|저를|내몸을?|제몸을?)(?:해(?:치|쳤|칠|쳐)|다치게)"
          r"|(?:내|제)?몸에상처를?(?:냈|내고싶|내버|내곤|내려)",
}
# "다 끝내고 싶다 · 다 끝났으면"은 같은 문장에 일 · 행사가 있으면 일 이야기로 본다.
END = r"다끝내(?:고싶|버리)|(?:다|그냥|전부)끝(?:났|나버렸)으면(?:좋|하|싶|바|해)"
TASK = re.compile(r"과제|숙제|고사|업무|공부|정리|청소|빨래|보고서|프로젝트|시험|학기|수업|회의|일정|방학|장마|공사|마감|야근|출장|발표"
                  r"|면접|휴가|여행|이사|작업|게임|경기|공연|겨울|여름|더위|추위|일(?:은|도|들|좀)?다끝")
# 영어는 낱말 경계가 필요해 띄어쓰기를 남긴 글(_words)에 건다.
ENGLISH = r"\bsuicid|\bkill ?my ?self|\bkms\b|\bwant(?:s)? to die|\bwanna die|\bend (?:my life|it all)|\bself ?harm" \
          r"|\bunalive|\bcut(?:ting)? my ?self|\bdon ?t (?:want to|wanna) live|\bwant to disappear"
# 약한 신호: 서로 다른 말이 둘 이상이면 위기(작별 · 무가치감 · 끝내고 싶음이 겹칠 때).
WEAK = r"그동안고마웠|그동안미안했|마지막인사|다들안녕|모두안녕|잘있어|먼저갈게|먼저간다|마지막편지|마지막으로남기" \
       r"|쓸모없|가치없|나같은건|나같은게|없는게나|없어도될|짐이되|짐만되|짐덩이|민폐만|실패작|살가치|아무도날?필요" \
       r"|내가없(?:으면|어지면)|나없(?:으면|어지면)" \
       r"|끝내고싶|끝내야겠|끝내버리|그만하고싶|포기하고싶|더는?못버티|더이상못버티|버틸수없|버틸힘이없|희망이없|의미가없|한계야|한계다" \
       r"|눈을?감고싶|무슨일이?라도(?:생겨|생겼|났)"
# 위기 낱말이 들어가도 위기가 아닌 합성어
NOT_CRISIS = re.compile(r"자살(?:예방|률|방지|골)|자해(?:예방|방지|공갈)|유서깊")
# 남 이야기 · 매체: 이런 문장은 "나"가 없으면 넘긴다.
OTHER = re.compile(r"뉴스|기사|영화|드라마|소설|웹툰|만화|책에서|주인공|등장인물|줄거리|다큐|통계|연예인|배우|가수|유튜브|노래(?!방)|가사|라디오"
                   r"|강의|수업|교육|캠페인|다고(?:했|하더|하던|말|들었|해서|하는|하길)|라고(?:했|하더)|싶대|싶다더|싶다네")
SELF = re.compile(r"(?<![가-힣])(?:나|난|내가|나는|나도|내|날|나를|저|전|저는|제가|저도|제)(?![가-힣])")
SENTENCES = re.compile(r"[^.!?。\n…]+")


def _squash(s):
    return re.sub(r"[^가-힣a-z]", "", s.lower())


def _words(s):
    return re.sub(r"[^a-z]+", " ", s.lower())


def detect_crisis(text, people=None, llm=False):
    """글 → {"crisis": bool, "signals": [{"type", "match"}]}.
    기본은 규칙만(네트워크 없음). llm=True 면 규칙이 위기가 아니라고 할 때 Solar 로 한 번 더 판정한다.
    people(사람 목록)로 가명 처리해 보내고, 없으면 새 이름 후보만 가린다. LLM 이 실패하면 규칙 결과 + "llm_error"."""
    r = _rules(text)
    if r["crisis"] or not llm or not (text or "").strip():
        return r
    try:
        crisis, reason, table = _ask_llm(text, people or [])
    except Exception as err:   # 네트워크 · 형식 · 실명 검사(RealNameLeak) 모두. 원문은 남기지 않는다.
        return {**r, "signals": r["signals"] + [{"type": "llm_error", "match": type(err).__name__}]}
    if crisis:
        return {"crisis": True, "signals": r["signals"] + [{"type": "llm", "match": unmask(reason, table)}]}
    return r


LLM_PROMPT = """너는 일기장 앱의 위기 신호 판정기다. 일기 글에서 글쓴이 자신에게 지금(요즘) 아래 가운데 하나라도 드러나는지 본다. 돌려 말하거나 완곡하게 · 은유로 쓴 것, 맞춤법 · 띄어쓰기가 틀린 것, 아주 짧은 글도 포함한다.
1. 자살 · 자해 생각, 죽고 싶음, 살고 싶지 않음, 살 이유 · 의미가 없어 삶을 그만두고 싶음
2. 죽음 · 사라짐 · 없어짐을 바람, 깨어나지 않거나 영원히 잠들기를 바람
3. 자기가 남에게 짐이라는 생각과 함께 자기가 없어지는 편이 낫다는 생각
4. 세상을 떠난 사람 곁으로 가고 싶음 · 따라가고 싶음
5. 스스로를 해침(때리기 · 상처 내기 · 아프게 하기 등, 돌려 말한 것 포함) 또는 해치고 싶음
6. 자기가 무가치하다는 생각과 함께 더는 버틸 수 없음 · 끝내고 싶음
위기가 아닌 것: 과장된 관용 표현(힘들어 죽겠다 같은 말), 시험 · 일 · 행사 · 계절 · 날씨가 끝나기를 바람, 피곤해서 푹 자고 싶음, 영화 · 책 · 노래 같은 작품의 줄거리, 다른 사람 이야기(글쓴이 자신의 바람이 아님), 이미 지나간 일이고 지금은 괜찮다고 분명히 말하는 회고.
판단이 애매하면 위기(true)로 답한다. 놓치는 것보다 지나치게 잡는 쪽이 낫다.
JSON 하나만 답한다: {"crisis": true 또는 false, "reason": "짧은 이유(20자 안팎, 원문을 길게 옮기지 않음)"}"""


def _ask_llm(text, people):
    masked, table = mask(text, people)
    msgs = [{"role": "system", "content": LLM_PROMPT}, {"role": "user", "content": masked}]
    # 시스템 글(고정 규칙)은 빼고 본다: 한 글자 이름(별)이 규칙 글 낱말에 걸리는 오탐 때문(docs/eval-v8.md).
    assert_no_real_names([m["content"] for m in msgs[1:]], people + [{"name": v} for v in table.values()])
    raw = _llm.chat(msgs, temperature=0) or ""
    # JSON 파싱 대신 낱말로 읽는다: Solar 가 reason 안에 따옴표를 그대로 넣어 JSON 이 깨지는 일이 있다.
    c = re.search(r'"crisis"\s*:\s*(true|false)', raw)
    if not c:
        raise ValueError("형식")
    r = re.search(r'"reason"\s*:\s*(.*?)\s*\}?\s*$', raw, re.S)
    return c.group(1) == "true", (r.group(1).strip('" ') if r else "")[:80], table


def _rules(text):
    signals, weak = [], set()
    for sent in SENTENCES.findall(text or ""):
        sq = NOT_CRISIS.sub("", _squash(sent))
        # ponytail: 문장 단위로 "나"가 있는지만 본다. "영화 보고 나는 울었다"처럼 과잉이 날 수 있으나 놓치는 쪽보다 낫다.
        if OTHER.search(sq) and not SELF.search(sent):
            continue
        for kind, pat in STRONG.items():
            signals += [{"type": kind, "match": m.group()} for m in re.finditer(pat, sq)]
        if not TASK.search(sq):
            signals += [{"type": "삶을 끝내고 싶음", "match": m.group()} for m in re.finditer(END, sq)]
        signals += [{"type": "영어", "match": m.group().strip()} for m in re.finditer(ENGLISH, _words(sent))]
        weak |= {m.group() for m in re.finditer(WEAK, sq)}
    crisis = bool(signals) or len(weak) >= 2
    if len(weak) >= 2:
        signals += [{"type": "겹친 약한 신호", "match": w} for w in sorted(weak)]
    return {"crisis": crisis, "signals": signals}


# 방법 · 장소는 절대 넣지 않는다. 109 · 마들랜 안내는 2026-10-08 보건복지부 · 복지로 공식 안내로 확인.
CARE = (
    "오늘 글을 읽으니 마음이 많이 무겁고 힘든 시간을 보내고 있는 것 같아요. 이렇게 적어 준 것만으로도 큰 용기예요.\n"
    "하나 직접 물어볼게요. 지금 스스로를 해치고 싶은 마음이 있나요? 지금 있는 곳은 안전한가요?\n"
    "혼자 버티지 않아도 괜찮아요. 지금 바로 이야기할 사람이 필요하면 연락해 주세요.\n"
    "· 자살예방 상담전화 109: 24시간 · 365일, 전화 요금 없음. 전화가 어려우면 109로 문자를 보내도 상담사와 이어져요.\n"
    "· SNS 상담 마들랜: 카카오톡에서 '마들랜'을 검색해 말풍선을 누르거나, 마들랜 앱에서 상담할 수 있어요(24시간).\n"
    "지금 당장 위험하다면 119나 112에 바로 연락해 주세요. 여기서 계속 들을게요."
)


SHORT = "· 아래 단추로 109 · 마들랜에 바로 이어질 수 있어요(24시간)."


def care_message(tone=None, resources=True):
    """위기면 말투와 상관없이(팩폭이어도) 평소 틀을 멈추고 이 글로 바꾼다. tone 은 일부러 쓰지 않는다.
    resources=False: 화면이 109 · 마들랜 단추(care.resources)를 따로 보여 줄 때. 자세한 안내 두 줄을 단추를 가리키는 한 줄로."""
    if resources:
        return CARE
    lines = [x for x in CARE.split("\n") if not x.startswith("· ")]
    return "\n".join(lines[:3] + [SHORT] + lines[3:])
