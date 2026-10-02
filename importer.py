"""
importer.py

어디서 온 글이든 같은 '공통 기록'으로 바꾼다 (PRD §4.1).

공통 기록: id, written_at, day, day_basis(확실/추정), title, body, source_kind, source_ref, sections
출처별 사정(인스타 글자 깨짐, 이어진 게시물, 제목 속 날짜, P1 소제목)은 여기서 끝낸다.
"""

import hashlib
import html
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
SECTION = re.compile(r"^\s*(?:P|Part|PART|part)\s?\.?\s?(\d+)\s*\.?\s*(.*)$")
TITLE_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*/\s*(\d{1,2})(?!\d)")
SERIES_START = re.compile(r"^\s*(?:\(\s*\d+\s*\)|\d+\s*편|번외)")
SERIES_END = re.compile(r"(이어짐|=>|\(계속\))\s*$")


def _fix(s):  # 인스타 내보내기는 UTF-8 바이트를 latin-1 문자로 저장한다
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _record_id(source_kind, key):
    return "R" + hashlib.sha1(f"{source_kind}:{key}".encode()).hexdigest()[:8]


def _sections(body):
    """P1·Part1 소제목으로 나눈다. 없으면 글 전체가 한 부분."""
    out, cur = [], {"heading": "", "lines": []}
    for line in body.splitlines():
        m = SECTION.match(line)
        if m:
            if cur["lines"] or cur["heading"]:
                out.append(cur)
            cur = {"heading": line.strip(), "lines": []}
        elif line.strip():
            cur["lines"].append(line.strip())
    out.append(cur)
    return [{"heading": s["heading"], "text": "\n".join(s["lines"])} for s in out if s["lines"]]


def _day(title, written):
    """제목 속 날짜(예: 9/20)가 있으면 확실, 없으면 작성일로 추정."""
    m = TITLE_DATE.search(title or "")
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = written.year - (1 if month > written.month + 1 else 0)  # 1월에 쓴 12월 일기
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d"), "확실"
        except ValueError:
            pass
    return written.strftime("%Y-%m-%d"), "추정"


def make_record(title, body, written, source_kind, source_ref, day=None):
    title = (title or "").strip() or body.strip().splitlines()[0][:30]
    d, basis = (day, "확실") if day else _day(title, written)
    return {
        "id": _record_id(source_kind, source_ref),
        "written_at": written.isoformat(timespec="minutes"),
        "day": d, "day_basis": basis,
        "title": title, "body": body.strip(),
        "source_kind": source_kind, "source_ref": source_ref,
        "sections": _sections(body),
    }


##################################################
# 인스타그램 "내 정보 다운로드" ZIP
##################################################

def from_instagram_zip(data: bytes):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = sorted(n for n in z.namelist() if re.search(r"posts_\d+\.json$", n))
        if not names:
            raise ValueError("ZIP 안에서 posts_1.json을 찾지 못했습니다. 인스타그램 '내 정보 다운로드'(JSON 형식) 파일인지 확인해 주세요.")
        posts = [p for n in names for p in json.loads(z.read(n))]

    items = []
    for p in posts:
        media = p.get("media") or [{}]
        caption = _fix(p.get("title") or media[0].get("title") or "")
        ts = p.get("creation_timestamp") or media[0].get("creation_timestamp")
        if caption.strip() and ts:
            items.append((ts, caption))
    items.sort()

    merged = []  # 여러 게시물로 이어 쓴 일기를 하나로 묶는다
    for ts, caption in items:
        prev = merged[-1] if merged else None
        if prev and ts - prev["ts"] < 86400 and (SERIES_START.match(caption) or SERIES_END.search(prev["caption"].rstrip())):
            prev["caption"] = SERIES_END.sub("", prev["caption"].rstrip()) + "\n" + caption
            prev["parts"] += 1
        else:
            merged.append({"ts": ts, "caption": caption, "parts": 1})

    records = []
    for m in merged:
        lines = m["caption"].strip().splitlines()
        title, body = lines[0], "\n".join(l for l in lines[1:] if not SERIES_START.match(l) or SECTION.match(l))
        written = datetime.fromtimestamp(m["ts"], KST)
        rec = make_record(title, body or title, written, "instagram", f"post@{m['ts']}")
        rec["series_parts"] = m["parts"]
        records.append(rec)
    return records


##################################################
# MD · TXT 파일, 직접 쓴 글
##################################################

def from_text_file(name: str, data: bytes):
    text = data.decode("utf-8-sig", errors="replace")
    lines = text.strip().splitlines()
    title = re.sub(r"^#+\s*", "", lines[0]).strip() if lines else name
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", name + " " + title)
    written = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 21, 0, tzinfo=KST) if m else datetime.now(KST)
    body = "\n".join(re.sub(r"^#+\s*", "", l) for l in lines[1:])
    return [make_record(title, body or title, written, "file", name, day=m.group(0) if m else None)]


def from_direct(title: str, body: str, day: str):
    now = datetime.now(KST)
    return make_record(title, body, now, "direct", f"direct@{now.timestamp()}", day=day)


##################################################
# Studio에 보낼 HTML (Studio는 MD · TXT를 받지 않는다)
##################################################

def to_html(rec):
    parts = [f"<h1>{html.escape(rec['title'])}</h1>"]
    for s in rec["sections"]:
        if s["heading"]:
            parts.append(f"<h2>{html.escape(s['heading'])}</h2>")
        parts += [f"<p>{html.escape(line)}</p>" for line in s["text"].splitlines()]
    return ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f"<title>{html.escape(rec['title'])}</title></head><body>{''.join(parts)}</body></html>")


if __name__ == "__main__":  # 자기 점검: 가상 ZIP을 읽어 묶기·날짜·소제목을 확인
    import config
    recs = from_instagram_zip(config.VIRTUAL_ZIP.read_bytes())
    assert len(recs) == 29, len(recs)                       # 30개 게시물 중 2개가 하나로 묶임
    series = [r for r in recs if r.get("series_parts") == 2][0]
    assert "축제 준비와 시험을 동시에" in series["body"] and "이어짐" not in series["body"]
    late = [r for r in recs if r["title"].startswith("3/27")][0]
    assert late["day"] == "2026-03-27" and late["day_basis"] == "확실" and late["written_at"].startswith("2026-03-28")
    assert [s["heading"] for s in late["sections"]] == ["P1. 저녁", "P2. 생각"]
    poem = [r for r in recs if r["title"] == "봄비"][0]
    assert poem["day_basis"] == "추정"
    print("importer ok:", len(recs), "records")
