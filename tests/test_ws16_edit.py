"""WS16 우주 고치기 API: 해 추가(기준 축 AI 제안 + 사용자 변경) · 작은 별 옮기기 · 합치기 제안 → 확인 · 생각 종류 · 가치 고치기 ·
사람 지울 때 그 사람이 나온 생각 숨기기. 고친 내용은 오답 재료(feedback)로 남고, 남의 것은 못 고친다. 메모리 저장소 · 가짜 외부 호출."""
import hashlib

import pytest

from app.agents import tools
from app.repository import diary
from tests.test_api_flow import H1, H2, U2, client, events, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, DAY2, U1, env  # noqa: F401  (env 픽스처)

D1, D2 = "2026-10-01T22:00:00+09:00", "2026-10-03T22:00:00+09:00"


def fake_vec(t):   # FakeUpstage._embed 와 같은 벡터
    return [b / 255 for b in hashlib.sha256(t.encode()).digest()[:8]]


@pytest.fixture
def axes(monkeypatch):
    """기준 축 벡터(가짜 임베딩 8차원): '통일 사역'은 공동체와 같은 방향."""
    monkeypatch.setattr(tools, "sun_vectors", lambda: ({"공동체": [fake_vec("통일 사역")], "여가": [fake_vec("놀이")]}, [0.0] * 8))


def topic_on(env, word, topic):  # noqa: F811
    """가짜 기록 Agent: 본문에 word 가 있으면 주제를 topic 으로."""
    orig = env.fake._record

    def rec(html):
        d = orig(html)
        if word in html:
            for t in d["thoughts"]:
                t["topic"] = [topic]
        return d
    env.fake._record = rec


def lessons(env, uid=U1, **eq):  # noqa: F811
    with env.repo.session(uid) as s:
        return [{**r, "data": diary.unseal(s, "feedback", r["id"], r["enc"])} for r in s.rows("feedback", **eq)]


def uni(client, h=H1):  # noqa: F811
    return client.get("/universe", headers=h).json()


##################################################
# 해 추가 · 기준 축
##################################################

def test_add_sun_ai_axis_then_user_changes(client, env, axes):  # noqa: F811
    r = client.post("/suns", headers=H1, json={"name": "  통일   사역 "})
    assert r.status_code == 200, r.text
    sun = r.json()
    assert sun["name"] == "통일 사역" and sun["custom"] is True
    assert sun["axis"] == "공동체" and sun["suggested"] == {"axis": "공동체", "basis": "임베딩"}   # 대표 낱말 없음 → 임베딩
    assert env.fake.calls["embed"] == 1
    with env.repo.session(U1) as s:
        run = s.rows("runs", step="suggest_axis")
    assert len(run) == 1 and run[0]["calls"] == 1 and run[0]["entry_id"] is None   # 비용은 runs 로 센다
    # 우주에 새 해가 뜬다(아직 행성이 없어도 사용자 해)
    assert any(x["id"] == sun["id"] and x["custom"] for x in uni(client)["suns"])
    lst = client.get("/suns", headers=H1).json()
    assert lst["axes"][-1] == "사용자 영역" and len(lst["axes"]) == 10
    assert next(x for x in lst["suns"] if x["id"] == sun["id"])["axis"] == "공동체"
    # 사용자가 축을 바꿈 → 고친 값은 오답 재료
    r = client.patch(f"/suns/{sun['id']}", headers=H1, json={"axis": "영성·신앙"})
    assert r.status_code == 200 and r.json()["axis"] == "영성·신앙"
    les = lessons(env, target="sun")
    assert [x["value"] for x in les] == ["축 고침"]
    assert les[0]["data"] == {"sun": "통일 사역", "from": "공동체", "to": "영성·신앙"}
    assert client.patch(f"/suns/{sun['id']}", headers=H1, json={"axis": "우주"}).status_code == 422
    assert client.post("/suns", headers=H1, json={"name": "통일 사역"}).status_code == 409   # 같은 이름 두 번


