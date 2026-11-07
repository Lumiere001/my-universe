"""
app/service/mcp_input.py — AI 비서(MCP)로 들어오는 일기의 입력 검사 · 도구 설명. 원격(app/api/mcp_link.py)과 로컬 stdio(tools/mcp_diary.py)가 같이 쓴다.
표준 라이브러리 + pydantic 만 쓴다(stdio 판이 앱 의존성 없이 이 파일만 읽어 가게).
"""

import hashlib
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

TZ = ZoneInfo("Asia/Seoul")
IMPORTED, WRITTEN = "지난 글 묶음", "텍스트"   # app/models SOURCES
MAX_BATCH = 50    # 한 번에 받는 편수(정리는 한 편 1분쯤 · $0.15쯤 — app/service/importer 어림값)
MAX_TEXT = 8000   # 백엔드 MAX_TEXT_CHARS 기본값(넘으면 서버도 422)
MAX_TITLE = 120   # 백엔드 MAX_TITLE_CHARS 기본값
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")

DOCS = {
    "import_diaries": "다른 곳(노션 · 메모 앱 · 파일 …)에 있던 지난 일기 여러 편을 나의 우주로 가져온다(한 번에 50편까지). "
                      "본문은 사용자가 쓴 그대로 넘긴다. 한 편마다 AI 정리(유료, 1분쯤)가 돌아서 몇 편을 넣을지 사용자에게 먼저 확인한다. "
                      "날짜 순서와 관계없이 넣어도 오래된 글부터 정리한다. 이미 넣은 글은 다시 정리하지 않는다. 바로 돌려주고 정리는 뒤에서 한다.",
    "write_diary": "오늘(또는 date 날)의 일기 한 편을 나의 우주에 쓴다. 본문은 사용자가 쓴 그대로 넘긴다. AI 정리(유료, 1분쯤)는 뒤에서 하고 바로 돌려준다.",
    "recent_diaries": "최근 기록 n편(1~100)의 날짜 · 제목 · 정리 상태(done 끝 · processing 정리 중 · failed 멈춤)만 본다. 본문은 돌려주지 않는다. "
                      "넣기 전에 이미 있는 글인지 확인할 때, 넣은 뒤 정리가 끝났는지 볼 때 쓴다.",
}
INSTRUCTIONS = ("사용자의 일기를 나의 우주(일기 앱)로 넘기는 도구. 본문은 고치지 말고 그대로, 여러 편이면 먼저 recent_diaries 로 "
                "이미 있는지 보고, 몇 편을 넣을지 사용자에게 확인한 뒤 import_diaries 로.")
NOTE = "정리는 한 편에 1분쯤, 오래된 글부터 차례로 해요. recent_diaries 로 상태(done = 끝)를 볼 수 있어요."


class Diary(BaseModel):
    text: str = Field(description="일기 본문. 사용자가 쓴 그대로(고치거나 요약하지 않음), 8,000자까지")
    date: str | None = Field(None, description="글이 다루는 날 YYYY-MM-DD. 모르면 비움(서버가 제목 · 본문 속 날짜를 읽음)")
    title: str = Field("", description="제목. 없으면 비움")


def body(i, e: Diary, source):
    """한 편 → POST /diary 본문. 틀리면 몇 번째 글이 왜 틀렸는지 ValueError."""
    text, title = e.text.strip(), " ".join(e.title.split())
    if not text:
        raise ValueError(f"{i}번 글: 본문이 비어 있어요.")
    if len(text) > MAX_TEXT:
        raise ValueError(f"{i}번 글: {MAX_TEXT:,}자까지 넣을 수 있어요(지금 {len(text):,}자). 나눠서 넣어 주세요.")
    if len(title) > MAX_TITLE:
        raise ValueError(f"{i}번 글: 제목은 {MAX_TITLE}자까지예요.")
    out = {"text": text, "title": title, "source": source}
    if e.date:
        try:
            day = date.fromisoformat(e.date) if DAY.fullmatch(e.date) else None
        except ValueError:
            day = None
        if not day:
            raise ValueError(f"{i}번 글: 날짜는 YYYY-MM-DD 로 적어 주세요(받은 값 {e.date!r}).")
        now = datetime.now(TZ)
        if day > now.date():
            raise ValueError(f"{i}번 글: 앞으로의 날짜({e.date})예요.")
        # 앱 가져오기와 같게: 그날 낮 12시에 쓴 글로(오늘이면 지금까지), 글이 다루는 날은 그대로 확실
        out |= {"day": e.date, "written_at": min(datetime(day.year, day.month, day.day, 12, tzinfo=TZ), now).isoformat()}
    if source == IMPORTED:   # 같은 원본 표시: 다시 넣어도 서버가 같은 글로 알아봄(앱의 '파일:' 표시와 같은 방식)
        out["source_ref"] = "mcp:" + hashlib.sha256(f"{e.date}\n{title}\n{text}".encode()).hexdigest()[:32]
    return out


def batch(entries, source=IMPORTED):
    """여러 편 → 오래된 것부터 보낼 본문들(날짜 없는 글은 뒤로, 받은 순서 그대로). 하나라도 틀리면 아무것도 보내지 않음."""
    if not entries:
        raise ValueError("가져올 글이 없어요.")
    if len(entries) > MAX_BATCH:
        raise ValueError(f"한 번에 {MAX_BATCH}편까지 넣을 수 있어요(받은 글 {len(entries)}편). 나눠서 넣어 주세요.")
    bodies = [body(i, e if isinstance(e, Diary) else Diary(**e), source) for i, e in enumerate(entries, 1)]
    return sorted(bodies, key=lambda b: b.get("day") or "9999")
