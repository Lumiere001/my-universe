"""
app/service/voice

말 걸기 생성(WS7): Solar 채팅으로 한마디와 다음 질문을 만든다.
말투 · 넘지 않는 선 · 상황 규칙 문장은 v8.json 에서 읽어 프롬프트를 조립하고, 만든 뒤 코드로 검사한다.
들어오는 글은 이미 가명 처리된 글이어야 한다(app/service/safety).

ctx (모두 선택, 없으면 기본값):
  tone            "다정하게" | "담백하게" | "고양이처럼" | "팩폭"
  text            오늘 글(가명 처리)
  summary         오늘 글 요약
  thoughts        [{"thought", "kind", "certainty", "quote"}]
  weather         마음 날씨 이름 또는 None
  addressee       "나" | "특정 인물" | "신"
  person_history  편지 상대와의 지난 기록 요약 목록
  written_at      쓴 시각(ISO 문자열 또는 datetime)
  past_messages   그 사용자의 지난 한마디 전체(오래된 것 → 최근)
  aspiration      {"said", "value", "obstacle", "if_then"} 또는 None
  reached         되고 싶은 모습에 닿은 순간 [{"quote", "note"}] (관측 Agent가 원문 근거로 찾은 것)
  commitments     [{"text", "state", "due", "overdue"}]  (열린 다짐 · 기한 지난 다짐)
  kept            오늘 지켜 낸 다짐 글 목록
  open_questions  남겨 둔 질문 글 목록
  heavy           글에 슬픔 · 상실이 드러남(관측 결과)
  crisis          위기 신호(WS4 safety)
  days_written    지금까지 쓴 날 수(0이면 첫 만남)
  weather_skipped 마음 날씨 질문을 건너뛴 적 있음
  aspiration_step 되고 싶은 모습 묻기 진행 중이면 답한 단계 수(0~3), 아니면 None
  aspiration_off  "그만 묻기" 또는 "이번엔 넘어가기" 뒤 아직 계기 없음
  settings        {"gentle": 오늘은 살살, "comfort_only": 오늘은 위로만, "suggest": "자주" | "가끔" | "안 함"}
"""

import json
import re
from datetime import datetime

from app.core import llm
from app.core.ontology import load
from app.service.voice import checks

# 운영 기본값(연구 근거 아님, 피드백으로 맞춘다)
LATE_HOURS = {23, 0, 1, 2, 3, 4}
LONG_TEXT = 700          # 늦은 밤 '길게' 쓰는 글자 수
SHORT_TEXT = 300         # 기분이 안 드러난 '짧은 글' 글자 수
COMPLEX_THOUGHTS = 6     # 생각이 이만큼 많거나, 질문 · 고민 중이 둘 이상이면 복잡한 날
ASPIRATION_AFTER_DAYS = 3
PAST_IN_PROMPT = 10

# 기록이 없을 때 쓰는 정해 둔 질문(PRD §6.2)
FIRST_QUESTIONS = ["오늘 하루를 한 단어로 하면요?", "오늘 가장 오래 머문 장소는 어디예요?"]
INVITE = "요즘 써 온 글을 보다가 궁금해졌어요. 되고 싶은 모습에 대해 잠깐 이야기해 볼까요? (넘어가도 괜찮아요)"

# 두 번 실패하면 쓰는 안전한 기본 문장 (말투 · 위로만 여부별)
SAFE = {
    ("다정하게", False): "오늘도 기록해 줘서 고마워요. 적어 둔 마음, 잘 읽었어요.",
    ("다정하게", True): "오늘 마음이 무거웠겠어요. 무거운 채로 있어도 괜찮아요. 적어 둔 것만으로 충분해요.",
    ("담백하게", False): "오늘 기록, 잘 받았어요.",
    ("담백하게", True): "오늘 기록 잘 받았어요. 오늘은 그대로 두어도 괜찮아요.",
    ("고양이처럼", False): "오늘도 기록해 줘서 고맙다냥. 잘 읽었다냥.",
    ("고양이처럼", True): "오늘은 마음이 무거웠겠다냥. 옆에 가만히 있을게냥.",
    ("팩폭", False): "오늘 쓴 거 잘 봤어. 기록한 건 너야. 오늘은 여기까지.",
    ("팩폭", True): "오늘은 따질 날 아니야. 쓴 걸로 충분해. 푹 쉬어.",
}


