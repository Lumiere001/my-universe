"""통합: 로컬 Supabase(Postgres · Auth) + ChromaDB 가 떠 있을 때만(scripts/dev_up.sh). 외부 AI 호출은 가짜.
실제 DB 쓰고 읽기 · 암호문 저장 · RLS 로 다른 사용자 데이터 안 보임 · 실제 토큰으로 API 전체 흐름."""
import json

import httpx
import psycopg
import pytest

from app.core import config

pytestmark = pytest.mark.skipif(not config.DATABASE_URL.startswith("postgresql://postgres:postgres@127.0.0.1"),
                                reason="로컬 Supabase 없음(scripts/dev_up.sh)")


def _up():
    try:
        httpx.get(f"http://{config.CHROMA_HOST}:{config.CHROMA_PORT}/api/v2/heartbeat", timeout=2).raise_for_status()
        psycopg.connect(config.DATABASE_URL, connect_timeout=2).close()
        return True
    except Exception:
        return False


if config.DATABASE_URL and not _up():
    pytestmark = pytest.mark.skip(reason="로컬 Supabase · ChromaDB 가 꺼져 있음")

from tests.test_graph_flow import DAY1, DAY2, NAMES, FakeUpstage  # noqa: E402


@pytest.fixture(scope="module")
def users():
    from app.core import seed
    pw = seed._read(seed.ENV_LOCAL)["DEV_TEST_PASSWORD"]
    out = {}
    for k in ("a", "b"):
        email = f"it-{k}@my-universe.test"
        seed.admin_user(email, pw)
        out[k] = seed.token(email, pw)   # (token, uid)
    return out


@pytest.fixture
def repo(users, monkeypatch, tmp_path):
    from app.agents import studio
    from app.core import llm, seed
    from app.repository import PgRepo
    from app.repository.vectors import ChromaVectors
    monkeypatch.setattr(config, "CHROMA_COLLECTION", "thoughts_it")
    monkeypatch.setattr(config, "RECORD_AGENT_ID", "rec-agent")
    monkeypatch.setattr(config, "LOG_TO_FILE", True)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path)
    fake = FakeUpstage()
    monkeypatch.setattr(studio, "_client", fake)
    monkeypatch.setattr(llm, "_client", fake)
    r = PgRepo(config.DATABASE_URL, ChromaVectors())
    for _, uid in users.values():
        seed.wipe(r, uid)
    r.fake = fake
    return r


def write(repo, uid, title, text, when):
    from app.agents import graph
    from app.repository import diary, views
    eid = diary.new_id("e")
    with repo.session(uid) as s:
        diary.create_entry(s, eid, diary.parse_dt(when), "맑음", title, text)
    graph.run(repo, uid, eid)
    with repo.session(uid) as s:
        return views.entry_result(s, eid)


def test_db_roundtrip_ciphertext_and_rls(repo, users):
    from app.repository import diary, views
    ua, ub = users["a"][1], users["b"][1]
    r1 = write(repo, ua, *DAY1, "2026-10-01T22:00:00+09:00")
    r2 = write(repo, ua, *DAY2, "2026-10-03T22:00:00+09:00")
    assert r1["status"] == r2["status"] == "done" and r2["past"] and r2["relations"]
    # 원문은 DB 에 암호문으로만
    with psycopg.connect(config.DATABASE_URL) as c:
        rows = c.execute("select enc, steps_enc from entries where user_id = %s", [ua]).fetchall()
        tenc = c.execute("select enc from thoughts where user_id = %s", [ua]).fetchall()
        penc = c.execute("select enc from people where user_id = %s", [ua]).fetchall()
    blob = b"".join(bytes(x) for r in rows + tenc + penc for x in r if x)
    assert blob and all(w.encode() not in blob for w in ("걷기", "아침", *NAMES))
    assert all(r[1] is None for r in rows)          # 끝난 기록의 단계별 저장값은 지움
    # RLS: b 로는 a 의 행이 하나도 안 보인다(코드의 user_id 거름과 상관없이 SQL 로 직접 봐도)
    with repo.session(ub) as s:
        assert views.entry_result(s, r1["id"]) is None
        for t in ("entries", "thoughts", "people", "relations", "states", "runs", "stars", "suns"):
            assert s.conn.execute(f"select count(*) as n from {t}").fetchone()["n"] == 0, t
        n = s.conn.execute("update entries set status = 'failed' where id = %s", [r1["id"]]).rowcount
        assert n == 0
    with repo.session(ua) as s:
        assert s.conn.execute("select count(*) as n from entries").fetchone()["n"] == 2
        assert {p["name"] for p in diary.people(s)} >= set(NAMES)
    # 벡터: 원문 없음, 사용자별
    docs, metas = repo.vectors.documents(ua)
    assert docs and all(d is None for d in docs) and repo.vectors.get(ub) == {}
    assert not [n for n in NAMES if n in "\n".join(repo.fake.sent)]


