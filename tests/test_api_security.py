"""보안 검토(docs/security-review-v8.md) 고침 시험: 허용 목록(M6) · 로그인 오류(L2) · 계정 지우기(M3) · 이어 하기 상한(M8) ·
DB 잠금(M9 · L4) · 하루 글 수(L5) · /docs 끄기(L6) · 제어 문자(L7) · 지우기 범위(L8 · L9) · 마음 상태 enc(M5) · 로그 KST."""
import importlib
import json
from datetime import timedelta

import httpx
import pytest

import main
from app.core import auth, config, logger
from app.repository import diary
from tests.test_api_flow import H1, H2, U2, client, events, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import CRISIS, DAY1, DAY2, U1, env  # noqa: F401  (env 픽스처)


def _row(env, table, **eq):  # noqa: F811
    return [r for r in env.repo.store.tables.get(table, []) if all(r.get(k) == v for k, v in eq.items())]


##################################################
# 로그인 · 허용 목록
##################################################

@pytest.fixture
def supa(monkeypatch):
    """Supabase /auth/v1/user 가짜: 토큰 → (상태, 본문)."""
    answers = {}
    monkeypatch.setattr(config, "SUPABASE_URL", "http://supabase.test")
    auth._cache.clear()

    def get(url, headers, timeout):
        status, body = answers[headers["Authorization"].removeprefix("Bearer ")]
        return httpx.Response(status, text=body if isinstance(body, str) else json.dumps(body))
    monkeypatch.setattr(auth.httpx, "get", get)
    yield answers
    auth._cache.clear()


def test_allowed_emails(supa, monkeypatch):
    supa["a"] = (200, {"id": U1, "email": "Dongkyu@Example.com"})
    supa["b"] = (200, {"id": U2, "email": "stranger@example.com"})
    assert auth.get_user("Bearer b")["id"] == U2                     # 목록이 없으면 누구나
    monkeypatch.setattr(config, "ALLOWED_EMAILS", {"dongkyu@example.com", "hyunho@example.com"})
    assert auth.get_user("Bearer a")["id"] == U1                     # 대소문자 무시
    with pytest.raises(auth.ApiError) as e:
        auth.get_user("Bearer b")
    assert (e.value.status, e.value.code) == (403, "not_allowed")


def test_allowed_emails_api_403(supa, monkeypatch, env):  # noqa: F811
    from fastapi.testclient import TestClient

    from app.deps import get_repo
    supa["b"] = (200, {"id": U2, "email": "stranger@example.com"})
    monkeypatch.setattr(config, "ALLOWED_EMAILS", {"dongkyu@example.com"})
    main.app.dependency_overrides[get_repo] = lambda: env.repo
    try:
        r = TestClient(main.app).get("/me", headers={"Authorization": "Bearer b"})
    finally:
        main.app.dependency_overrides.clear()
    assert r.status_code == 403 and r.json()["error"] == {"code": "not_allowed", "message": "초대된 사람만 쓸 수 있어요."}


@pytest.mark.parametrize("status,body,code", [(500, "oops", "auth_unavailable"), (200, "<html>", "auth_unavailable"),
                                              (401, {"msg": "bad"}, "unauthorized"), (200, {"email": "x"}, "unauthorized")])
def test_auth_errors(supa, status, body, code):
    supa["t"] = (status, body)
    with pytest.raises(auth.ApiError) as e:
        auth.verify("t")
    assert e.value.code == code


##################################################
# 계정 지우기 (DELETE /me)
##################################################

@pytest.fixture
def admin(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "SUPABASE_URL", "http://supabase.test")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "service-key")

    def delete(url, headers, timeout):
        calls.append(url)
        return httpx.Response(200, text="{}")
    monkeypatch.setattr(auth.httpx, "delete", delete)
    return calls