def _o():
    return load()


def _hour(ctx):
    w = ctx.get("written_at")
    if isinstance(w, str):
        try:
            w = datetime.fromisoformat(w)
        except ValueError:
            return None
    return w.hour if w else None


def _comfort_weathers():
    return {w["name"] for w in _o()["weather"] if w.get("comfort_only")}


def situations(ctx):
    """오늘의 상황 이름 목록(규칙, LLM 없음)."""
    s = ctx.get("settings") or {}
    text, thoughts = ctx.get("text") or "", ctx.get("thoughts") or []
    out = []
    if ctx.get("crisis"):
        return ["위기"]
    if ctx.get("weather") in _comfort_weathers() or ctx.get("heavy") or s.get("comfort_only"):
        out.append("무거운 날")
    if _hour(ctx) in LATE_HOURS and len(text) >= LONG_TEXT:
        out.append("늦은 밤 길게")
    if len(thoughts) >= COMPLEX_THOUGHTS or sum(
            t.get("kind") == "질문" or t.get("certainty") == "고민 중" for t in thoughts) >= 2:
        out.append("생각이 복잡한 날")
    if ctx.get("weather") == "흐림":
        out.append("쉼 권하기")
    a = ctx.get("addressee")
    if a == "신":
        out.append("기도")
    elif a == "특정 인물":
        out.append("편지")
    if ctx.get("reached"):
        out.append("되고 싶은 모습에 닿음")
    if ctx.get("kept"):
        out.append("다짐을 지켜 냄")
    if "무거운 날" not in out and any(c.get("overdue") or c.get("state") == "열림" for c in ctx.get("commitments") or []):
        out.append("다짐 안부")
    if s.get("gentle") and ctx.get("tone") == "팩폭":
        out.append("오늘은 살살")
    return out


def _suggest(ctx, sit):
    """이번 한마디에 다음 걸음 제안을 넣을지. 무거운 날 · 쉼 권하기 · '안 함'이면 빼고, '가끔'은 지난번에 했으면 뺀다."""
    if "무거운 날" in sit or "쉼 권하기" in sit:
        return False
    freq = (ctx.get("settings") or {}).get("suggest", "가끔")
    if freq == "안 함":
        return False
    past = ctx.get("past_messages") or []
    return freq == "자주" or not (past and checks.has_suggestion(past[-1]))


def next_question_kind(ctx):
    """다음 질문의 종류(규칙, LLM 없음).
    "" | "aspiration"(4단계 이어 묻기) | "weather" | "first" | "commitment" | "open_question" | "aspiration_invite"
    """
    sit = situations(ctx)
    if "위기" in sit or "무거운 날" in sit:
        return ""
    step = ctx.get("aspiration_step")
    if step is not None and step < len(_o()["aspiration"]["ask_steps"]) and not ctx.get("aspiration_off"):
        return "aspiration"
    first = not ctx.get("days_written")
    no_mood = not ctx.get("weather") and not any(t.get("kind") == "감정" for t in ctx.get("thoughts") or []) \
        and len(ctx.get("text") or "") < SHORT_TEXT
    if not ctx.get("weather_skipped") and not ctx.get("weather") and (first or no_mood):
        return "weather"
    if first:
        return "first"
    if any(c.get("overdue") for c in ctx.get("commitments") or []):
        return "commitment"
    if ctx.get("open_questions"):
        return "open_question"
    if not ctx.get("aspiration") and not ctx.get("aspiration_off") and ctx.get("days_written", 0) >= ASPIRATION_AFTER_DAYS:
        return "aspiration_invite"
    return ""


def base_question(kind, ctx):
    """정해 둔 질문 글(있는 종류만). 말투는 LLM이 입힌다."""
    if kind == "aspiration":
        return _o()["aspiration"]["ask_steps"][ctx["aspiration_step"]]["question"]
    if kind == "weather":
        ws = " / ".join(f"{w['name']}({' · '.join(w['words'])})" for w in _o()["weather"])
        return f"오늘 마음 날씨는 어디에 가까워요? {ws}"
    if kind == "first":
        past = " ".join(ctx.get("past_messages") or [])
        return next((q for q in FIRST_QUESTIONS if q not in past), FIRST_QUESTIONS[0])
    if kind == "aspiration_invite":
        return INVITE
    return ""


def _lines(xs):
    return "\n".join(f"- {x}" for x in xs)


