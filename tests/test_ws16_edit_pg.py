"""WS16 우주 고치기를 로컬 Supabase(Postgres · Auth · RLS · FK) + ChromaDB 로: 실제 토큰으로 해 추가 · 옮기기 · 합치기 ·
생각 고치기 · 사람과 그 생각 지우기, 남의 것은 못 고침. 멈춘 기록을 합친 뒤 이어 하면 FK 오류 없이 끝남. 외부 AI 는 가짜."""
import json

import pytest

from tests.test_repo_pg import DAY1, DAY2, migrated, pytestmark, repo  # noqa: F401  (픽스처 · 건너뛰기 조건)


@pytest.fixture(scope="module")
def users():
    """다른 갈래 시험(it-a · it-b)과 겹치지 않는 계정."""
    from app.core import seed
    pw = seed._read(seed.ENV_LOCAL)["DEV_TEST_PASSWORD"]
    out = {}
    for k in ("a", "b"):
        email = f"it-ws16-{k}@my-universe.test"
        seed.admin_user(email, pw)
        out[k] = seed.token(email, pw)
    return out


def _result(r):
    blocks = [b for b in r.text.split("\n\n") if b.startswith(("event: result", "event: error"))]
    return blocks[-1].split("\n")[0].removeprefix("event: "), json.loads(blocks[-1].split("data: ", 1)[1])


def test_edit_on_pg(repo, users, monkeypatch):  # noqa: F811
    from fastapi.testclient import TestClient

    import main
    from app.agents import tools
    from app.deps import get_repo
    orig = repo.fake._record

    def rec(html):   # 둘째 날은 다른 작은 별(합치기 후보)
        d = orig(html)
        if "사흘째" in html:
            for t in d["thoughts"]:
                t["topic"] = ["걷기 습관"]
        return d
    repo.fake._record = rec
    monkeypatch.setattr(tools, "sun_vectors", lambda: ({}, None))
    main.app.dependency_overrides[get_repo] = lambda: repo
    try:
        c = TestClient(main.app)
        ha, hb = ({"Authorization": f"Bearer {users[k][0]}"} for k in ("a", "b"))
        k1, r1 = _result(c.post("/diary/stream", headers=ha, json={"title": DAY1[0], "text": DAY1[1]}))
        assert k1 == "result"
        repo.fake.fail_observe = 2   # 둘째 날은 관측에서 멈춤 → 단계 저장값이 '걷기 습관' 별 id 를 들고 있음
        k2, err = _result(c.post("/diary/stream", headers=ha, json={"title": DAY2[0], "text": DAY2[1]}))
        assert k2 == "error"
        a = r1["thoughts"][0]["star_id"]
        stars = {x["name"]: x["id"] for x in c.get("/universe", headers=ha).json()["stars"]}
        assert list(stars.values()) == [a]   # 멈춘 기록은 아직 우주에 없다
        # 해 추가 → 별 옮기기 → 행성이 따라감
        sun = c.post("/suns", headers=ha, json={"name": "통일 사역"}).json()
        assert sun["custom"] and sun["axis"] == "사용자 영역"
        assert c.patch(f"/suns/{sun['id']}", headers=ha, json={"axis": "공동체"}).json()["axis"] == "공동체"
        assert c.patch(f"/suns/{sun['id']}", headers=hb, json={"axis": "여가"}).status_code == 404
        assert c.patch(f"/stars/{a}", headers=hb, json={"sun_id": sun["id"]}).status_code == 404
        assert c.patch(f"/stars/{a}", headers=ha, json={"sun_id": sun["id"]}).status_code == 200
        assert c.get("/universe", headers=ha).json()["planets"][0]["sun_id"] == sun["id"]
        # 멈춘 기록의 별을 합친 뒤 이어 하면 FK 오류 없이 합친 별로 저장
        with repo.session(users["a"][1]) as s:
            b = s.conn.execute("select id from stars where id <> %s", [a]).fetchone()["id"]
        assert c.post("/stars/merge", headers=hb, json={"from_id": b, "into_id": a}).status_code == 404
        assert c.post("/stars/merge", headers=ha, json={"from_id": b, "into_id": a}).status_code == 200
        k3, r2 = _result(c.post(f"/diary/{err['entry_id']}/resume/stream", headers=ha))
        assert k3 == "result" and {t["star_id"] for t in r2["thoughts"]} == {a} and {t["sun_id"] for t in r2["thoughts"]} == {sun["id"]}
        # 생각 고치기
        vow = next(t for t in r1["thoughts"] if t["kind"] == "다짐")
        assert c.patch(f"/thoughts/{vow['id']}", headers=hb, json={"kind": "소망"}).status_code == 404
        t = c.patch(f"/thoughts/{vow['id']}", headers=ha, json={"kind": "소망", "value": "성취"}).json()
        assert (t["kind"], t["value"], t["state"]) == ("소망", "성취", None)
        # 사람과 그 사람이 나온 생각 지우기(관계 · 벡터까지, FK 순서)
        mj = next(p for p in c.get("/people", headers=ha).json()["people"] if p["name"] == "민준")
        tids = {t["id"] for t in c.get(f"/people/{mj['id']}/thoughts", headers=ha).json()["thoughts"]}
        assert tids and tids <= set(repo.vectors.get(users["a"][1]))
        assert c.delete(f"/people/{mj['id']}/with-thoughts", headers=hb).status_code == 404
        r = c.delete(f"/people/{mj['id']}/with-thoughts", headers=ha)
        assert r.status_code == 200 and r.json()["hidden"] > 0
        with repo.session(users["a"][1]) as s:
            assert s.conn.execute("select count(*) as n from thoughts where id = any(%s)", [list(tids)]).fetchone()["n"] == 0
            assert s.conn.execute("select count(*) as n from relations where from_thought = any(%s) or to_thought = any(%s)",
                                  [list(tids)] * 2).fetchone()["n"] == 0
            assert s.conn.execute("select count(*) as n from thoughts").fetchone()["n"] > 0   # 다른 생각은 남음
            n = s.conn.execute("select count(*) as n from feedback where value in ('축 고침', '옮김', '합침', '고침')").fetchone()["n"]
        assert n == 5   # 오답 재료: 축 · 옮김 · 합침 · 종류 · 가치
        left = set(repo.vectors.get(users["a"][1]))
        assert left and not left & tids   # 그 사람이 나온 생각의 벡터만 지움
    finally:
        main.app.dependency_overrides.clear()
