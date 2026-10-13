"""
app/service/chat

대화 Agent 규칙(WS19, PRD §6.1 대화 기준표 · §6.2 첫 만남 질문 · §5.1).
LLM 없이 정하는 것: 첫 말(서비스가 먼저 묻기) · 턴 상황 · 지난 기록 물음인지 · 마칠 때 · 말 검사 · 기본 문장.
Solar 로 보내는 글(프롬프트)도 여기서 만든다. 들어오는 글은 이미 가명 처리된 것이어야 한다(가명 · 보내기 · 위기 판정 ·
실명 검사는 app/agents/chat_graph.py).

말투 · 넘지 않는 선 · 위기 문장은 v8.json(voice 와 같은 곳)에서 읽고, 검사는 voice.checks.problems 를 그대로 쓴다.
voice.build_messages 를 그대로 쓰지 않는 이유: 그쪽은 일기 한 편에 건네는 한마디(다음 걸음 제안 · 질문 없음 규칙)라,
한 번에 질문 하나씩 이어 묻는 대화와 규칙이 다르다.
"""

import json
import re

from app.core import llm
from app.core.ontology import load
from app.service import voice
from app.service.safety import detect_crisis, find_new_names, judged
from app.service.voice import checks

# 운영 기본값(연구 근거 아님, 피드백으로 맞춘다)
WRAP_AFTER = 8          # 사용자 턴이 이만큼이면 정리를 제안한다(§6.1 대화를 마칠 때 — 붙잡지 않기)
SUMMARY_EVERY = 3       # '지금까지 정리'를 고쳐 쓰는 사용자 턴 간격
LONG_TURN = 300         # 이만큼 긴 말(녹음으로 한 긴 이야기, WS21)은 바로 정리에 담는다
TURNS_IN_PROMPT = 12    # 프롬프트에 넣는 최근 턴 수(정리가 그 앞을 들고 감)
PAST_IN_PROMPT = 5
MAX_REPLY = 300

FREE = "오늘 하루는 어땠어요? 떠오르는 것부터 편하게 이야기해 줘요."

# 끝낼 신호(§6.1 대화를 마칠 때). '그만두고 싶다'처럼 일 이야기는 걸리지 않게 말꼴을 좁게 잡는다.
END = re.compile(r"(이제|오늘은|여기서|그럼)\s?(그만|이만|여기까지|끝)|그만\s?(할게|할래|하자|얘기할래|말할래)|이만\s?(할게|잘게|갈게|줄일게)"
                 r"|(잘게|자러\s?(갈게|간다|가야))|다음에\s?(또|봐|얘기)|마무리\s?(할게|하자|해\s?줘)|정리해\s?(줘|주라|줄래)|여기까지\s?(할게|하자)")
# 지난 기록을 묻는 말: 때 · 지난 낱말 + 말한 것을 묻는 꼴, 묻는 끝맺음일 때만(그때 엄마가 뭐라고 했는지 모르겠어 ✗)
RECALL = re.compile(r"(예전|전에|지난번|지난주|지난달|작년|그때|언젠가|처음)[^?.!]{0,30}(뭐라고|뭐라|어떻게|무슨|뭘|뭐)\s?[^?.!]{0,12}"
                    r"(했|썼|적었|말했|얘기했|생각했)[^?.!]{0,6}(지|더라|었나|었어|나|니|까)\s?\??\s*$"
                    r"|(했었나|했던가|썼었나|적었었나|말했었나)\s?\??\s*$")
# 위기 턴의 답에 그 바람의 낱말을 다시 꺼내지 않는다(따라 말하기 금지, crisis.voice). 위로 문장에는 필요 없는 말들이다.
# ponytail: 낱말 목록이라 돌려 말한 되받기는 위기 한마디 판정(Solar)이 받친다.
ECHO = re.compile(r"사라지|사라진|없어지|없어졌|죽|끝내|끝나|곁으로|따라가|따라갈|잠들|깨어나지|눈을\s?감")
TIRED = re.compile(r"지쳤|지친|피곤|힘들|녹초|고된|고단|기진|탈진|버거")
# 무거운 날: 한마디의 슬픔 · 상실 말 + 대화에서 자주 나오는 마음 말(속상 · 우울 · 비참 · 절망)
HEAVY = re.compile(voice._SAD + "|" + voice._HEAVY_LOSS + r"|속상|우울|비참|절망")

