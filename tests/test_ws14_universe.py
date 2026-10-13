"""WS14 우주 화면이 쓰는 API: 사람별 생각(시간순) · 이어진 선의 그때 → 지금 인용 · 북극성의 닿은 순간 목록."""
from app.repository import diary
from tests.test_api_flow import H1, H2, client, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, DAY2, U1, env  # noqa: F401  (env 픽스처)


def two_days(client):  # noqa: F811
    _, ev1 = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    _, ev2 = write(client, *DAY2, "2026-10-03T22:00:00+09:00")
    return ev1[-1][1], ev2[-1][1]


def test_person_thoughts_in_time_order(client):  # noqa: F811
    r1, r2 = two_days(client)
    mj = next(p for p in client.get("/people", headers=H1).json()["people"] if p["name"] == "민준")
    out = client.get(f"/people/{mj['id']}/thoughts", headers=H1).json()
    assert out["person"] == {"id": mj["id"], "name": "민준", "relation": mj["relation"]}
    ts = out["thoughts"]
    assert ts and all(mj["id"] in t["people"] for t in ts)
    assert [t["entry_id"] for t in ts] == sorted((t["entry_id"] for t in ts), key=[r1["id"], r2["id"]].index)
    assert {t["entry_id"] for t in ts} == {r1["id"], r2["id"]}           # 두 날 모두, 먼저 쓴 날부터
    assert [t["written_at"] for t in ts] == sorted(t["written_at"] for t in ts)
    first = ts[0]
    assert first["title"] == DAY1[0] and first["quote"] and first["kind"] and "state" in first
    assert first["quote"] in DAY1[1]                                      # 원문 인용


def test_person_thoughts_not_found_and_isolated(client):  # noqa: F811
    two_days(client)
    mj = next(p for p in client.get("/people", headers=H1).json()["people"] if p["name"] == "민준")
    assert client.get("/people/p_nobody/thoughts", headers=H1).status_code == 404
    assert client.get(f"/people/{mj['id']}/thoughts", headers=H2).status_code == 404   # 남의 사람
    assert client.get("/people/bad%20id/thoughts", headers=H1).status_code == 422
    added = client.post("/people", headers=H1, json={"name": "하린", "relation": "동생"}).json()
    assert client.get(f"/people/{added['id']}/thoughts", headers=H1).json()["thoughts"] == []


def test_links_carry_then_and_now_quotes(client, env):  # noqa: F811
    r1, r2 = two_days(client)
    u = client.get("/universe", headers=H1).json()
    link = u["links"][0]
    rel = next(x for x in r2["relations"] if x["id"] == link["id"])
    then = next(t for t in r1["thoughts"] if t["id"] == rel["from"])
    now = next(t for t in r2["thoughts"] if t["id"] == rel["to"])
    assert link["from_quote"] == then["quote"] and link["to_quote"] == now["quote"]
    assert link["from_quote"] in DAY1[1] and link["to_quote"] in DAY2[1]


def test_north_star_lists_reached_moments(client, env):  # noqa: F811
    client.post("/aspiration", headers=H1, json={"want": "꾸준한 사람", "values": ["성취"]})
    r1, _ = two_days(client)
    with env.repo.session(U1) as s:   # 관측 Agent 가 찾은 닿은 순간 하나(가짜 Studio 는 찾지 않으므로 직접)
        asp = diary.aspirations(s)[-1]
        s.insert("aspiration_reached", {"id": "rc1", "aspiration_id": asp["id"], "entry_id": r1["id"],
                                        "thought_id": r1["thoughts"][0]["id"], "at": diary.parse_dt(r1["written_at"]),
                                        "enc": diary.seal(s, "aspiration_reached", "rc1", {"quote": "매일 아침 30분 걷기", "note": ""})})
    ns = client.get("/universe", headers=H1).json()["north_star"]
    assert ns["reached_planets"] == [r1["id"]]
    assert ns["reached"] == [{"entry_id": r1["id"], "quote": "매일 아침 30분 걷기", "at": r1["written_at"]}]
    client.delete(f"/diary/{r1['id']}", headers=H1)                       # 지운 기록의 닿은 순간은 목록에서 빠짐
    assert client.get("/universe", headers=H1).json()["north_star"]["reached"] == []