@pytest.mark.parametrize("key, bearer", [("eyJhbGciOi.legacy", True), ("sb_secret_new", False)])
def test_delete_account_key_headers(monkeypatch, key, bearer):
    # 예전 service_role(JWT)은 Bearer 로도, 새 sb_secret_ 키는 apikey 헤더로만 보낸다
    sent = {}
    monkeypatch.setattr(config, "SUPABASE_URL", "http://supabase.test")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", key)
    monkeypatch.setattr(auth.httpx, "delete", lambda url, headers, timeout: sent.update(headers) or httpx.Response(204))
    auth.delete_account("u1")
    assert sent["apikey"] == key and ("Authorization" in sent) == bearer


def test_delete_me_removes_everything(client, env, admin):  # noqa: F811
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    write(client, *CRISIS, "2026-10-02T23:30:00+09:00")
    write(client, *DAY1, "2026-10-01T22:00:00+09:00", h=H2)
    client.post("/feedback", headers=H1, json={"target": "message", "value": "오늘은 위로만"})
    client.post("/aspiration", headers=H1, json={"want": "꾸준한 사람", "values": ["성취"]})
    assert env.repo.vectors.get(U1) and _row(env, "people", user_id=U1)
    assert client.delete("/me", headers=H1).status_code == 204
    assert admin == [f"http://supabase.test/auth/v1/admin/users/{U1}"]
    left = [t for t, rows in env.repo.store.tables.items() for r in rows if r.get("user_id") == U1]
    assert left == [] and env.repo.vectors.get(U1) == {}
    assert env.repo.vectors.get(U2) and client.get("/diary", headers=H2).json()["entries"]   # 다른 사람 것은 그대로


def test_delete_me_vector_failure_keeps_account(client, env, admin, monkeypatch):  # noqa: F811
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")

    def boom(uid, **kw):
        raise ConnectionError("chroma down")
    monkeypatch.setattr(env.repo.vectors, "delete", boom)
    r = client.delete("/me", headers=H1)
    assert r.status_code == 503 and r.json()["error"]["code"] == "vector_delete_failed"
    assert admin == [] and client.get("/diary", headers=H1).json()["entries"]


def test_delete_me_unconfigured_or_admin_error(client, env, admin, monkeypatch):  # noqa: F811
    monkeypatch.setattr(auth.httpx, "delete", lambda url, headers, timeout: httpx.Response(500, text="x"))
    assert client.delete("/me", headers=H1).json()["error"]["code"] == "account_delete_failed"
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")
    r = client.delete("/me", headers=H1)
    assert r.status_code == 503 and r.json()["error"]["code"] == "account_delete_unconfigured"


def test_delete_me_waits_for_running_entry(client, env, admin):  # noqa: F811
    with env.repo.session(U1) as s:
        diary.create_entry(s, "e_run", diary.now(), None, "", "글")
        assert diary.lock(s, "e_run")
    assert client.delete("/me", headers=H1).status_code == 409 and admin == []


##################################################
# 잠금 · 이어 하기 상한 · 하루 글 수
##################################################

def test_lock_is_conditional_and_expires(env, monkeypatch):  # noqa: F811
    with env.repo.session(U1) as s:
        diary.create_entry(s, "e_a", diary.now(), None, "", "글")
        assert diary.lock(s, "e_a") and not diary.lock(s, "e_a")      # 두 번째(다른 인스턴스)는 못 잡음
        s.update("entries", {"locked_until": diary.now() - timedelta(seconds=1)}, id="e_a")
        assert diary.lock(s, "e_a")                                    # 만료된 잠금은 다시 잡힘
        diary.unlock(s, "e_a")
        assert not diary.is_locked(s.rows("entries", id="e_a")[0]) and diary.lock(s, "e_a")


def test_running_entry_states(client, env):  # noqa: F811
    with env.repo.session(U1) as s:
        diary.create_entry(s, "e_b", diary.now(), None, "", "글")
        diary.lock(s, "e_b")
    assert client.get("/diary/e_b", headers=H1).json()["status"] == "processing"
    assert client.delete("/diary/e_b", headers=H1).status_code == 409
    assert client.post("/diary/e_b/resume/stream", headers=H1).status_code == 409
    assert client.delete("/diary/e_b", headers=H2).status_code == 404        # 남의 기록은 잠겨 있어도 404(L4)
    with env.repo.session(U1) as s:
        s.update("entries", {"locked_until": diary.now() - timedelta(seconds=1)}, id="e_b")
    assert client.get("/diary/e_b", headers=H1).json()["status"] == "failed"   # 멈춘 기록 → 이어서 하기
    assert client.delete("/diary/e_b", headers=H1).status_code == 204