# 기본 문장(두 번 다 검사에 걸렸을 때). 지난 답과 겹치지 않는 첫 문장을 쓴다.
SAFE = {
    "다정하게": ["그랬군요. 그때 마음이 어땠는지 조금 더 들려줄래요?", "이야기해 줘서 고마워요. 그다음엔 어떻게 됐어요?"],
    "담백하게": ["그랬군요. 조금 더 이야기해 줄래요?", "알겠어요. 그다음엔 어떻게 됐어요?"],
    "고양이처럼": ["그랬구냥. 조금 더 들려줄래냥?", "알겠다냥. 그다음엔 어떻게 됐냥?"],
    "팩폭": ["알겠어. 그래서 그다음엔 어떻게 됐어?", "그래. 조금 더 말해 봐."],
}
HEAVY_SAFE = {
    "다정하게": ["많이 무거운 하루였겠어요. 천천히 말해도 괜찮아요.", "그 마음, 그대로 들을게요. 하고 싶은 만큼만 이야기해 줘요."],
    "담백하게": ["무거운 하루였겠어요. 천천히 말해도 돼요.", "들을게요. 하고 싶은 만큼만 말해 줘요."],
    "고양이처럼": ["많이 무거웠겠다냥. 천천히 말해도 괜찮다냥.", "옆에서 들을게냥. 하고 싶은 만큼만 말해 줘냥."],
    "팩폭": ["오늘은 따질 날 아니야. 천천히 말해.", "들을게. 하고 싶은 만큼만 말해."],
}
NOT_FOUND = {
    "다정하게": "찾아봤는데, 그 이야기는 지난 기록에서 못 찾았어요. 기억나는 만큼 들려주면 오늘 기록에 담아 둘게요.",
    "담백하게": "지난 기록에서는 그 이야기를 못 찾았어요. 기억나는 만큼 말해 주면 오늘 기록에 담을게요.",
    "고양이처럼": "찾아봤는데 그 이야기는 지난 기록에 없었다냥. 기억나는 만큼 들려주면 오늘 기록에 담아 둘게냥.",
    "팩폭": "지난 기록엔 그 얘기 없어. 기억나는 만큼 말해. 오늘 기록에 담아 둘게.",
}
WRAP = {
    "다정하게": "여기까지 정리해 둘까요? 아래 '대화 마치고 정리하기'를 누르면 오늘 이야기를 일기로 정리해요.",
    "담백하게": "여기까지 정리해 둘까요? 아래 '대화 마치고 정리하기'를 누르면 일기로 정리해요.",
    "고양이처럼": "여기까지 정리해 둘까냥? 아래 '대화 마치고 정리하기'를 누르면 일기로 정리해 준다냥.",
    "팩폭": "여기까지 정리하자. 아래 '대화 마치고 정리하기' 눌러.",
}


def _tone(t):
    return t if t in SAFE else "다정하게"


##################################################
# 첫 말 · 상황 (LLM 없음)
##################################################

def opening(p, from_entry=None, invite=False):
    """서비스가 먼저 묻는 첫 말(§6.2, 즉석에서 지어내지 않음). p = 쓰기 화면 말풍선(app.api.write.prompt)의 결과.
    from_entry: '이 이야기 이어 하기'로 연 기록 {"day", "title", "summary", "quotes"}. invite: 되고 싶은 모습을 물을 때.
    → {"kind": "continue|vow|first|question|aspiration|free", "text", "sources": 별지기가 인용해도 되는 지난 글}"""
    if from_entry:
        name = from_entry.get("title") or (from_entry.get("summary") or "")[:40] or "그날"
        return {"kind": "continue", "text": f"{from_entry['day']}에 쓴 '{name}' 이야기를 이어 해 볼까요? 그 뒤로 어떻게 지냈어요?",
                "sources": list(from_entry.get("quotes") or [])}
    if p.get("vow"):
        v = p["vow"]["text"]
        return {"kind": "vow", "text": f"지난번에 적은 다짐, '{v}' 요즘은 어때요? 떠오르는 만큼 편하게 들려줘요.", "sources": [v]}
    if p.get("kind") == "first":
        return {"kind": "first", "text": p["text"], "sources": []}
    if p.get("kind") == "aspiration" and p.get("text"):
        return {"kind": "aspiration", "text": p["text"], "sources": []}
    if p.get("kind") in ("free", "weather") and p.get("text"):
        return {"kind": "question", "text": p["text"], "sources": []}
    if invite:
        return {"kind": "aspiration", "text": voice.INVITE, "sources": []}
    return {"kind": "free", "text": FREE, "sources": []}


