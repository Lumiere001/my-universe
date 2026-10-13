"""
app/service/importer

지난 글 묶음(인스타그램 '내 정보 다운로드' ZIP)을 기록 후보로 바꾼다(PRD §4.4). 1차 importer.py 에서 옮겼다(1차 파일은 그대로).
여기서 끝내는 것: 깨진 한글 복원, 이어 쓴 게시물 묶기, 짧은 첫 줄을 제목으로. 글이 다루는 날은 기록을 만들 때와 같은 규칙
(rules.dates.read_day, G2: 제목 속 날짜면 확실, 없으면 게시일 추정)으로 미리 보여 주기만 한다 — 서버가 기록을 만들 때 다시 읽는다.
DB · 외부 호출 없음. 화면이 ZIP 에서 posts_N.json 만 꺼내 보내고(POST /import/instagram/preview), 고른 글을 한 편씩
/diary/stream(source='지난 글 묶음', source_ref=ref)으로 보낸다. 같은 원본을 두 번 가져오는 건 /diary/stream 이 막는다.
"""

import io
import json
import re
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core import config
from app.service.rules.dates import read_day

TZ = ZoneInfo(config.TIMEZONE)
SOURCE = "지난 글 묶음"
POSTS_FILE = re.compile(r"posts_\d+\.json$")
SERIES_START = re.compile(r"^\s*(?:\(\s*\d+\s*\)|\d+\s*편|번외)")
SERIES_END = re.compile(r"(이어짐|=>|\(계속\))\s*$")
SERIES_GAP_S = 86400   # 하루 안에 올린 다음 게시물만 이어 쓴 글로 본다
MARKER_MAX = 20        # ponytail: 이어 쓴 표시 줄('(2) 이어서' · '2편')은 짧다고 봄. 그보다 긴 줄은 내용이라 남김
TITLE_MAX = 40         # 쓰기 화면 파일 불러오기와 같은 기준: 짧은 첫 줄만 제목
# 화면이 보여 줄 어림값(docs/e2e-real.md · tech-explainer: 편당 외부 호출 4번 약 $0.10, Studio 기록 + 관측 약 54초 + 나머지)
# ponytail: 고정값. 사용자별 실측(runs 표 평균)이 필요해지면 그때 바꿈
EST_SECONDS_PER_POST = 60
EST_USD_PER_POST = 0.10


def fix(s):
    """인스타 내보내기는 UTF-8 바이트를 latin-1 글자로 적는다(깨진 한글). 이미 바른 글은 그대로."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def posts_from_zip(data: bytes):
    """ZIP 안의 posts_N.json 을 모두 읽어 게시물 목록으로(시험 · 스크립트용. 화면은 브라우저에서 같은 일을 한다)."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(n for n in z.namelist() if POSTS_FILE.search(n))
        if not names:
            raise ValueError("ZIP 안에서 posts_1.json 을 찾지 못했어요. 인스타그램 '내 정보 다운로드'(JSON 형식) 파일인지 확인해 주세요.")
        return [p for n in names for p in json.loads(z.read(n))]


def _merge(posts):
    """캡션 있는 게시물을 시간 순으로, 하루 안에 이어 쓴 게시물('(2)…' 로 시작하거나 앞 글이 '이어짐 · =>'로 끝남)은 하나로."""
    items = []
    for p in posts:
        media = p.get("media") or [{}]
        caption = fix(p.get("title") or media[0].get("title") or "")
        ts = p.get("creation_timestamp") or media[0].get("creation_timestamp")
        if caption.strip() and ts:
            items.append((int(ts), caption))
    merged = []
    for ts, caption in sorted(items):
        prev = merged[-1] if merged else None
        if prev and ts - prev["last"] < SERIES_GAP_S and (SERIES_START.match(caption) or SERIES_END.search(prev["caption"].rstrip())):
            prev.update(caption=SERIES_END.sub("", prev["caption"].rstrip()) + "\n" + caption, last=ts, parts=prev["parts"] + 1)
        else:
            merged.append({"ts": ts, "last": ts, "caption": caption, "parts": 1})
    return merged


def records(posts, max_text=None):
    """게시물 목록 → 기록 후보(최근 것부터). 사진만 있는 게시물은 뺀다.
    ref = 'ig:<첫 게시물 시각>'(같은 원본 다시 가져오기 막기), written_at = 게시 시각, too_long = 본문이 글 길이 상한을 넘음."""
    max_text = max_text or config.MAX_TEXT_CHARS
    out = []
    for m in reversed(_merge(posts)):
        lines = m["caption"].strip().splitlines()
        if m["parts"] > 1:
            lines = lines[:1] + [x for x in lines[1:] if not (SERIES_START.match(x) and len(x.strip()) <= MARKER_MAX)]
        titled = len(lines) > 1 and len(lines[0].strip()) <= TITLE_MAX
        title = " ".join(lines[0].split()) if titled else ""
        text = "\n".join(lines[1:] if titled else lines).strip()
        if not text:   # 제목 줄만 남은 글: 그 줄이 본문
            title, text = "", title
        written = datetime.fromtimestamp(m["ts"], TZ)
        day, basis, check = read_day(title, text, written.date())
        out.append({"ref": f"ig:{m['ts']}", "written_at": written.isoformat(), "title": title, "text": text,
                    "day": day.isoformat(), "day_basis": basis, "day_check": check, "parts": m["parts"],
                    "too_long": len(text) > max_text})
    return out