def test_finished_run_releases_lock(client, env):  # noqa: F811
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    eid = ev[-1][1]["id"]
    assert _row(env, "entries", id=eid)[0]["locked_until"] is None
    assert [r["step"] for r in _row(env, "runs", entry_id=eid)][0] == "start"


def test_resume_limits(client, env, monkeypatch):  # noqa: F811
    env.fake.fail_observe = 100
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    eid = ev[-1][1]["entry_id"]
    monkeypatch.setattr(config, "RESUME_LIMIT", 2)
    for _ in range(2):
        assert events(client.post(f"/diary/{eid}/resume/stream", headers=H1).text)[-1][0] == "error"
    r = client.post(f"/diary/{eid}/resume/stream", headers=H1)
    assert r.status_code == 429 and r.json()["error"]["code"] == "resume_limit"
    monkeypatch.setattr(config, "RESUME_LIMIT", 9)
    monkeypatch.setattr(config, "MONTHLY_COST_CAP_USD", 0.0)
    r = client.post(f"/diary/{eid}/resume/stream", headers=H1)
    assert r.status_code == 429 and r.json()["error"]["code"] == "monthly_budget"


def test_daily_limit_counts_started_entries(client, env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DAILY_ENTRY_LIMIT", 2)
    with env.repo.session(U1) as s:   # 시드한 글(처리 안 함)은 세지 않는다
        for i in range(3):
            diary.create_entry(s, f"e_seed{i}", diary.now(), None, "", "글")
    _, ev = write(client, *CRISIS, "2026-10-02T23:30:00+09:00")
    assert ev[-1][0] == "result"
    assert client.delete(f"/diary/{ev[-1][1]['id']}", headers=H1).status_code == 204
    write(client, *CRISIS, "2026-10-02T23:30:00+09:00")
    r = client.post("/diary", headers=H1, json={"text": "하나 더"})   # 지워도 줄지 않는다
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_limit"
    with env.repo.session(U1) as s:  # 예전 기록을 오늘 이어 하는 것도 하루 수에 든다
        diary.add_run(s, "e_seed0", "start")
        s.update("runs", {"created_at": diary.now() - timedelta(days=2)}, entry_id="e_seed0")
    r = client.post("/diary/e_seed0/resume/stream", headers=H1)
    assert r.status_code == 429 and r.json()["error"]["code"] == "daily_limit"


##################################################
# 입력 · 문서 · 로그
##################################################

def test_control_chars_removed_and_bad_ids(client, env):  # noqa: F811
    r = client.post("/people", headers=H1, json={"name": "하린\u0000", "relation": "친\u0000구\u0007"})
    assert r.status_code == 200 and (r.json()["name"], r.json()["relation"]) == ("하린", "친구")
    assert client.post("/diary", headers=H1, json={"text": "\u0000\u0001"}).status_code == 422
    for path in ("/diary/e%00x", "/diary/a%20b", "/people/x.y"):
        assert client.delete(path, headers=H1).status_code == 422, path


def test_docs_off_unless_api_docs(monkeypatch):
    try:
        monkeypatch.setattr(config, "API_DOCS", False)
        from fastapi.testclient import TestClient
        c = TestClient(importlib.reload(main).app)
        assert [c.get(p).status_code for p in ("/docs", "/redoc", "/openapi.json")] == [404, 404, 404]
        monkeypatch.setattr(config, "API_DOCS", True)
        assert TestClient(importlib.reload(main).app).get("/openapi.json").status_code == 200
    finally:
        monkeypatch.undo()
        importlib.reload(main)


def test_logger_kst_and_no_mood_fields(monkeypatch, capsys):
    monkeypatch.setattr(config, "LOG_TO_FILE", False)
    monkeypatch.setattr(config, "TIMEZONE", "Asia/Seoul")
    line = logger.log("step", situations=["무거운 날"], mode="care", checks=2)
    assert line["ts"].endswith("+09:00") and "situations" not in line and "mode" not in line and line["checks"] == 2


def test_sun_vectors_missing_warns(monkeypatch, tmp_path, capsys):
    from app.agents import tools
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(config, "LOG_TO_FILE", False)
    tools.sun_vectors.cache_clear()
    try:
        assert tools.sun_vectors() == ({}, None)
        assert '"code": "sun_vectors_missing"' in capsys.readouterr().out
    finally:
        tools.sun_vectors.cache_clear()


##################################################
# 지우기 범위 · 마음 상태 enc
##################################################

def test_delete_entry_cleans_feedback_stars_auto_people(client, env):  # noqa: F811
    _, ev1 = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    _, ev2 = write(client, "", "오늘 서윤이와 피아노를 쳤다. 피아노가 즐거웠다.", "2026-10-03T22:00:00+09:00")
    e2 = ev2[-1][1]
    client.post("/feedback", headers=H1, json={"target": "entry", "target_id": e2["id"], "value": "좋아요"})
    client.post("/feedback", headers=H1, json={"target": "message", "target_id": e2["id"], "value": "별로"})
    names = lambda: {p["name"] for p in client.get("/people", headers=H1).json()["people"]}   # noqa: E731
    assert "서윤" in names()
    stars = {x["star_id"] for x in _row(env, "thoughts", entry_id=e2["id"])}
    assert client.delete(f"/diary/{e2['id']}", headers=H1).status_code == 204
    assert _row(env, "feedback", target_id=e2["id"]) == []
    assert "서윤" not in names() and "민준" in names()              # 이 글에만 나온 자동 등록 사람만 정리
    left = {r["id"] for r in _row(env, "stars")}
    assert not (stars - {x["star_id"] for x in _row(env, "thoughts")}) & left
    assert client.get(f"/diary/{ev1[-1][1]['id']}", headers=H1).json()["status"] == "done"


def test_delete_person_cleans_steps_feedback_questions(client, env):  # noqa: F811
    env.fake.fail_observe = 2
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")          # 끊긴 기록: 단계 저장값에 이름이 있음
    eid = ev[-1][1]["entry_id"]
    client.post("/feedback", headers=H1, json={"target": "app", "value": "불편한 점 한 줄", "text": "민준이 이름이 틀려요"})
    mj = next(p for p in client.get("/people", headers=H1).json()["people"] if p["name"] == "민준")
    with env.repo.session(U1) as s:
        diary.add_question(s, eid, "민준", "별명")
    assert client.delete(f"/people/{mj['id']}", headers=H1).json()["ok"]
    with env.repo.session(U1) as s:
        steps = json.dumps(diary.entry(s, eid)["steps"], ensure_ascii=False)
        fb = [diary.unseal(s, "feedback", r["id"], r["enc"]) for r in s.rows("feedback") if r["enc"]]
        assert "민준" not in steps and "민준" not in json.dumps(fb, ensure_ascii=False)
        assert [q for q in diary.questions(s) if "민준" in q["name"]] == []


def test_mood_feedback_and_settings_encrypted(client, env):  # noqa: F811
    client.post("/feedback", headers=H1, json={"target": "message", "value": "오늘은 위로만"})
    client.post("/feedback", headers=H1, json={"target": "message", "value": "좋아요"})
    raw = json.dumps([{k: str(v) for k, v in r.items()} for t in ("feedback", "profiles") for r in env.repo.store.tables[t]],
                     ensure_ascii=False)
    assert "위로만" not in raw and "comfort_only_today" not in raw
    assert client.get("/me", headers=H1).json()["settings"]["comfort_only_today"] == diary.today()
    assert client.get("/stats", headers=H1).json()["feedback"] == {"오늘은 위로만": 1, "좋아요": 1}
