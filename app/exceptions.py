"""
app/exceptions.py

API 오류는 모두 HTTP 상태 + {"error": {"code": "영문_코드", "message": "한국어 안내"}}.
메시지에는 원문(일기 · 인용 · 이름)을 넣지 않는다.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core import logger


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def body(code, message):
    return {"error": {"code": code, "message": message}}


def install(app):
    @app.exception_handler(ApiError)
    async def _api(request: Request, e: ApiError):
        return JSONResponse(body(e.code, e.message), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, e: RequestValidationError):
        # 입력값(원문)을 되돌려 보내지 않고 어느 칸이 틀렸는지만 알린다
        fields = sorted({".".join(str(x) for x in err["loc"][1:]) for err in e.errors()})
        return JSONResponse(body("invalid_input", f"입력을 확인해 주세요: {', '.join(fields) or '본문'}"), status_code=422)

    @app.exception_handler(HTTPException)
    async def _http(request: Request, e: HTTPException):
        return JSONResponse(body(f"http_{e.status_code}", "요청을 처리할 수 없어요."), status_code=e.status_code)

    @app.exception_handler(Exception)
    async def _any(request: Request, e: Exception):
        logger.log("error", path=request.url.path, code="internal", what=type(e).__name__)
        return JSONResponse(body("internal", "잠시 뒤 다시 해 주세요."), status_code=500)
