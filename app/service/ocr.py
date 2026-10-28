"""
app/service/ocr.py

사진 글자 읽기(WS18): Upstage Document Digitization 으로 사진 한 장의 글자만 읽는다.
사진은 받은 바이트 그대로 보내고 버린다(디스크 · DB · 로그에 남기지 않음). 읽은 글도 돌려주기만 하고 여기서 저장하지 않는다.
실명 가리기 예외(결정 7): 사진 속 이름은 가릴 수 없어 그대로 간다. 정리 · 대화 요청(Studio · Solar)의 실명 0건 관문은
사용자가 읽은 글을 고쳐 보낸 뒤 지금의 텍스트 길(POST /diary/stream, source=사진)에서 그대로 건다.

모델: ocr(글자 + 줄만). 2026-10-14 가상 손글씨 사진으로 ocr 과 document-parse 를 1회씩 재어 정함(tools/photo_samples.py measure):
정확도는 비슷하고 ocr 이 싸고(쪽당 $0.0015 vs $0.01) 빨라서. 일기장 사진은 표 · 제목 구조가 필요 없다.
"""

import time

import httpx

from app.core import config, logger, trace

MODEL = "ocr"
PRICE_PER_PAGE = {"ocr": 0.0015, "document-parse": 0.01}   # 요금표(2026-10, 부가세 빼고)
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


def read_page(data, model=MODEL):
    """사진 한 장 → 읽은 글. Upstage 가 바쁘면(429) 두 번까지 잠깐 쉬고 다시 묻는다."""
    with trace.span("ocr", kind="TOOL", system="upstage", model=model):   # 사진 · 읽은 글은 넣지 않음
        return _read_page(data, model)


def _read_page(data, model):
    if not config.UPSTAGE_API_KEY:
        raise OcrError("ocr_unconfigured")
    k = kind(data)
    form = {"model": model, **({"ocr": "force", "output_formats": '["text"]'} if model == "document-parse" else {})}
    t0 = time.time()
    for attempt in range(3):
        try:
            r = httpx.post(f"{config.UPSTAGE_BASE_URL}/document-digitization", data=form, timeout=TIMEOUT_S,
                           headers={"Authorization": f"Bearer {config.UPSTAGE_API_KEY}"},
                           files={"document": (f"page.{k}", data, MIME.get(k, "application/octet-stream"))})
        except httpx.HTTPError as e:
            logger.log("external", what="upstage_ocr", ok=False, code=type(e).__name__, ms=int((time.time() - t0) * 1000))
            raise OcrError("ocr_failed") from None
        if r.status_code != 429 or attempt == 2:
            break
        time.sleep(1.5)
    trace.set(http_status=r.status_code)
    if r.status_code >= 400:
        logger.log("external", what="upstage_ocr", ok=False, http=r.status_code, ms=int((time.time() - t0) * 1000))
        raise OcrError("ocr_busy" if r.status_code == 429 else "ocr_failed")
    j = r.json()
    text = j.get("text") if model == "ocr" else (j.get("content") or {}).get("text")
    pages = j.get("numBilledPages") or (j.get("usage") or {}).get("pages") or 1
    logger.log("external", what="upstage_ocr", ok=True, pages=pages, est_usd=pages * PRICE_PER_PAGE[model],
               ms=int((time.time() - t0) * 1000))
    trace.set(pages=pages, est_usd=pages * PRICE_PER_PAGE[model])
    return tidy(text)
