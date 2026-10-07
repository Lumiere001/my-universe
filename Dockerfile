# 백엔드(FastAPI · main.py:app) 이미지. 2차 가이드 ⑥. 화면은 infra/frontend/Dockerfile.
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy LOG_TO_FILE=1

# 의존성 먼저(코드만 바뀌면 이 층은 다시 만들지 않는다)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 실행에 필요한 것만. 1차 Streamlit 파일 · data/ · 테스트는 넣지 않는다.
COPY main.py ./
COPY app ./app

EXPOSE 8001
# 로그는 /srv/logs (compose 가 ./logs 로 마운트). 원문은 로그에 남기지 않는다(앱 규칙).
CMD ["/srv/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