def mask_people(people, texts):
    """가명 표 = 사람 목록 + 이 대화의 새 이름 후보(확실하지 않아도 가명으로 — 결정 3). 후보는 사람 목록에 등록하지 않는다
    (등록은 초안이 일기 그래프의 names 단계를 지날 때). 보내기 직전 실명 검사도 이 표로 한다."""
    found = find_new_names("\n".join(texts), people)
    return list(people) + [{"id": None, "name": n, "nicknames": [], "relation": ""}
                           for n in found["auto"] + [a["name"] for a in found["ask"]]]


# 지난 기록 물음에서 찾을 낱말이 아닌 말(때 · 묻는 말)
ASK_WORDS = ("예전", "전에", "지난", "작년", "그때", "언젠가", "처음", "얘기", "이야기", "뭐라", "어떻게", "무슨", "했", "썼", "적었",
             "말했", "생각", "내가", "제가", "나는", "기록", "일기")
HITS = 3


def sentence_hits(question, entries):
    """지난 기록 물음의 낱말(예: 축제 · 부스)이 든 기록 본문 문장 → past 모양(최근 기록부터 HITS 개). entries: [(기록 id, 날, 본문)]."""
    words = [w[:-1] if len(w) > 2 and w[-1] in "은는이가을를에의도와과랑" else w for w in re.findall(r"[가-힣]{2,}", question or "")]
    words = [w for w in words if not w.startswith(ASK_WORDS)]
    out = []
    for eid, day, text in sorted(entries, key=lambda x: x[1], reverse=True):
        for i, sent in enumerate(x.strip() for x in re.split(r"(?<=[.!?。])\s+|\n", text or "")):
            if sent and any(w in sent for w in words) and len(out) < HITS and not is_recall(sent):   # 예전 물음 문장은 기록 내용이 아님
                out.append({"id": f"{eid}-s{i}", "entry_id": eid, "day": day, "thought": "", "quote": sent})
    return out


def is_recall(text):
    """사용자가 지난 기록을 묻는 말인지(예: '예전에 진로 얘기 뭐라고 했지?')."""
    return bool(RECALL.search((text or "").strip()))


def should_wrap(text, user_turns, crisis=False):
    """마칠 때: 끝낼 신호가 있거나 턴이 길어짐. 위기 턴에는 정리를 권하지 않는다(위로가 먼저)."""
    return not crisis and (bool(END.search(text or "")) or user_turns >= WRAP_AFTER)


def situations(text, *, crisis=False, hour=None, recall=False, wrap=False, past=(), first=False, comfort_only=False):
    """이번 턴의 상황 이름(§6.1, 규칙만)."""
    out = ["위기"] if crisis else []
    if crisis or comfort_only or HEAVY.search(text or ""):
        out.append("무거운 날")
    if hour in voice.LATE_HOURS and TIRED.search(text or ""):
        out.append("고된 하루를 마친 밤")
    if first:
        out.append("첫 대화")
    if recall:
        out.append("지난 기록 물음")
    elif past and "무거운 날" not in out:
        out.append("지난 기록 떠올리기")
    if len(text or "") >= LONG_TURN and not crisis:   # 녹음 등으로 한 번에 들려준 긴 이야기(WS21)
        out.append("긴 이야기")
    if wrap:
        out.append("대화를 마칠 때")
    return out


