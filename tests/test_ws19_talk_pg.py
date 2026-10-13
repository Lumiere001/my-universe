"""통합(로컬 Supabase · ChromaDB): 대화 표(20261014000100_v8_conversations.sql) — 암호문 저장 · RLS · Data API 막힘,
대화 → 정리(확인 전) → 확인 저장을 실제 DB 로. 외부 AI 는 가짜, 가상 인물 글만."""
import json

import httpx
import psycopg
import pytest

from app.core import config
from tests.test_repo_pg import migrated, pytestmark, repo, users  # noqa: F401  (픽스처 · 건너뛰기 조건)
from tests.test_ws19_talk import fake_talk


def _events(text):
    return [(b.split("\n")[0].removeprefix("event: "), json.loads(b.split("data: ", 1)[1]))
            for b in text.split("\n\n") if b.startswith("event: ")]


def test_talk_confirm_on_pg(repo, users):  # noqa: F811
    from fastapi.testclient import TestClient

    import main
    from app.deps import get_repo
    from app.repository import conversations
    fake_talk(repo.fake)
    (ta, ua), (tb, ub) = users["a"], users["b"]
    ha, hb = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}
    main.app.dependency_overrides[get_repo] = lambda: repo
    try:
        c = TestClient(main.app)
        cid = c.post("/talk", headers=ha).json()["id"]
        r = c.post(f"/talk/{cid}/turn/stream", headers=ha, json={"text": "오늘부터 매일 아침 30분 걷기를 하겠다. 민준이랑 걸었다."})
        assert _events(r.text)[-1][0] == "turn"
        with psycopg.connect(config.DATABASE_URL) as conn:
            enc = conn.execute("select enc, turn_count from conversations where id = %s", [cid]).fetchone()
        assert enc[1] == 1 and "민준".encode() not in bytes(enc[0]) and "걷기".encode() not in bytes(enc[0])   # 암호문만
        with repo.session(ub) as s:   # RLS: 다른 사용자는 SQL 로 직접 봐도 0건
            assert s.conn.execute("select count(*) as n from conversations").fetchone()["n"] == 0
        assert c.get(f"/talk/{cid}", headers=hb).status_code == 404
        draft = _events(c.post(f"/talk/{cid}/finish/stream", headers=ha).text)[-1][1]
        assert draft["status"] == "confirm" and c.get("/diary", headers=ha).json()["entries"] == []
        done = c.post(f"/diary/{draft['id']}/confirm", headers=ha, json={"agreed": ["summary"]}).json()
        assert done["status"] == "done" and done["confirmed"] == "확인됨"
        with repo.session(ua) as s:
            assert conversations.get(s, cid) is None
        base = f"{config.SUPABASE_URL}/rest/v1/conversations"   # Data API 로는 읽지도 쓰지도 못함
        h = {"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {ta}", "Content-Type": "application/json"}
        tries = [httpx.get(base, headers=h, params={"select": "*"}), httpx.post(base, headers=h, json={"id": "c_x", "user_id": ua})]
        assert [x.status_code for x in tries if x.status_code not in (401, 403)] == []
    finally:
        main.app.dependency_overrides.clear()
