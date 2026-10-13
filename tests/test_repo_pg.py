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


@pytest.fixture(scope="module", autouse=True)
def migrated():
    with psycopg.connect(config.DATABASE_URL) as c:
        if not c.execute("select 1 from pg_roles where rolname = 'app_user'").fetchone():
            pytest.fail("로컬 DB 에 보안 마이그레이션(20261009000000_v8_security)이 없어요: supabase migration up --local")


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
        seed.agree(r, uid)
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
        mj = next(p for p in diary.people(s) if p["name"] == NAMES[0])   # 사람별 생각(WS14): 두 날 모두, 먼저 쓴 날부터
        pts = views.person_thoughts(s, mj["id"])["thoughts"]
        assert [t["entry_id"] for t in pts][0] == r1["id"] and pts[-1]["entry_id"] == r2["id"]
        ex = views.export(s)                                              # JSON 내려받기(WS15): 원문 · 실명 그대로, 먼저 쓴 것부터
        assert [r["id"] for r in ex["records"]] == [r1["id"], r2["id"]] and ex["records"][0]["text"] == DAY1[1]
        assert NAMES[0] in {n for t in ex["records"][0]["thoughts"] for n in t["people"]} and ex["domains"]
        assert r2["observation"]["state"] != "비교할 지난 글 없음" and r1["observation"]["state"] == "비교할 지난 글 없음"
    with repo.session(ub) as s:
        assert views.person_thoughts(s, mj["id"]) is None
        assert views.export(s, r1["id"]) is None and views.export(s)["records"] == []
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


def test_crisis_and_caps_on_pg(repo, users, monkeypatch):
    """최근 바뀐 길을 Postgres 로: 위기 글(시험 단계)도 평소 결과 + 위로 한마디 + 안부 한 줄, 위기 표시 · 위로 여부는 암호문 안.
    운영 상한(기본 0 = 끔)은 env 로 켰을 때 runs 로 센다."""
    from fastapi.testclient import TestClient

    import main
    from app.deps import get_repo
    from tests.test_graph_flow import CRISIS
    monkeypatch.setattr(config, "DAILY_ENTRY_LIMIT", 1)
    monkeypatch.setattr(config, "MONTHLY_COST_CAP_USD", 100.0)
    main.app.dependency_overrides[get_repo] = lambda: repo
    try:
        c = TestClient(main.app)
        h = {"Authorization": f"Bearer {users['a'][0]}"}
        r = c.post("/diary/stream", headers=h, json={"title": CRISIS[0], "text": CRISIS[1]})
        res = json.loads([b for b in r.text.split("\n\n") if b.startswith("event: result")][0].split("data: ", 1)[1])
        assert res["status"] == "done" and res["crisis"] is True and res["thoughts"]
        assert res["message"]["mode"] == "comfort" and res["message"]["check_in"]
        assert c.get("/universe", headers=h).json()["planets"][0]["id"] == res["id"]
        r = c.post("/diary", headers=h, json={"text": "하나 더"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "daily_limit"
    finally:
        main.app.dependency_overrides.clear()
    with psycopg.connect(config.DATABASE_URL) as conn:
        cols = {x[0] for x in conn.execute("select column_name from information_schema.columns "
                                           "where table_schema = 'public' and table_name in ('entries', 'messages')").fetchall()}
        blob = b"".join(bytes(x[0]) for x in conn.execute("select enc from entries where user_id = %s", [users["a"][1]]))
    assert not cols & {"crisis", "mode", "check_in"} and "죽고".encode() not in blob


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
    seed.agree(repo, uid)
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


def test_record_fields_on_pg(repo, users):
    """WS11 기록 칸을 Postgres 로: 새 칸 저장 · 읽기, 같은 글 찾기(사용자별 HMAC), 원본 표시 유일 색인, 설정 번호."""
    from app.agents import graph
    from app.repository import diary, views
    ua = users["a"][1]
    eid = diary.new_id("e")
    with repo.session(ua) as s:
        diary.create_entry(s, eid, diary.parse_dt("2026-10-01T22:00:00+09:00"), None, "9/30 걷기", DAY2[1], "사진", "photo-1")
    graph.run(repo, ua, eid)
    with repo.session(ua) as s:
        r = views.entry_result(s, eid)
        assert (r["source"], r["day"], r["day_basis"], r["record_type"]) == ("사진", "2026-09-30", "확실", "생각·성찰")
        w = diary.parse_dt("2026-10-01T09:00:00+09:00")
        assert diary.same_entry(s, "9/30 걷기", DAY2[1], w) == eid and diary.same_entry(s, "다른", "글", w, "사진", "photo-1") == eid
        assert diary.same_entry(s, "9/30 걷기", DAY2[1], diary.parse_dt("2026-10-02T09:00:00+09:00")) is None   # 다른 날
        assert {x["studio_config"] for x in s.rows("runs", entry_id=eid)} == {"2/2"}
    with pytest.raises(psycopg.errors.UniqueViolation):   # 같은 원본을 두 번 가져오지 못함(DB 가 막음)
        with repo.session(ua) as s:
            diary.create_entry(s, "e_dupref", diary.now(), None, "", "다른 글", "사진", "photo-1")
    with repo.session(users["b"][1]) as s:
        assert diary.same_entry(s, "9/30 걷기", DAY2[1], diary.parse_dt("2026-10-01T22:00:00+09:00")) is None
    with psycopg.connect(config.DATABASE_URL) as c:
        ref, h = c.execute("select source_ref, content_hash from entries where id = %s", [eid]).fetchone()
    assert len(ref) == len(h) == 64 and "photo" not in ref


def test_consents_rls_append_only_and_data_api(repo, users):
    """WS24: 동의 기록은 그 사용자만 보고(RLS), 백엔드 역할도 고치지 못하며(update 권한 없음), 필수 셋이 빠진 줄은 DB 가 거부.
    Data API(/rest/v1)로는 읽지도 쓰지도 못한다."""
    from app.api import consent
    from app.core import seed
    (ta, ua), (_, ub) = users["a"], users["b"]
    for u in (ua, ub):
        seed.wipe(repo, u)   # 계정 지우기 = 동의 기록도 지움(repo 픽스처가 넣어 둔 동의)
    with repo.session(ua) as s:
        consent.save(s, operator_read=True)
        assert not consent.needed(s) and consent.operator_read(s)
    with repo.session(ub) as s:
        assert s.rows("consents") == [] and consent.needed(s)
    with psycopg.connect(config.DATABASE_URL) as c:   # 코드가 user_id 를 빠뜨려도 RLS 가 막는다
        c.execute("set local role app_user")
        c.execute("select set_config('app.user_id', %s, true)", [ub])
        assert c.execute("select count(*) from consents").fetchone()[0] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with repo.session(ua) as s:
            s.update("consents", {"operator_read": False})
    with pytest.raises(psycopg.errors.CheckViolation):
        with repo.session(ua) as s:
            s.insert("consents", {"id": "c_bad", "version": consent.VERSION, "required": True, "sensitive": False, "age14": True})
    base = f"{config.SUPABASE_URL}/rest/v1/consents"
    user = {"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {ta}", "Content-Type": "application/json"}
    tries = [httpx.get(base, headers=user, params={"select": "*"}),
             httpx.post(base, headers=user, json={"id": "c_x", "user_id": ua, "version": "x", "required": True,
                                                  "sensitive": True, "age14": True})]
    assert [r.status_code for r in tries if r.status_code not in (401, 403)] == []
    with repo.session(ua) as s:
        assert [r["operator_read"] for r in s.rows("consents")] == [True]