LINES = {
    "무거운 날": "마음이 무거운 날: 공감과 있는 그대로 인정. 질문은 하나만. 해결책을 늘어놓거나 '힘내'를 쓰지 않는다.",
    "고된 하루를 마친 밤": "고된 하루를 마친 밤: 수고를 먼저 알아주고 짧게 묻는다. 하루를 평가하거나 할 일을 상기시키지 않는다.",
    "첫 대화": "첫 대화(기록 없음): 가볍고 한 단어로도 답할 수 있게 묻는다(예: '오늘 가장 오래 머문 곳은요?'). "
            "어떤 순간 · 왜 같은 깊은 개인사 질문이나 가치관 판단 질문은 하지 않는다.",
    "지난 기록 물음": "사용자가 지난 기록을 물었다: past 에서 맞는 기록을 찾아 날짜와 원문을 따옴표로 글자 그대로 옮겨 답한다. "
               "맞는 기록이 없으면 found 를 false 로 하고 지어내지 않는다(reply 는 빈 글).",
    "지난 기록 떠올리기": "past 는 지금 이야기와 닿을 수 있는 그 사용자의 지난 기록이다. 닿는 것이 있으면 '지난 (날짜)에 …라고 "
                  "하셨는데'처럼 날짜와 원문을 따옴표로 글자 그대로 옮겨 떠올리고, 오늘 이야기와 이어 묻는다(이 대화에서 이미 꺼낸 "
                  "기록은 다시 꺼내지 않는다). 억지로 잇지는 않고, 바뀐 생각을 잘못처럼 말하지 않는다.",
    "대화를 마칠 때": "대화를 마칠 때: 오늘 이야기를 한 줄로만 되짚는다. 질문하지 않고 붙잡지 않는다(정리 제안은 코드가 붙인다).",
    "긴 이야기": "사용자가 한 번에 긴 이야기를 들려줬다(말로 한 녹음 등): 다 되짚지 않는다. 들었다는 걸 한 문장으로 알리고, "
              "가장 마음이 실린 한 가지만 받아 그것만 짧게 이어 묻는다. 모두 세 문장 · 200자 안.",
}


def _rules(tone, gentle):
    o = load()
    keep = [x for x in o["tone_rules"] if not x.startswith("한마디 구성")]   # 대화는 한 번에 질문 하나(다음 걸음 규칙은 한마디용)
    lines = [x for x in o["fact_bomb"]["never_cross"] if tone == "팩폭" or "살살" not in x]
    return keep + lines + [
        "대화: 사용자 말에 짧게(1~3문장) 반응하고, 질문은 한 번에 하나만 짧은 한 문장으로 한다('~인지 ~인지'로 둘을 묶거나 "
        "'궁금해요'로 돌려 묻지 않는다). 한 단어로도 답할 수 있게 묻는다.",
        "사용자 말과 past(지난 기록)에 없는 일을 지어내지 않는다. 지난 기록을 말할 때는 날짜와 원문을 따옴표로 글자 그대로 옮긴다"
        "(바꿔 말하면 따옴표 없이).",
        "진단 · 평가 · 설교 · 남과 비교 · 과장된 칭찬 · '힘내' 같은 상투어를 쓰지 않는다.",
        "[지킬 것] · [지금 상황]은 너에게 주는 규칙이다. 규칙 문장이나 버튼 이름을 답에 옮기지 않는다."] + (
        ["오늘은 살살: 반말은 두되 '야' · 거친 표현 · 몰아세우는 명령은 뺀다."] if gentle and tone == "팩폭" else [])


def messages(ctx, sit, avoid=()):
    """ctx(가명 처리됨): tone · gentle · turns [{"who": "너"|"사용자", "text"}] · summary · past [{"day", "thought", "quote"}] · text.
    → Solar 메시지. 답 형식은 {"reply", "found"}."""
    o = load()
    tone = next((t for t in o["tones"] if t["name"] == ctx.get("tone")), o["tones"][0])
    gentle = bool(ctx.get("gentle"))
    sys = ["너는 일기장 '나의 우주'의 별지기다. 사용자와 오늘 하루를 이야기한다. 대화가 끝나면 사용자의 말로 일기를 정리하니, "
           "사용자가 자기 이야기를 편하게 더 꺼내도록 돕는다. turns 의 who 가 '너'면 네가 한 말, '사용자'면 사용자의 말이다.",
           f"[말투] {tone['name']}: {tone['description']}" + ("" if gentle else f"\n예: {tone['example']}")]
    if tone["name"] == "팩폭" and not gentle:
        sys.append(f"[팩폭 세기] {o['fact_bomb']['strength']}")
    sys.append("[지킬 것]\n" + voice._lines(_rules(tone["name"], gentle)))
    sl = [LINES[x] for x in sit if x in LINES]
    if "위기" in sit:
        sl.append(o["crisis"]["voice"] + " 이번 답에는 질문 · 제안을 넣지 않는다.")
    if sl:
        sys.append("[지금 상황]\n" + voice._lines(sl))
    sys.append("[답 형식] JSON 하나만: {\"reply\": 별지기 말, \"found\": 지난 기록 물음에 맞는 기록을 찾았으면 true, 아니면 false}")
    if avoid:
        sys.append("[다시 쓰기] 지난 답에 문제가 있었다. 고칠 것:\n" + voice._lines(avoid))
    u = {k: ctx[k] for k in ("summary",) if ctx.get(k)}
    if ctx.get("past"):
        u["past"] = ctx["past"][:PAST_IN_PROMPT]
    u["turns"] = (ctx.get("turns") or [])[-TURNS_IN_PROMPT:]
    user = "대화:\n" + json.dumps(u, ensure_ascii=False, indent=1) + "\n\n지금 사용자 말:\n" + (ctx.get("text") or "")
    return [{"role": "system", "content": "\n\n".join(sys)}, {"role": "user", "content": user}]


