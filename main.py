"""
main.py — 나의 우주 v8 백엔드(FastAPI) 진입점.

    uv run --frozen uvicorn main:app --port 8001          # 로컬 · Docker
    문서: http://localhost:8001/docs (OpenAPI, API_DOCS=1 일 때만 — 로컬 .env.local), API 약속: docs/api-v8.md
"""

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app import exceptions
from app.agents import tools
from app.api import consent, diary, people_thoughts, routes
from app.api import write   # WS13
from app.api import chat   # WS19 대화 · WS20 요약 확인
from app.core import config, logger

docs = config.API_DOCS   # 배포에서는 /docs · /redoc · /openapi.json 을 열지 않는다
app = FastAPI(title="나의 우주 API", version=config.VERSION,
              description="말을 거는 일기장 v8. 로그인: Supabase access token 을 `Authorization: Bearer` 로.",
              docs_url="/docs" if docs else None, redoc_url="/redoc" if docs else None,
              openapi_url="/openapi.json" if docs else None)
app.add_middleware(CORSMiddleware, allow_origins=[config.FRONTEND_ORIGIN], allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type", "Accept"])
exceptions.install(app)
app.include_router(routes.router)
app.include_router(write.router)   # diary.router 보다 먼저: GET /diary/prompt 가 /diary/{eid} 에 걸리지 않게
app.include_router(diary.router)
app.include_router(consent.router)
app.include_router(people_thoughts.router)
app.include_router(chat.router)
tools.sun_vectors()   # 기준 축 벡터 파일(data/ops)이 없으면 시작할 때 sun_vectors_missing 을 남긴다


@app.middleware("http")
async def access_log(request: Request, call_next):
    """원문 없는 접근 기록: 방법 · 경로(id 만 들어 있음) · 상태 · 시간."""
    t0 = time.time()
    response = await call_next(request)
    logger.log("http", method=request.method, path=request.url.path, http=response.status_code,
               ms=int((time.time() - t0) * 1000))
    return response