def test_api_with_real_tokens(repo, users, monkeypatch):
    from fastapi.testclient import TestClient

    import main
    from app.deps import get_repo
    main.app.dependency_overrides[get_repo] = lambda: repo
    try:
        c = TestClient(main.app)
        ta, tb = users["a"][0], users["b"][0]
        ha, hb = {"Authorization": f"Bearer {ta}"}, {"Authorization": f"Bearer {tb}"}
        assert c.get("/me", headers={"Authorization": "Bearer nope"}).status_code == 401
        me = c.get("/me", headers=ha).json()
        assert me["user"]["email"] == "it-a@my-universe.test"
        r = c.post("/diary/stream", headers=ha, json={"title": DAY1[0], "text": DAY1[1]})
        ev = [b for b in r.text.split("\n\n") if b.startswith("event: result")]
        res = json.loads(ev[0].split("data: ", 1)[1])
        assert res["status"] == "done"
        assert c.get(f"/diary/{res['id']}", headers=hb).status_code == 404
        assert c.get("/universe", headers=ha).json()["planets"][0]["id"] == res["id"]
        assert c.get("/universe", headers=hb).json()["planets"] == []
        assert c.delete(f"/diary/{res['id']}", headers=ha).status_code == 204
        assert c.get("/diary", headers=ha).json()["entries"] == []
    finally:
        main.app.dependency_overrides.clear()


def test_data_api_blocked(users):
    """H1: 화면이 공개하는 anon 키 + 사용자 토큰으로 Supabase Data API(/rest/v1)를 직접 불러도 표를 읽고 쓰지 못한다."""
    token, uid = users["a"]
    base = f"{config.SUPABASE_URL}/rest/v1"
    user = {"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    anon = {"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {config.SUPABASE_ANON_KEY}"}
    tries = [
        httpx.post(f"{base}/runs", headers=user, json={"user_id": uid, "step": "x", "est_usd": -100}),
        httpx.get(f"{base}/runs", headers=user, params={"select": "*"}),
        httpx.delete(f"{base}/runs", headers=user, params={"user_id": f"eq.{uid}"}),
        httpx.patch(f"{base}/profiles", headers=user, params={"user_id": f"eq.{uid}"}, json={"settings": {"tone": "팩폭"}}),
        httpx.get(f"{base}/entries", headers=user, params={"select": "id"}),
        httpx.get(f"{base}/entries", headers=anon, params={"select": "id"}),
    ]
    assert [r.status_code for r in tries if r.status_code not in (401, 403)] == []
    with psycopg.connect(config.DATABASE_URL) as c:
        assert c.execute("select count(*) from runs where est_usd < 0 or step = 'x'").fetchone()[0] == 0


def test_runs_check_and_lock_across_connections(repo, users):
    """est_usd >= 0 check, 실행 잠금은 다른 연결(다른 인스턴스)에서 동시에 잡지 못한다."""
    import threading
    import time

    from app.repository import diary
    ua = users["a"][1]
    with pytest.raises(psycopg.errors.CheckViolation):
        with repo.session(ua) as s:
            diary.add_run(s, None, "x", est_usd=-1)
    with repo.session(ua) as s:
        diary.create_entry(s, "e_lockit", diary.now(), None, "", "글")
    got = {}
    with repo.session(ua) as s1:
        assert diary.lock(s1, "e_lockit")

        def other():
            with repo.session(ua) as s2:     # s1 이 커밋할 때까지 기다렸다가 조건을 다시 본다
                got["b"] = diary.lock(s2, "e_lockit")
        t = threading.Thread(target=other)
        t.start()
        time.sleep(0.3)
    t.join(5)
    assert got == {"b": False}


def test_delete_me_real(repo):
    """M3: 실제 Supabase · Chroma 로 DELETE /me → 모든 표 · 벡터 · auth 계정에서 그 user_id 가 0건."""
    from fastapi.testclient import TestClient

    import main
    from app.core import seed
    from app.deps import get_repo
    from app.repository.diary import WIPE
    pw = seed._read(seed.ENV_LOCAL)["DEV_TEST_PASSWORD"]
    seed.admin_user("it-del@my-universe.test", pw)
    token, uid = seed.token("it-del@my-universe.test", pw)
    main.app.dependency_overrides[get_repo] = lambda: repo
    try:
        c = TestClient(main.app)
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/diary", headers=h, json={"title": DAY1[0], "text": DAY1[1]})
        assert r.status_code == 200 and repo.vectors.get(uid)
        c.post("/feedback", headers=h, json={"target": "message", "value": "오늘은 살살"})
        assert c.delete("/me", headers=h).status_code == 204
        assert c.get("/me", headers=h).status_code == 401
    finally:
        main.app.dependency_overrides.clear()
    with psycopg.connect(config.DATABASE_URL) as conn:
        left = {t: conn.execute(f"select count(*) from {t} where user_id = %s", [uid]).fetchone()[0] for t in WIPE}
        assert sum(left.values()) == 0, left
    assert repo.vectors.get(uid) == {}
    with pytest.raises(httpx.HTTPStatusError):
        seed.token("it-del@my-universe.test", pw)