def parse(raw):
    """→ (답, found). JSON 이 깨지면 낱말로 읽는다. found 칸이 없으면(JSON 없이 글만 옴) None."""
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    if not d:   # 깨진 JSON · 'reply: … found: false' 꼴 · 글만
        raw = raw or ""
        f = re.search(r'"?found"?\s*[:：]\s*"?(true|false)', raw)
        r = re.search(r'"reply"\s*:\s*"(.*?)"\s*[,}]', raw, re.S)
        body = r.group(1) if r else re.sub(r'^\s*"?reply"?\s*[:：]\s*', "", raw[:f.start()] if f else raw)
        d = {"reply": body.strip().rstrip(","), "found": f and f.group(1) == "true"}
    found = d.get("found")
    return str(d.get("reply") or d.get("message") or "").strip(), None if found is None else found in (True, "true")


def problems(reply, *, sources, past_replies, tone=None, crisis=False, gentle=False, wrap=False):
    """대화 답의 문제 목록(비면 통과): 한마디와 같은 검사(넘지 않는 선 · 원문에 없는 인용 · 반복 · 사람 판정 · 위기) + 질문 하나만."""
    out = checks.problems(reply, "", sources=sources, past=past_replies, comfort=crisis, aspiration=False, gentle=gentle,
                          tone=tone, crisis=crisis)
    if crisis and (m := ECHO.search(reply or "")):
        out.append(f"위기 바람을 다시 꺼냄: '{m.group(0)}'")
    n = len(re.findall(r"[?？]", checks._QUOTE.sub("", reply or "")))   # 인용 속 물음표는 세지 않는다
    if n > (0 if crisis or wrap else 1):
        out.append(f"질문 {n}개(한 번에 하나만)")
    return out


def cited(text, past):
    """답에 따옴표 인용이 있고 모두 지난 기록(past) 원문에 글자 그대로 있는가."""
    return bool(checks._QUOTE.findall(text or "")) and not checks.quote_problems(
        text, [f"{p.get('thought', '')} {p.get('quote', '')}" for p in past or []])


def fallback(tone, past_replies=(), crisis=False, heavy=False):
    """기본 문장: 위기면 위로 문장(voice.CRISIS_SAFE), 무거운 날이면 듣는 말, 아니면 이어 묻는 말."""
    if crisis:
        opts = voice.CRISIS_SAFE.get(tone) or voice.CRISIS_SAFE["다정하게"]
    else:
        opts = (HEAVY_SAFE if heavy else SAFE)[_tone(tone)]
    return next((m for m in opts if not checks.repeat_problems(m, past_replies)), opts[0])


def recall_fallback(past, tone):
    """지난 기록 물음에 답을 못 만들었을 때: 찾은 기록이 있으면 그 원문 그대로, 없으면 못 찾았다고(지어내지 않음)."""
    p = next((p for p in past or [] if p.get("quote")), None)
    if not p:
        return NOT_FOUND[_tone(tone)]
    return f"{p['day']}에 '{p['quote']}'라고 적었어요."


def wrap_line(tone):
    return WRAP[_tone(tone)]