def build_messages(ctx, kind, sit, suggest, avoid=()):
    """v8.json 의 말투 · 규칙 문장으로 시스템 프롬프트를, ctx 로 사용자 입력을 만든다."""
    o = _o()
    tone = next((t for t in o["tones"] if t["name"] == ctx.get("tone")), o["tones"][0])
    fb = o["fact_bomb"]
    lines = [x for x in fb["never_cross"] if tone["name"] == "팩폭" or "살살" not in x]  # 살살은 팩폭 버튼
    rules = list(o["tone_rules"]) + lines + list(o["aspiration"]["reached"]) + [
        "되고 싶은 모습은 오늘 글과 닿을 때만 꺼낸다. '되고 싶다면서 왜'처럼 그 말로 몰아세우지 않는다.",
        "[지킬 것] · [오늘 상황]은 너에게 주는 규칙이다. 규칙 문장이나 버튼 이름을 한마디에 옮기지 않는다."]
    gentle = "오늘은 살살" in sit
    sys = ["너는 일기장 '나의 우주'의 별지기다. 사용자가 오늘 쓴 일기에 한마디를 건넨다.",
           f"[말투] {tone['name']}: {tone['description']}" + ("" if gentle else f"\n예: {tone['example']}")]
    if tone["name"] == "팩폭" and not gentle:  # 살살인 날은 센 예시 · 세기 문장을 빼야 실제로 낮아진다
        sys.append(f"[팩폭 세기] {fb['strength']}")
    sys.append("[지킬 것]\n" + _lines(rules))

    # 상황별 지시. v8.json 에 있는 문장은 거기서 읽고, 없는 상황(늦은 밤 · 복잡한 날 · 쉼)만 여기 적는다.
    sl = []
    if "무거운 날" in sit:
        sl.append(next(r for r in o["weather_rules"] if "비 · 천둥" in r))
        sl.append("마음이 무거운 날: 공감과 있는 그대로 인정만. 해결책 · 할 일 · 다음 걸음 제안 없이, '힘내' 같은 상투어 없이.")
    if "늦은 밤 길게" in sit and "무거운 날" not in sit:
        sl.append("늦은 밤에 길게 쓰는 중: 쓴 것을 알아주고, 내일 일정(아침에 일어날 일)을 가볍게 떠올리게 해 오늘은 여기까지 쓰고 쉬게 한다.")
    if "생각이 복잡한 날" in sit:
        sl.append("생각을 정리하려고 쓴 날: 적으며 정리한 것을 비춰 준다. 지금의 생각과 감정은 자고 나면 옅어질 수 있으니 적어 둔 것으로 충분하다고, 더 깊이 빠지지 않게 한다.")
    if "쉼 권하기" in sit:
        sl.append("지친 날: 수고를 먼저 알아주고 쉼을 권한다. 할 일을 상기시키지 않는다.")
    for h in o["addressee_handling"]:
        if h["name"] in sit:
            sl.append(f"{h['name']}({h['addressee']}에게 쓴 글): {h['do']} 하지 않을 것: {h['dont']}.")
    if "다짐 안부" in sit:
        sl += [n for n in o["states"]["다짐"]["notes"] if "안부" in n]
        sl.append("다짐의 안부는 부드럽게 묻고 추궁하지 않는다.")
    if "다짐을 지켜 냄" in sit:
        sl.append("오늘 지켜 낸 다짐을 기록의 행동으로 알아준다.")
    if "되고 싶은 모습에 닿음" in sit:
        sl.append("되고 싶은 모습에 닿은 순간을 원문을 짧게 따옴표로 인용해 인정한다.")
    if "오늘은 살살" in sit:
        sl.append(next(f"오늘은 살살: {f['changes']}" for f in o["feedback"] if f["name"] == "오늘은 살살")
                  + " 반말은 두되 '야' · 거친 표현 · 몰아세우는 명령은 빼고, 다음 걸음은 권하는 말로.")
    sl.append("이번 한마디에는 작은 다음 걸음을 질문으로 하나 넣는다(팩폭은 명령형 가능)." if suggest
              else "이번 한마디에는 다음 걸음 제안을 넣지 않는다(질문 · 명령 · '~만 해 보기' 모두 없이).")
    sys.append("[오늘 상황]\n" + _lines(sl))

    nq = {"commitment": "next_question 에는 기한 지난 다짐의 안부를 묻는 질문 하나를 쓴다.",
          "open_question": "next_question 에는 남겨 둔 질문을 오늘 글과 이어 묻는 질문 하나를 쓴다."
          }.get(kind, "next_question 은 빈 글로 둔다.")
    sys.append("[답 형식] JSON 하나만: {\"message\": 한마디(2~4문장), \"next_question\": 다음 질문}. "
               "따옴표 안에는 아래 원문을 글자 그대로 옮긴다(바꿔 말하면 따옴표 없이). 지난 한마디와 표현을 겹치지 않는다. " + nq)
    if avoid:
        sys.append("[다시 쓰기] 지난 답에 문제가 있었다. 고칠 것:\n" + _lines(avoid))

    u = {k: ctx.get(k) for k in ("summary", "weather", "addressee", "reached", "commitments",
                                 "kept", "open_questions", "person_history") if ctx.get(k)}
    if ctx.get("reached"):  # 되고 싶은 모습은 닿은 날에만 보여 준다(다른 날엔 그 말로 몰아세우기 쉬움)
        u["aspiration"] = ctx.get("aspiration")
    u["thoughts"] = [{k: t[k] for k in ("thought", "kind", "quote") if t.get(k)} for t in ctx.get("thoughts") or []]
    if ctx.get("written_at"):
        u["written_at"] = str(ctx["written_at"])
    u["past_messages"] = (ctx.get("past_messages") or [])[-PAST_IN_PROMPT:]
    user = "오늘 글:\n" + (ctx.get("text") or "") + "\n\n참고:\n" + json.dumps(u, ensure_ascii=False, indent=1)
    return [{"role": "system", "content": "\n\n".join(sys)}, {"role": "user", "content": user}]


