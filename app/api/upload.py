"""
app/api/upload.py

사진(손글씨 · 일기장) 글자 읽기(WS18). POST /photo/read — 본문 = 사진 한 장의 바이트 그대로(jpg · png · heic) → {"text"}.

- 저장하지 않는다: 사진은 이 요청의 메모리에서 Upstage 로 보내고 버린다(DB · 디스크 · 로그 0). 읽은 글도 돌려주기만 한다.
- 사용자가 쓰기 칸에서 읽은 글을 고친 뒤 POST /diary/stream(source=사진)으로 보내면 그때부터 지금의 텍스트 길
  (위기 판정 · 가명 처리 → 기록 · 관측 · 한마디, 글이 다루는 날은 첫 줄 날짜 G2 · 없으면 올린 날 추정).
- 여러 쪽은 화면이 한 장씩 차례로 부르고 이어 붙인다(Vercel 함수 요청 본문 4.5MB 한도 때문에 한 요청 = 한 장).
- 형식 · 크기 검사는 신뢰 경계 입력 검사다(운영 상한 아님). 형식은 앞 바이트로 본다.
- 외부(Upstage)로 나가므로 동의(consent.check)를 먼저 본다.
"""

from fastapi import APIRouter, Depends, Request

from app.api import consent
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.service import ocr

router = APIRouter(tags=["일기"])
MAX_BYTES = 4_500_000   # Vercel 요청 본문 한도. 화면은 4MB 아래로 줄여 보낸다
MESSAGES = {
    "ocr_busy": "글자 읽기가 잠깐 붐벼요. 잠시 뒤 다시 눌러 주세요.",
    "ocr_failed": "사진의 글자를 읽지 못했어요. 잠시 뒤 다시 해 주세요.",
    "ocr_unconfigured": "지금은 사진 글자 읽기를 쓸 수 없어요. 운영자에게 알려 주세요.",
}
TOO_BIG = "사진이 너무 커요(4.5MB까지). JPG로 바꾸거나 다시 찍어 올려 주세요."


async def photo_bytes(request: Request):
    """본문을 끝까지 받되 한도를 넘는 순간 멈춘다(큰 파일을 메모리에 다 올리지 않게)."""
    if int(request.headers.get("content-length") or 0) > MAX_BYTES:
        raise ApiError(413, "photo_too_big", TOO_BIG)
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > MAX_BYTES:
            raise ApiError(413, "photo_too_big", TOO_BIG)
    return bytes(buf)


@router.post("/photo/read", summary="사진 한 장의 글자 읽기(저장 안 함) → 쓰기 칸에 채울 글")
def read_photo(user=Depends(get_user), repo=Depends(get_repo), data: bytes = Depends(photo_bytes)):
    with repo.session(user["id"]) as s:
        consent.check(s)   # 동의 전이면 403(사진이 밖으로 나가기 전에)
    if not data:
        raise ApiError(422, "photo_empty", "사진이 비어 있어요. 다시 골라 주세요.")
    if not ocr.kind(data):
        raise ApiError(415, "photo_type", "jpg · png · heic 사진만 읽을 수 있어요.")
    try:
        return {"text": ocr.read_page(data)}
    except ocr.OcrError as e:
        raise ApiError(503 if e.code == "ocr_unconfigured" else 502, e.code, MESSAGES[e.code])