def respond(ctx):
    """한 턴의 별지기 답(가명 글로). ctx: messages 의 ctx + crisis · recall · wrap · hour · first · comfort_only ·
    sources(인용해도 되는 원문: 사용자 말 · 지난 생각 · 첫 말 근거) · past_replies(이 대화의 지난 별지기 말).
    → {"text", "kind": "reply|recall|wrap", "mode": "normal|comfort", "tone", "check_in", "found", "checks": [문제 개수…]}"""
    ctx = voice.soften(ctx)   # 위기 턴은 팩폭도 다정하게
    tone, crisis = ctx.get("tone"), bool(ctx.get("crisis"))
    sit = situations(ctx.get("text"), crisis=crisis, hour=ctx.get("hour"), recall=ctx.get("recall"), wrap=ctx.get("wrap"),
                     past=ctx.get("past"), first=ctx.get("first"), comfort_only=ctx.get("comfort_only"))
    kind = "wrap" if ctx.get("wrap") else "recall" if ctx.get("recall") else "reply"
    base = {"kind": kind, "mode": "comfort" if "무거운 날" in sit else "normal", "tone": tone,
            "check_in": voice.check_in_line(tone, ctx.get("past_check_ins")) if crisis or ctx.get("crisis_unsure") else ""}
    if kind == "recall" and not ctx.get("past"):   # 찾을 기록이 없으면 Solar 를 부르지 않고 없다고 답한다
        return {**base, "text": NOT_FOUND[_tone(tone)], "found": False, "checks": []}
    avoid, log, text, found = [], [], "", False
    for _ in (1, 2):
        text, found = parse(llm.chat(messages(ctx, sit, avoid), temperature=0.2 if kind == "recall" else 0.5))
        if kind == "recall":
            if found is None:   # JSON 없이 글만 옴: 지난 기록 원문을 그대로 인용했을 때만 찾은 것(인용 대조가 근거)
                found = cited(text, ctx.get("past"))
            if not found:   # 못 찾았으면 정해 둔 문장(답 글에 무엇을 적었든 쓰지 않음)
                break
        # 지난 기록 물음의 답은 지난 기록 원문만 인용할 수 있다(사용자의 물음을 기록처럼 인용하지 않게)
        src = [f"{p.get('thought', '')} {p.get('quote', '')}" for p in ctx.get("past") or []] if kind == "recall" \
            else ctx.get("sources") or []
        probs = problems(text, sources=src, past_replies=ctx.get("past_replies"), tone=tone,
                         crisis=crisis, gentle=bool(ctx.get("gentle")), wrap=kind == "wrap")
        if len(text) > MAX_REPLY:
            probs.append(f"너무 김({len(text)}자)")
        if checks._norm(text) == checks._norm(ctx.get("text")):   # 사용자 말을 그대로 되풀이한 답(--live 에서 본 꼴)
            probs.append("사용자 말을 그대로 되풀이함")
        if not probs and crisis:   # 위기 턴은 코드 검사를 지나도 위기 바람 동조를 Solar 로 한 번 더(한마디와 같음)
            probs = checks.llm_crisis_problems(text, "", ctx.get("text") or "")
        elif not probs and tone == "팩폭":
            probs = checks.llm_line_problems(text, "", ctx.get("text") or "")
        log.append(len(probs))
        if not probs:
            break
        avoid = probs
        text = ""
    if kind == "recall" and not found:
        text = NOT_FOUND[_tone(tone)]
    elif not text:   # 두 번 다 걸림 → 기본 문장(지어내지 않는 쪽)
        text = (recall_fallback(ctx.get("past"), tone) if kind == "recall" and not crisis
                else "" if kind == "wrap" else fallback(tone, ctx.get("past_replies"), crisis, "무거운 날" in sit))
    if kind == "wrap":
        text = f"{text}\n{wrap_line(tone)}".strip()
    return {**base, "text": text, "found": bool(found), "checks": log}


##################################################
# 지금까지 정리 · 일기 초안 (사용자 말만 근거)
##################################################

SUMMARY_SYS = ("너는 일기장 '나의 우주'의 정리 담당이다. 대화에서 사용자(나)가 한 말만 근거로 '지금까지 정리'를 3~5줄로 쓴다. "
               "앞 정리가 있으면 이어서 고쳐 쓴다. 별지기가 한 말 · 지난 기록 · 짐작은 넣지 않는다. 사용자가 쓴 표현을 살리고, "
               "평가 · 진단 · 조언 없이 1인칭(나)으로 쓴다. 별지기에게 한 물음('예전에 뭐라고 했지?')과 대화를 끝내는 말('이만 잘게요')은 "
               "넣지 않는다. 긴 이야기도 줄여서 모두 합쳐 400자 안. 정리 글만 답한다(JSON · 머리말 없이).")
