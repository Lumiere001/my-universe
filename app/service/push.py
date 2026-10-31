"""
app/service/push.py

고른 시각 알림(PRD v9 Q8 · Q8-2 · Q17-1). 잠금 화면에 보이므로 일기 내용 · 이름 · 되고 싶은 모습은 넣지 않고,
고른 별지기 캐릭터의 말투로 정해 둔 질문 한 줄만 보낸다(숨은 이유가 담긴 진짜 첫 말은 앱을 연 뒤).
하루 한 번, 그날 이미 일기를 썼으면 보내지 않고, 일주일 넘게 쓰지 않았으면 사흘에 한 번만(귀찮게 하는 알림은 꺼지기 때문).
"""

import json
from datetime import date, datetime

LINES = {
    "다정하게": "오늘 하루는 어땠어요? 잠깐 이야기 들려줄래요?",
    "담백하게": "오늘 이야기, 한 줄만 남겨 볼까요?",
    "고양이처럼": "뭐, 오늘 얘기 안 해 줄 거야? 조금 궁금하긴 한데.",
    "팩폭": "오늘 기록 아직이야. 한 줄만 쓰고 자.",
}
QUIET_AFTER, EVERY = 7, 3   # 마지막 일기 뒤 7일이 넘으면 사흘에 한 번


def slot(now):
    """한국 시각 → 30분 단위 'HH:MM'(예약 작업이 조금 늦게 돌아도 그 30분 안이면 같은 자리)."""
    return f"{now.hour:02d}:{0 if now.minute < 30 else 30:02d}"


def should_send(today, last_sent, last_entry_day):
    if last_sent and str(last_sent) == str(today):
        return False
    if last_entry_day and str(last_entry_day) == str(today):   # 오늘 이미 씀
        return False
    if last_entry_day:
        gap = (date.fromisoformat(str(today)) - date.fromisoformat(str(last_entry_day))).days
        if gap > QUIET_AFTER and gap % EVERY:
            return False
    return True


def payload(tone):
    return json.dumps({"title": "나의 우주", "body": LINES.get(tone, LINES["다정하게"]), "url": "/"}, ensure_ascii=False)


def send(sub, data, private_key, subject):
    """→ "ok" | "gone"(구독 만료 · 지워짐 → 구독을 지움) | "fail". pywebpush 가 암호화 · VAPID 서명을 한다."""
    from pywebpush import WebPushException, webpush
    try:
        webpush(subscription_info=sub, data=data, vapid_private_key=private_key, vapid_claims={"sub": subject}, ttl=3600)
        return "ok"
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        return "gone" if code in (404, 410) else "fail"


if __name__ == "__main__":
    assert slot(datetime(2026, 11, 2, 21, 7)) == "21:00" and slot(datetime(2026, 11, 2, 21, 41)) == "21:30"
    assert not should_send("2026-11-02", "2026-11-02", None)
    assert not should_send("2026-11-02", None, "2026-11-02")
    assert should_send("2026-11-02", "2026-11-01", "2026-11-01")
    assert not should_send("2026-11-19", None, "2026-11-02") and should_send("2026-11-20", None, "2026-11-02")   # 17일: 쉼 · 18일: 보냄
    print("ok")