def test_add_sun_keyword_and_no_vectors(client, env, monkeypatch):  # noqa: F811
    r = client.post("/suns", headers=H1, json={"name": "새벽 묵상"}).json()
    assert r["axis"] == "영성·신앙" and r["suggested"]["basis"] == "낱말" and env.fake.calls["embed"] == 0
    monkeypatch.setattr(tools, "sun_vectors", lambda: ({}, None))   # 기준 축 벡터 파일이 없으면 사용자 영역
    r = client.post("/suns", headers=H1, json={"name": "통일 사역"}).json()
    assert r["axis"] == "사용자 영역" and r["suggested"]["basis"] == "없음" and env.fake.calls["embed"] == 0
    assert client.post("/suns", headers=H1, json={"name": ""}).status_code == 422


def test_add_sun_masks_names_and_needs_consent(client, env, axes):  # noqa: F811
    client.post("/people", headers=H1, json={"name": "민준", "relation": "친구"})
    r = client.post("/suns", headers=H1, json={"name": "민준과 통일"})
    assert r.status_code == 200
    assert not any("민준" in x for x in env.fake.sent)   # 실명은 외부로 나가지 않음(가명 처리)
    with env.repo.session(U2) as s:
        s.delete("consents")
    assert client.post("/suns", headers=H2, json={"name": "통일 사역"}).status_code == 403


def test_base_axis_sun_and_others(client, env):  # noqa: F811
    write(client, *DAY1, D1)
    base = next(x for x in client.get("/suns", headers=H1).json()["suns"] if x["name"] == "건강")
    assert base["axis"] == "건강" and base["custom"] is False
    assert client.patch(f"/suns/{base['id']}", headers=H1, json={"axis": "여가"}).status_code == 409
    assert client.patch(f"/suns/{base['id']}", headers=H2, json={"axis": "여가"}).status_code == 404   # 남의 해
    assert client.get("/suns", headers=H2).json()["suns"] == []


##################################################
# 작은 별 옮기기
##################################################

def test_move_star_planet_follows_and_next_entry_too(client, env, axes):  # noqa: F811
    _, ev = write(client, *DAY1, D1)
    r1 = ev[-1][1]
    star = r1["thoughts"][0]["star_id"]
    new = client.post("/suns", headers=H1, json={"name": "통일 사역"}).json()
    assert client.patch(f"/stars/{star}", headers=H2, json={"sun_id": new["id"]}).status_code == 404   # 남의 별
    assert client.patch(f"/stars/{star}", headers=H1, json={"sun_id": "d_nope"}).status_code == 404
    r = client.patch(f"/stars/{star}", headers=H1, json={"sun_id": new["id"]})
    assert r.status_code == 200 and r.json()["sun_id"] == new["id"]
    u = uni(client)
    assert next(x for x in u["stars"] if x["id"] == star)["sun_id"] == new["id"]
    assert next(p for p in u["planets"] if p["id"] == r1["id"])["sun_id"] == new["id"]   # 행성이 따라감
    assert next(x for x in u["suns"] if x["id"] == new["id"])["planet_count"] == 1
    assert all(t["sun_id"] == new["id"] for t in client.get(f"/diary/{r1['id']}", headers=H1).json()["thoughts"])
    assert [x["data"] for x in lessons(env, target="star")] == [{"topic": "아침 걷기", "from": "건강", "to": "통일 사역"}]
    _, ev2 = write(client, *DAY2, D2)   # 같은 주제의 다음 글도 옮긴 해로
    assert {t["sun_id"] for t in ev2[-1][1]["thoughts"]} == {new["id"]}


def test_edit_waits_for_running_entry(client, env):  # noqa: F811
    _, ev = write(client, *DAY1, D1)
    star = ev[-1][1]["thoughts"][0]["star_id"]
    sid = client.get("/suns", headers=H1).json()["suns"][0]["id"]
    with env.repo.session(U1) as s:
        diary.lock(s, ev[-1][1]["id"])
    assert client.patch(f"/stars/{star}", headers=H1, json={"sun_id": sid}).json()["error"]["code"] == "already_running"


##################################################
# 작은 별 합치기
##################################################