DRAFT_SYS = ("너는 일기장 '나의 우주'의 정리 담당이다. 대화에서 사용자(나)가 한 말만 근거로 오늘의 일기 초안을 쓴다. "
             "1인칭(나)으로, 사용자가 쓴 표현 · 낱말을 되도록 그대로 살린다. 별지기의 말 · 질문, 지난 기록, 짐작 · 평가 · 조언은 넣지 않는다. "
             "사용자가 말한 마음(힘듦 · 슬픔 등)은 빼거나 누그러뜨리지 않고, 말한 날짜 · 사람 이름은 그대로 둔다. "
             "별지기에게 한 물음('예전에 뭐라고 했지?')과 대화를 끝내는 말('이만 잘게요')은 일기에 넣지 않는다. "
             "JSON 하나만: {\"title\": 짧은 제목(20자 안), \"text\": 일기 본문}")
MAX_SUMMARY = 600


def due_summary(user_turns, text):
    """'지금까지 정리'를 고쳐 쓸 때: 몇 턴마다, 또는 긴 이야기(녹음 등)가 들어왔을 때 바로."""
    return user_turns % SUMMARY_EVERY == 0 or len(text or "") >= LONG_TURN


def summarize(summary, user_texts):
    """가명 글 → 새 정리(가명). 사용자 말에 없는 인용 · 사람 판정이 있거나 비면 None(앞 정리를 그대로 둠).
    너무 길면 문장 끝에서 자른다(3분 녹음 이야기에서 600자를 넘어 정리가 비던 것 — 다시 쓰게 해도 Solar 는 830~950자로 답함, WS21 e2e)."""
    out = llm.chat([{"role": "system", "content": SUMMARY_SYS},
                    {"role": "user", "content": f"앞 정리:\n{summary or '(없음)'}\n\n사용자 말:\n" + voice._lines(user_texts)}],
                   temperature=0.3).strip()
    if len(out) > MAX_SUMMARY:   # ponytail: 뒷이야기는 화면 정리에서만 빠짐(초안은 사용자 말 전체로 만든다)
        keep = ""
        for x in re.split(r"(?<=[.!?。])\s+", out):
            if len(keep) + len(x) + 1 > MAX_SUMMARY:
                break
            keep = f"{keep} {x}".strip()
        out = keep
    if not out or len(out) > MAX_SUMMARY or judged(out) or checks.quote_problems(out, user_texts):
        return None
    return out


def draft_problems(text, user_texts, crisis=False):
    """일기 초안 검사: 비었거나, 사용자 말에 없는 인용, 사람 판정, 위기였던 대화인데 그 말이 빠짐."""
    out = [] if (text or "").strip() else ["빈 초안"]
    out += checks.quote_problems(text, user_texts)
    if judged(text):
        out.append("사람 판정 · 진단")
    if crisis and not detect_crisis(text)["crisis"]:
        out.append("위기였던 말이 빠짐")
    return out


def draft(user_texts, crisis=False, limit=8000):
    """가명 글 → {"title", "text"}(가명). 두 번 다 검사에 걸리면 사용자 말을 그대로 이은 글(지어낸 것 없음)."""
    avoid = []
    for _ in (1, 2):
        msgs = [{"role": "system", "content": DRAFT_SYS + ("\n[다시 쓰기] 고칠 것:\n" + voice._lines(avoid) if avoid else "")},
                {"role": "user", "content": "사용자 말:\n" + voice._lines(user_texts)}]
        raw = llm.chat(msgs, temperature=0.3)
        m = re.search(r"\{.*\}", raw or "", re.S)
        try:
            d = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            d = {}
        title, text = str(d.get("title") or "").strip()[:60], str(d.get("text") or "").strip()
        avoid = draft_problems(text, user_texts, crisis) + ([f"너무 김({len(text)}자)"] if len(text) > limit else [])
        if not avoid:
            return {"title": title, "text": text, "fallback": False}
    # ponytail: 사용자 말을 그대로 잇는다(글자 수 상한에서 자름). 긴 녹음이 상한을 넘으면 여러 편으로 나누는 일은 WS21 에서.
    return {"title": "", "text": "\n".join(user_texts)[:limit], "fallback": True}
