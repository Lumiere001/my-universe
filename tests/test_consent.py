"""첫 로그인 동의(WS24): 동의 전에는 기록을 만들 수 없고(외부 AI 로 나가는 길), 문구 판이 바뀌면 다시 묻는다."""
import pytest
from fastapi.testclient import TestClient

import main
from app.api import consent
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.repository import diary
from tests.test_api_flow import H1, H2, TOKENS, U1, U2, events
from tests.test_graph_flow import DAY1, env  # noqa: F401  (env 픽스처)

OK = {"version": consent.VERSION, "required": True, "sensitive": True, "age14": True}


@pytest.fixture
def c(env):  # noqa: F811  test_api_flow 의 client 와 같되 동의는 하지 않은 두 사용자
    from fastapi import Header

    def user(authorization: str = Header(default="")):
        if authorization.removeprefix("Bearer ") not in TOKENS:
            raise ApiError(401, "unauthorized", "로그인이 필요해요.")
        return TOKENS[authorization.removeprefix("Bearer ")]
    main.app.dependency_overrides[get_user] = user
    main.app.dependency_overrides[get_repo] = lambda: env.repo
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_no_consent_blocks_writing_but_not_reading(c, env):  # noqa: F811
    g = c.get("/consent", headers=H1).json()
    assert g == {"version": consent.VERSION, "needed": True, "agreed": None}
    r = c.post("/diary/stream", headers=H1, json={"title": DAY1[0], "text": DAY1[1]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"
    assert c.post("/diary", headers=H1, json={"text": "글"}).status_code == 403
    with env.repo.session(U1) as s:   # 동의 전에 만들어진 기록(옛 판 동의 · 시드)도 이어 하기를 막는다
        diary.create_entry(s, "e_old", diary.now(), None, "", "글")
        diary.set_status(s, "e_old", "failed")
    r = c.post("/diary/e_old/resume/stream", headers=H1)
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"
    # 읽기 · 지우기 쪽은 열려 있다(동의하지 않은 사람도 자기 기록을 보고 지울 수 있게)
    assert c.get("/me", headers=H1).status_code == 200
    assert c.get("/diary", headers=H1).status_code == 200
    assert c.delete("/diary/e_old", headers=H1).status_code == 204


def test_agree_then_write(c, env):  # noqa: F811
    r = c.post("/consent", headers=H1, json=OK)
    assert r.status_code == 200 and r.json()["needed"] is False
    assert r.json()["agreed"]["version"] == consent.VERSION and r.json()["agreed"]["operator_read"] is False
    r = c.post("/diary/stream", headers=H1, json={"title": DAY1[0], "text": DAY1[1]})
    assert r.status_code == 200 and events(r.text)[-1][0] == "result"
    # 다른 사람의 동의와는 상관없다
    assert c.get("/consent", headers=H2).json()["needed"] is True
    assert c.post("/diary", headers=H2, json={"text": "글"}).status_code == 403


@pytest.mark.parametrize("patch, status, code", [
    ({"age14": False}, 403, "under_14"),
    ({"sensitive": False}, 422, "consent_missing"),
    ({"required": False}, 422, "consent_missing"),
    ({"version": "2026-01-01"}, 409, "consent_outdated"),
    ({"extra": 1}, 422, "invalid_input"),
])
def test_bad_consent_saves_nothing(c, env, patch, status, code):  # noqa: F811
    r = c.post("/consent", headers=H1, json={**OK, **patch})
    assert r.status_code == status and r.json()["error"]["code"] == code
    with env.repo.session(U1) as s:
        assert s.rows("consents") == [] and consent.needed(s)


def test_new_version_asks_again(c, env, monkeypatch):  # noqa: F811
    assert c.post("/consent", headers=H1, json=OK).status_code == 200
    monkeypatch.setattr(consent, "VERSION", "2099-01-01")   # 문구가 바뀜
    g = c.get("/consent", headers=H1).json()
    assert g["needed"] is True and g["agreed"]["version"] == OK["version"]
    assert c.post("/diary", headers=H1, json={"text": "글"}).status_code == 403
    assert c.post("/consent", headers=H1, json=OK).status_code == 409          # 옛 문구로는 동의 안 됨
    assert c.post("/consent", headers=H1, json={**OK, "version": "2099-01-01"}).json()["needed"] is False


def test_operator_read_is_optional_and_can_be_withdrawn(c, env):  # noqa: F811
    with env.repo.session(U1) as s:
        assert consent.operator_read(s) is False
    c.post("/consent", headers=H1, json={**OK, "operator_read": True})
    with env.repo.session(U1) as s:
        assert consent.operator_read(s) is True
    r = c.post("/consent", headers=H1, json=OK)   # 다시 동의하며 선택을 끔 = 거둠
    assert r.json()["agreed"]["operator_read"] is False
    with env.repo.session(U1) as s:
        assert consent.operator_read(s) is False and len(s.rows("consents")) == 2   # 기록은 덧붙이기만
    with env.repo.session(U2) as s:
        assert consent.operator_read(s) is False


def test_consent_needs_login(c):
    assert c.get("/consent").status_code == 401 and c.post("/consent", json=OK).status_code == 401
