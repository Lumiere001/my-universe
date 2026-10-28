"""
app/core/logger.py

원문 없는 실행 기록. 한 줄 = JSON 하나(시각 · 사건 · 단계 · 시간 · 추정 비용 · id · 오류 코드 · 이름 목록).
LOG_TO_FILE=1 이면 logs/agent_flow_YYYYMMDD.log, 아니면 표준 출력(Vercel). 시각 · 파일 날짜는 APP_TIMEZONE(기본 KST) 고정.

원문 · 인용 · 사람 이름이 들어가지 않게 받는 칸을 정해 두고(ALLOWED), 글자 값은 짧은 이름만 받는다.
"""

import json
import sys
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core import config

# 받는 칸. 값은 숫자 · 참거짓 · 짧은 글자(id · 코드 · 단계 이름)만. 마음 상태(상황 이름 · 위로 모드 · 위기 여부)는 받지 않는다.
ALLOWED = {"step", "ms", "est_usd", "calls", "code", "user_id", "entry_id", "what", "ok", "status",
           "checks", "next_kind", "thoughts", "relations", "dropped", "past", "people_new",
           "questions", "attempts", "pages", "skipped", "path", "method", "http", "count", "tokens_in", "tokens_out",
           "model"}
MAX_STR = 40
_lock = threading.Lock()


def _clean(v):
    if isinstance(v, (bool, int, float)) or v is None:
        return v
    if isinstance(v, str):
        return v[:MAX_STR]
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v][:20]
    return str(type(v).__name__)


def log(event, **fields):
    """event: 'step' · 'external' · 'guard' · 'error' · 'http' … 모르는 칸은 버린다."""
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    line = {"ts": now.isoformat(timespec="seconds"), "event": event}
    line.update({k: _clean(v) for k, v in fields.items() if k in ALLOWED})
    text = json.dumps(line, ensure_ascii=False)
    with _lock:
        if config.LOG_TO_FILE:
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(config.LOG_DIR / f"agent_flow_{now:%Y%m%d}.log", "a", encoding="utf-8") as f:
                f.write(text + "\n")
        else:
            print(text, file=sys.stdout, flush=True)
    return line
