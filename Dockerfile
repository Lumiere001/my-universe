# 백엔드(FastAPI · main.py:app) 이미지. 2차 가이드 ⑥. 화면은 infra/frontend/Dockerfile.
FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy LOG_TO_FILE=1

# 의존성 먼저(코드만 바뀌면 이 층은 다시 만들지 않는다)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 실행에 필요한 것만. 1차 Streamlit 파일 · 테스트 · 일기 데이터는 넣지 않는다.
# data/ops 의 두 파일은 해 분류용 기준 축 벡터(app/agents/tools.py sun_vectors, 없으면 조용히 빈 값).
COPY main.py ./
COPY app ./app
COPY data/ops/domain_aliases_*.json data/ops/topic_center_*.json ./data/ops/

# root 가 아닌 사용자로 실행(업스테이지 가이드 ⑥ Step 1). 리눅스에서 ./logs 를 마운트하면 그 폴더를 uid 1000 이 쓸 수 있어야 한다.
RUN useradd --create-home --uid 1000 app && mkdir -p /srv/logs && chown -R app /srv
USER app

EXPOSE 8001
# 로그 파일 이름 · 시각을 한국 시간으로(로컬과 같게). 하루 한도는 앱이 APP_TIMEZONE 으로 따로 센다.
ENV TZ=Asia/Seoul
# 로그는 /srv/logs (compose 가 ./logs 로 마운트). 원문은 로그에 남기지 않는다(앱 규칙).
CMD ["/srv/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
