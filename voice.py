"""
voice.py

일기장만의 말투. 내용은 그대로 두고 여는 말과 문장 끝만 바꾼다 (가르치지 않는다).

- 다정하게: 여는 말 "오늘도 기록해 줘서 고마워요."
- 담백하게: 여는 말 없음
- 고양이처럼: 문장 끝에 꼬리 — "~다." → "~다냥.", "~요." → "~요냥.", "~까?" → "~까냥?"
"""

import html
import re

TONES = ["다정하게", "담백하게", "고양이처럼"]
OPENER = {"다정하게": "오늘도 기록해 줘서 고마워요.", "담백하게": "", "고양이처럼": "오늘도 기록해 줘서 고맙다냥."}
_CAT = re.compile(r"(?<=[가-힣])(?<!냥)([.?!])(?=\s|$)")   # 한글 글자 바로 뒤의 문장 끝 부호


def speak(text, tone="다정하게", opener=False):
    text = (text or "").strip()
    if opener and OPENER.get(tone):
        text = f"{OPENER[tone]} {text}".strip()
    if tone == "고양이처럼":
        text = _CAT.sub(r"냥\1", text)
    return text


def ask(question):
    """다음에 써 볼 질문은 늘 권하는 말로 (말투는 speak · bubble 이 입힌다)."""
    return f"다음엔 이런 걸 써 보면 어때요? {question}"


def bubble(text, tone="다정하게", name="별지기", opener=False, emoji="🔭"):
    """일기장이 하는 말 = 말풍선 HTML. 사용자의 글(인용)과 겹치지 않는 모양."""
    return (f'<div class="vb"><div class="vb-av">{emoji}</div><div><div class="vb-name">{html.escape(name or "별지기")}</div>'
            f'<div class="vb-text">{html.escape(speak(text, tone, opener))}</div></div></div>')


if __name__ == "__main__":
    assert speak("마음이 가볍다.", "고양이처럼") == "마음이 가볍다냥."
    assert speak("좋아요. 정말요?", "고양이처럼") == "좋아요냥. 정말요냥?"
    assert speak("맞는 선택일까?", "고양이처럼") == "맞는 선택일까냥?"
    assert speak("이미 냥.", "고양이처럼") == "이미 냥."                     # 꼬리를 두 번 달지 않는다
    assert speak("“배움” 쪽이다.", "고양이처럼") == "“배움” 쪽이다냥."
    assert speak("v1.5 버전", "고양이처럼") == "v1.5 버전"                   # 숫자 사이 점은 그대로
    assert speak("요약.", "다정하게", opener=True) == "오늘도 기록해 줘서 고마워요. 요약."
    assert speak("요약.", "담백하게", opener=True) == "요약."
    assert speak("요약.", "담백하게") == speak("요약.", "다정하게") == "요약."  # 내용은 그대로
    assert speak(ask("무엇이 달라졌을까?"), "고양이처럼").endswith("어때요냥? 무엇이 달라졌을까냥?")
    assert speak(speak("좋다.", "고양이처럼"), "고양이처럼") == "좋다냥."           # 두 번 입혀도 같다
    assert "&lt;b&gt;" in bubble("<b>", name="<x>") and "&lt;x&gt;" in bubble("a", name="<x>")
    print("voice ok")