def _parse(raw):
    m = re.search(r"\{.*\}", raw or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    if not d and raw:
        d = {"message": raw.strip()}
    return str(d.get("message") or "").strip(), str(d.get("next_question") or "").strip()


def _sources(ctx):
    return ([ctx.get("text") or ""] + [r.get("quote") or "" for r in ctx.get("reached") or []]
            + [(ctx.get("aspiration") or {}).get("said") or ""]
            + [c.get("text") or "" for c in ctx.get("commitments") or []] + list(ctx.get("kept") or [])
            + list(ctx.get("open_questions") or []) + list(ctx.get("person_history") or []))


def generate(ctx):
    """ctx → {"message", "next_question", "mode": "normal" | "comfort" | "care", "checks", "situations", "next_kind"}.
    위기면 LLM을 부르지 않고 mode "care" 만 돌려준다(돌봄 문장은 safety.care_message, WS5가 잇는다).
    """
    sit = situations(ctx)
    if "위기" in sit:
        return {"message": "", "next_question": "", "mode": "care", "checks": [], "situations": sit, "next_kind": ""}
    comfort = "무거운 날" in sit
    kind = next_question_kind(ctx)
    suggest = _suggest(ctx, sit)
    log, avoid = [], []
    for attempt in (1, 2):  # 한 번 다시 만들고, 그래도 문제면 안전한 기본 문장
        msg, nq = _parse(llm.chat(build_messages(ctx, kind, sit, suggest, avoid), temperature=0.8))
        if kind not in ("commitment", "open_question"):
            nq = base_question(kind, ctx)  # 정해 둔 질문(날씨 · 되고 싶은 모습 · 첫 만남)은 그대로
        # 제안 빈도는 선호라 검사로 막지 않는다. 무거운 날만 제안을 막는다(checks.problems).
        probs = checks.problems(msg, nq, sources=_sources(ctx), past=ctx.get("past_messages"),
                                comfort=comfort, aspiration=bool(ctx.get("aspiration")),
                                gentle="오늘은 살살" in sit, tone=ctx.get("tone"))
        log.append({"attempt": attempt, "problems": probs})
        if not probs:
            break
        avoid = probs
    else:
        tone = ctx.get("tone") if (ctx.get("tone"), comfort) in SAFE else "다정하게"
        msg, nq = SAFE[(tone, comfort)], "" if comfort or not kind else base_question(kind, ctx)
        log.append({"attempt": "기본 문장", "problems": []})
    return {"message": msg, "next_question": nq, "mode": "comfort" if comfort else "normal",
            "checks": log, "situations": sit, "next_kind": kind}
