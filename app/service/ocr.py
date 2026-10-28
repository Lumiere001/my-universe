"""
app/service/ocr.py

사진 글자 읽기(WS18): Upstage Document Digitization 으로 사진 한 장의 글자만 읽는다.
사진은 받은 바이트 그대로 보내고 버린다(디스크 · DB · 로그에 남기지 않음). 읽은 글도 돌려주기만 하고 여기서 저장하지 않는다.
실명 가리기 예외(결정 7): 사진 속 이름은 가릴 수 없어 그대로 간다. 정리 · 대화 요청(Studio · Solar)의 실명 0건 관문은
사용자가 읽은 글을 고쳐 보낸 뒤 지금의 텍스트 길(POST /diary/stream, source=사진)에서 그대로 건다.

모델: document-parse(기본, 2026-10-28 동규 결정). 되돌리려면 env PHOTO_READ_MODEL=ocr(코드 안 고침).
Document Parse(standard)는 줄 공책을 표 하나로 읽는다(줄 = 행, 왼쪽 여백 = 빈 칸). 응답 text 는 마크다운 표(| · --- 섞임)라
그대로 쓰면 글자 정확도가 0.2~0.5(10-14 의 0.35 가 이것, 글자는 맞게 읽음) → 표는 html 을 행마다 한 줄로 풀고(dp_text), 꼬리말은 뺀다.
2026-10-28 가상 손글씨 4장(tools/photo_samples.py measure): DP 풀기 = ocr 과 같은 글자(1.0 · 1.0 · 0.981 · 1.0), 약 2.5초(ocr 1.5초),
쪽당 $0.01(ocr $0.0015). enhanced 모드(쪽당 $0.03)는 표 없이 문단으로 읽지만 standard + 풀기와 글자가 같아 쓰지 않는다.
"""

import time
from html.parser import HTMLParser

import httpx

from app.core import config, logger

FORM = {"ocr": {"model": "ocr"},
        "document-parse": {"model": "document-parse", "ocr": "force", "output_formats": '["html", "text"]'}}
PRICE_PER_PAGE = {"ocr": 0.0015, "document-parse": 0.01}   # 요금표(2026-10, 부가세 빼고. DP 는 standard 모드)
TIMEOUT_S = 60
MIME = {"jpg": "image/jpeg", "png": "image/png", "heic": "image/heic"}
HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


class OcrError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code   # ocr_busy · ocr_failed · ocr_unconfigured


def kind(data):
    """앞 바이트로 형식을 본다(파일 이름 · Content-Type 은 믿지 않음). → 'jpg' | 'png' | 'heic' | None."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[4:8] == b"ftyp" and data[8:12] in HEIC_BRANDS:
        return "heic"
    return None


def tidy(text):
    """줄마다 앞뒤 빈칸을 떼고 빈 줄은 뺀다(첫 줄 날짜 G2 를 읽을 수 있게 줄은 남김)."""
    return "\n".join(x.strip() for x in (text or "").splitlines() if x.strip())


class _Rows(HTMLParser):
    """표 html → 행마다 한 줄(칸 글을 빈칸으로 이음, 칸 안 <br> 은 줄바꿈). 빈 행은 tidy 가 뺀다."""

    def __init__(self):
        super().__init__()
        self.lines, self.row, self.cell = [], [], None

    def _cell_done(self):
        if self.cell is not None:
            self.row.append("".join(self.cell).strip())
            self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._cell_done()   # 닫는 </td> 가 빠져도 칸을 잃지 않게
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append("\n")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th", "tr"):
            self._cell_done()
        if tag == "tr":
            self.lines.append(" ".join(c for c in self.row if c))
            self.row = []


def dp_text(j):
    """Document Parse 응답 → 읽는 순서의 글. 요소는 응답 순서(DP 가 정한 읽는 순서) 그대로, 표는 행마다 한 줄, 꼬리말은 뺀다.
    머리말은 남긴다(공책 맨 위 'Date ___' 칸에 쓴 날짜가 머리말로 읽힐 수 있어 G2 날짜를 잃지 않게)."""
    # ponytail: 표를 행 단위로만 푼다 — 두 단으로 쓴 쪽(왼쪽 · 오른쪽 글)이 한 표로 읽히면 두 단이 줄마다 섞인다. 그런 사진이 나오면 칸 좌표로 단을 나눔
    out = []
    for e in j.get("elements") or []:
        c = e.get("content") or {}
        if e.get("category") == "footer":
            continue
        if e.get("category") == "table":
            p = _Rows()
            p.feed(c.get("html") or "")
            out += p.lines
        else:
            out.append(c.get("text") or "")
    return "\n".join(out)


def ask(data, model):
    """사진 한 장을 Upstage 에 보내고 응답 JSON 을 돌려준다. 바쁘면(429) 두 번까지 잠깐 쉬고 다시 묻는다."""
    if not config.UPSTAGE_API_KEY or model not in FORM:
        raise OcrError("ocr_unconfigured")   # 키가 없거나 PHOTO_READ_MODEL 이 모르는 값
    k = kind(data)
    t0 = time.time()
    for attempt in range(3):
        try:
            r = httpx.post(f"{config.UPSTAGE_BASE_URL}/document-digitization", data=FORM[model], timeout=TIMEOUT_S,
                           headers={"Authorization": f"Bearer {config.UPSTAGE_API_KEY}"},
                           files={"document": (f"page.{k}", data, MIME.get(k, "application/octet-stream"))})
        except httpx.HTTPError as e:
            logger.log("external", what="upstage_ocr", model=model, ok=False, code=type(e).__name__,
                       ms=int((time.time() - t0) * 1000))
            raise OcrError("ocr_failed") from None
        if r.status_code != 429 or attempt == 2:
            break
        time.sleep(1.5)
    if r.status_code >= 400:
        logger.log("external", what="upstage_ocr", model=model, ok=False, http=r.status_code, ms=int((time.time() - t0) * 1000))
        raise OcrError("ocr_busy" if r.status_code == 429 else "ocr_failed")
    j = r.json()
    pages = j.get("numBilledPages") or (j.get("usage") or {}).get("pages") or 1
    logger.log("external", what="upstage_ocr", model=model, ok=True, pages=pages, est_usd=pages * PRICE_PER_PAGE[model],
               ms=int((time.time() - t0) * 1000))
    return j


def read_page(data, model=None):
    """사진 한 장 → 읽은 글(줄 단위, 빈 줄 뺌). model 을 안 주면 env PHOTO_READ_MODEL(기본 document-parse)."""
    model = model or config.PHOTO_READ_MODEL
    j = ask(data, model)
    return tidy(j.get("text") if model == "ocr" else dp_text(j))
