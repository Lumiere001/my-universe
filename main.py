"""
main.py — 나의 우주 v8 백엔드(FastAPI) 진입점.

    uv run --frozen uvicorn main:app --port 8001          # 로컬 · Docker
    문서: http://localhost:8001/docs (OpenAPI), API 약속: docs/api-v8.md
"""

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import exceptions
from app.api import diary, routes
from app.core import config, logger

app = FastAPI(title="나의 우주 API", version=config.VERSION,
              description="말을 거는 일기장 v8. 로그인: Supabase access token 을 `Authorization: Bearer` 로.")
app.add_middleware(CORSMiddleware, allow_origins=[config.FRONTEND_ORIGIN], allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type", "Accept"])
exceptions.install(app)
app.include_router(routes.router)
app.include_router(diary.router)


@app.middleware("http")
async def access_log(request: Request, call_next):
    """원문 없는 접근 기록: 방법 · 경로(id 만 들어 있음) · 상태 · 시간."""
    t0 = time.time()
    response = await call_next(request)
    logger.log("http", method=request.method, path=request.url.path, http=response.status_code,
               ms=int((time.time() - t0) * 1000))
    return response
