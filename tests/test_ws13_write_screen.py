"""WS13 쓰기 화면 작은 묶음(API 쪽): 고른 날 · 날짜 고치기 · 말풍선(첫 만남 · 지난 질문 · 다짐 안부 · 날씨 건너뛰기) ·
지우기 뒤 목록 · 우주 · 별지기 이름. 외부 호출은 가짜(메모리 저장소, FakeUpstage)."""
from datetime import date, timedelta

from app.repository import diary
from tests.test_api_flow import H1, H2, client, events, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, DAY2, U1, env  # noqa: F401  (env 픽스처)

YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


def _result(ev):
    kind, res = ev[-1]
    assert kind == "result", ev[-1]
    return res


def test_picked_day_is_yesterday(client):  # noqa: F811
    """쓰기 화면에서 어제를 고르면(day) 기록의 day 가 어제 · 확실, 목록에도 그날."""
    r = client.post("/diary/stream", headers=H1, json={"title": "", "text": DAY1[1], "day": YESTERDAY})
    res = _result(events(r.text))
    assert (res["day"], res["day_basis"], res["day_check"]) == (YESTERDAY, "확실", False)
    assert client.get("/diary", headers=H1).json()["entries"][0]["day"] == YESTERDAY


def test_day_check_then_fix(client):  # noqa: F811
    """제목에 날짜가 둘(3/27~3/29) → 날짜 확인 필요 → PATCH 로 고르면 그날 · 확실 · 확인 필요 거둠."""
    _, ev = write(client, "3/27~3/29 여행", DAY1[1], "2026-10-01T22:00:00+09:00")
    res = _result(ev)
    assert res["day_check"] and res["day_basis"] == "추정"
    r = client.patch(f"/diary/{res['id']}/day", headers=H1, json={"day": "2026-03-28"})
    assert r.status_code == 200
    fixed = r.json()
    assert (fixed["day"], fixed["day_basis"], fixed["day_check"]) == ("2026-03-28", "확실", False)
    assert fixed["thoughts"] == res["thoughts"] and fixed["info"]["summary"] == res["info"]["summary"]   # 정리 결과 · 글은 그대로
    assert client.get(f"/diary/{res['id']}", headers=H1).json()["day"] == "2026-03-28"
    assert client.patch(f"/diary/{res['id']}/day", headers=H2, json={"day": "2026-03-28"}).status_code == 404   # 남의 기록
    assert client.patch(f"/diary/{res['id']}/day", headers=H1, json={"day": "3월"}).status_code == 422
    assert client.patch("/diary/e_none/day", headers=H1, json={"day": "2026-03-28"}).status_code == 404


def test_day_fix_waits_for_running(client, env):  # noqa: F811
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    eid = _result(ev)["id"]
    with env.repo.session(U1) as s:
        diary.lock(s, eid)
    r = client.patch(f"/diary/{eid}/day", headers=H1, json={"day": "2026-09-30"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_running"


def test_prompt_first_meeting(client):  # noqa: F811
    """기록이 없으면 정해 둔 첫 만남 질문(즉석에서 지어내지 않음, PRD §6.2). /diary/{eid} 에 걸리지 않는다."""
    r = client.get("/diary/prompt", headers=H1)
    assert r.status_code == 200
    assert r.json() == {"kind": "first", "text": "오늘 하루를 한 단어로 하면요?", "vow": None}
    assert client.get("/diary/prompt").status_code == 401


def test_prompt_carries_last_question_and_vow(client):  # noqa: F811
    """지난 글의 '다음에 써 볼 질문'을 말풍선에, 지난 글에서 나온 열린 다짐은 안부로(누르면 닫혀 다시 안 물음)."""
    res = _result(write(client, *DAY1, "2026-10-01T22:00:00+09:00")[1])
    p = client.get("/diary/prompt", headers=H1).json()
    assert p["text"] == res["next_question"]["text"] and p["kind"] == res["next_question"]["kind"]
    vow = next(t for t in res["thoughts"] if t["kind"] == "다짐")
    assert p["vow"] == {"thought_id": vow["id"], "text": vow["text"], "overdue": False}
    client.post("/feedback", headers=H1, json={"target": "vow", "target_id": vow["id"], "value": "지켰어요"})
    assert client.get("/diary/prompt", headers=H1).json()["vow"] is None


def test_prompt_weather_skip(client):  # noqa: F811
    """첫 글 뒤 날씨 질문 → 말풍선에 날씨 질문 → 건너뛰면 말풍선 · 다음 글 모두 날씨 질문 없음."""
    res = _result(write(client, "", "오늘은 그냥 그랬다.", "2026-10-01T22:00:00+09:00")[1])
    assert res["next_question"]["kind"] == "weather"
    assert client.get("/diary/prompt", headers=H1).json()["kind"] == "weather"
    assert client.post("/feedback", headers=H1, json={"target": "weather", "value": "날씨 건너뜀"}).json()["ok"]
    assert client.get("/diary/prompt", headers=H1).json()["kind"] == "none"
    res2 = _result(write(client, "", "오늘도 별일 없었다.", "2026-10-02T22:00:00+09:00")[1])
    assert res2["next_question"]["kind"] != "weather"


def test_prompt_no_vow_on_comfort_day(client):  # noqa: F811
    """무거운 날(위로 모드) 뒤에는 다짐 안부를 묻지 않는다."""
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    res = _result(write(client, "", "할머니가 돌아가셨다. 너무 슬프다. 내일은 장례식장에 가겠다.", "2026-10-02T22:00:00+09:00")[1])
    assert res["message"]["mode"] == "comfort"
    assert client.get("/diary/prompt", headers=H1).json()["vow"] is None


def test_delete_removes_from_list_and_universe(client):  # noqa: F811
    a = _result(write(client, *DAY1, "2026-10-01T22:00:00+09:00")[1])
    b = _result(write(client, *DAY2, "2026-10-03T22:00:00+09:00")[1])
    assert {p["id"] for p in client.get("/universe", headers=H1).json()["planets"]} == {a["id"], b["id"]}
    assert client.delete(f"/diary/{b['id']}", headers=H1).status_code == 204
    assert [e["id"] for e in client.get("/diary", headers=H1).json()["entries"]] == [a["id"]]
    u = client.get("/universe", headers=H1).json()
    assert [p["id"] for p in u["planets"]] == [a["id"]] and all(b["id"] not in (x["from_planet"], x["to_planet"]) for x in u["links"])


def test_keeper_name(client):  # noqa: F811
    assert client.get("/me", headers=H1).json()["settings"]["keeper_name"] == "별지기"
    assert client.patch("/settings", headers=H1, json={"keeper_name": " 달지기 "}).json()["keeper_name"] == "달지기"
    assert client.get("/me", headers=H1).json()["settings"]["keeper_name"] == "달지기"
    assert client.get("/me", headers=H2).json()["settings"]["keeper_name"] == "별지기"
    assert client.patch("/settings", headers=H1, json={"keeper_name": "  "}).status_code == 422
    assert client.patch("/settings", headers=H1, json={"keeper_name": "가" * 13}).status_code == 422
