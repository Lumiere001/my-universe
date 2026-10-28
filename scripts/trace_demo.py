"""
추적 시연(유료 호출 0, Docker 없이): 메모리 저장소 + 가짜 Upstage(tests 의 FakeUpstage)로 진짜 API 길을 돌려
일기 한 편(POST /diary/stream)과 대화 한 턴(POST /talk/{id}/turn/stream)의 span 을 로컬 Phoenix 로 보낸다. docs/trace.md

    uvx arize-phoenix serve                       # 다른 창. 화면 http://localhost:6006
    uv run --frozen python scripts/trace_demo.py  # 주소를 안 주면 http://localhost:6006 으로 보냄

가상 인물 하늘의 글이다. 가짜 Upstage 라 단계 시간은 실제보다 짧고 결과 글은 실제와 다르다(나무 모양 · 속성 확인용).
"""

import os
import sys
import types
import uuid
from pathlib import Path

os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:6006")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from app.agents import studio  # noqa: E402
from app.api import consent  # noqa: E402
from app.core import config, llm, security  # noqa: E402
from app.deps import get_repo, get_user  # noqa: E402
from app.repository import MemRepo  # noqa: E402
from tests.test_graph_flow import FakeUpstage  # noqa: E402
from tests.test_ws19_talk import fake_talk  # noqa: E402

DIARY = {"title": "민수 선배와 걸은 저녁", "written_at": "2026-10-27T22:10:00+09:00",
         "text": "퇴근하고 민수 선배랑 한강을 걸었다. 요즘 일이 많아 지쳐 있었는데 이야기를 나누니 마음이 가벼워졌다. "
                 "다음 주부터 저녁마다 30분씩 걷겠다."}
TURN = "오늘 회의에서 내 의견이 받아들여져서 기뻤어"

fake = FakeUpstage()
fake_talk(fake)
config.DIARY_ENC_KEY = security.new_master_key()
config.RECORD_AGENT_ID, config.OBSERVE_AGENT_ID = "rec-agent", "obs-agent"
studio._client = fake
llm._client = types.SimpleNamespace(chat=fake.chat, embeddings=fake.embeddings)
repo, uid = MemRepo(), str(uuid.uuid4())
main.app.dependency_overrides[get_user] = lambda: {"id": uid, "email": "haneul@my-universe.test"}
main.app.dependency_overrides[get_repo] = lambda: repo
with repo.session(uid) as s:
    consent.save(s)

c = TestClient(main.app)
r = c.post("/diary/stream", json=DIARY)
print("diary.stream", r.status_code, r.text.count("event: progress"), "단계")
cid = c.post("/talk").json()["id"]
r = c.post(f"/talk/{cid}/turn/stream", json={"text": TURN})
print("talk.turn", r.status_code)
print("Phoenix 로 보냄:", os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"])   # 끝날 때 남은 span 을 보내고 닫는다(TracerProvider atexit)