def test_merge_suggest_confirm_and_sticks(client, env):  # noqa: F811
    topic_on(env, "사흘째", "걷기 습관")
    _, ev1 = write(client, *DAY1, D1)
    _, ev2 = write(client, *DAY2, D2)
    a, b = ev1[-1][1]["thoughts"][0]["star_id"], ev2[-1][1]["thoughts"][0]["star_id"]
    assert a != b
    cands = client.get("/stars/merge", headers=H1).json()["candidates"]
    assert len(cands) == 1 and {cands[0]["a"]["id"], cands[0]["b"]["id"]} == {a, b} and cands[0]["sun"] == "건강"
    assert client.get("/stars/merge", headers=H2).json()["candidates"] == []
    assert client.post("/stars/merge", headers=H2, json={"from_id": b, "into_id": a}).status_code == 404   # 남의 별
    r = client.post("/stars/merge", headers=H1, json={"from_id": b, "into_id": a})
    assert r.status_code == 200 and r.json()["id"] == a
    u = uni(client)
    assert [x["id"] for x in u["stars"]] == [a] and u["stars"][0]["planet_count"] == 2
    ts = client.get(f"/diary/{ev2[-1][1]['id']}", headers=H1).json()["thoughts"]
    assert {(t["star_id"], t["topic"]) for t in ts} == {(a, "아침 걷기")}
    with env.repo.session(U1) as s:
        assert all(v.get("topic") != "걷기 습관" for v in diary.states(s).values())
    assert [x["data"] for x in lessons(env, target="star")] == [{"from": "걷기 습관", "into": "아침 걷기"}]
    assert client.get("/stars/merge", headers=H1).json()["candidates"] == []
    # 다음 글에서 기록 Agent 가 옛 이름을 다시 내도 합친 별로 간다(새 별을 만들지 않음)
    _, ev3 = write(client, "걷기 나흘째", "걷기를 사흘째 넘어 나흘째 이어 갔다.", "2026-10-04T22:00:00+09:00")
    assert {t["star_id"] for t in ev3[-1][1]["thoughts"]} == {a}
    assert len(uni(client)["stars"]) == 1


def test_merge_decline_not_suggested_again(client, env):  # noqa: F811
    topic_on(env, "사흘째", "걷기 습관")
    _, ev1 = write(client, *DAY1, D1)
    _, ev2 = write(client, *DAY2, D2)
    a, b = ev1[-1][1]["thoughts"][0]["star_id"], ev2[-1][1]["thoughts"][0]["star_id"]
    assert client.post("/stars/merge/decline", headers=H2, json={"from_id": a, "into_id": b}).status_code == 404
    assert client.post("/stars/merge/decline", headers=H1, json={"from_id": a, "into_id": b}).json() == {"ok": True}
    assert client.get("/stars/merge", headers=H1).json()["candidates"] == []
    assert len(uni(client)["stars"]) == 2


def test_merge_fixes_unfinished_entry_steps(client, env):  # noqa: F811
    """멈춘 기록의 단계 저장값이 들고 있던 별 id 도 바꾼다(이어 하기 때 지운 별로 저장하지 않게 — Postgres 에서는 FK 오류)."""
    topic_on(env, "사흘째", "걷기 습관")
    _, ev1 = write(client, *DAY1, D1)
    a = ev1[-1][1]["thoughts"][0]["star_id"]
    env.fake.fail_observe = 2
    _, ev2 = write(client, *DAY2, D2)
    err = ev2[-1][1]
    assert ev2[-1][0] == "error"
    with env.repo.session(U1) as s:
        b = next(x["id"] for x in diary.stars(s) if x["name"] == "걷기 습관")
        assert b in str(diary.entry(s, err["entry_id"])["steps"])
    assert client.post("/stars/merge", headers=H1, json={"from_id": b, "into_id": a}).status_code == 200
    ev3 = events(client.post(f"/diary/{err['entry_id']}/resume/stream", headers=H1).text)
    assert ev3[-1][0] == "result" and {t["star_id"] for t in ev3[-1][1]["thoughts"]} == {a}


##################################################
# 생각 종류 · 가치 고치기
##################################################

def test_fix_thought_kind_value_and_state(client, env):  # noqa: F811
    _, ev = write(client, *DAY1, D1)
    vow = next(t for t in ev[-1][1]["thoughts"] if t["kind"] == "다짐")
    assert vow["state"]["type"] == "다짐"
    assert client.patch(f"/thoughts/{vow['id']}", headers=H2, json={"kind": "소망"}).status_code == 404   # 남의 생각
    assert client.patch(f"/thoughts/{vow['id']}", headers=H1, json={"kind": "다짐함"}).status_code == 422
    assert client.patch(f"/thoughts/{vow['id']}", headers=H1, json={"value": "돈"}).status_code == 422
    r = client.patch(f"/thoughts/{vow['id']}", headers=H1, json={"kind": "소망", "value": "성취"})
    assert r.status_code == 200
    t = r.json()
    assert t["kind"] == "소망" and t["value"] == "성취" and t["state"] is None   # 다짐이 아니면 금빛 고리를 거둠
    assert not next(p for p in uni(client)["planets"] if p["id"] == ev[-1][1]["id"])["ring"]
    les = lessons(env, target="thought")
    assert {x["value"] for x in les} == {"고침"} and all(x["target_id"] == vow["id"] for x in les)
    assert sorted((x["data"]["field"], x["data"]["from"], x["data"]["to"]) for x in les) == \
        [("kind", "다짐", "소망"), ("value", None, "성취")]
    t = client.patch(f"/thoughts/{vow['id']}", headers=H1, json={"kind": "다짐", "value": None}).json()
    assert t["kind"] == "다짐" and t["value"] is None and t["state"] == {"type": "다짐", "status": "열림", "mistake": False}
    feel = next(x for x in ev[-1][1]["thoughts"] if x["kind"] == "감정")
    assert feel["grateful"]
    assert client.patch(f"/thoughts/{feel['id']}", headers=H1, json={"kind": "해석"}).json()["grateful"] is False
    n = len(lessons(env, target="thought"))
    client.patch(f"/thoughts/{feel['id']}", headers=H1, json={"kind": "해석"})   # 같은 값이면 남기지 않음
    assert len(lessons(env, target="thought")) == n


##################################################
# 사람 지우기 + 그 사람이 나온 생각 숨기기
##################################################

def test_delete_person_with_thoughts(client, env):  # noqa: F811
    _, ev1 = write(client, *DAY1, D1)
    _, ev2 = write(client, *DAY2, D2)
    mj = next(p for p in client.get("/people", headers=H1).json()["people"] if p["name"] == "민준")
    client.patch(f"/people/{mj['id']}", headers=H1, json={"relation": "친구"})
    tids = [t["id"] for t in client.get(f"/people/{mj['id']}/thoughts", headers=H1).json()["thoughts"]]
    assert tids and all(t in env.repo.vectors.items for t in tids)
    assert client.delete(f"/people/{mj['id']}/with-thoughts", headers=H2).status_code == 404   # 남의 사람
    r = client.delete(f"/people/{mj['id']}/with-thoughts", headers=H1)
    assert r.status_code == 200 and r.json()["hidden"] == len(tids) and r.json()["replaced"] > 0
    assert not any(t in env.repo.vectors.items for t in tids)                       # 벡터도 지움
    left = [t["id"] for e in (ev1, ev2) for t in client.get(f"/diary/{e[-1][1]['id']}", headers=H1).json()["thoughts"]]
    assert not set(tids) & set(left)
    with env.repo.session(U1) as s:
        assert not [r for r in s.rows("relations") if {r["from_thought"], r["to_thought"]} & set(tids)]
        assert not [k for k in diary.states(s) if any(t in k for t in tids)]
        body = diary.entry(s, ev1[-1][1]["id"])["data"]["text"]
    assert "민준" not in body and "친구" in body                                    # 글 본문은 이름만 관계 말로
    assert all(p["name"] != "민준" for p in client.get("/people", headers=H1).json()["people"])
    assert client.delete(f"/people/{mj['id']}/with-thoughts", headers=H1).status_code == 404
