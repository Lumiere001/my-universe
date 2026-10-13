"""WS20 요약 확인: 대화 초안은 save 앞에서 멈추고(목록 · 우주에 안 보임) → 확인 화면에서 고친 값이 저장되고 오답 재료로 남음 →
대화 턴은 지움. 확인 없이 둔 초안은 다음 요청 때 지움. 텍스트 길은 이전과 같음(회귀). 외부 호출은 가짜, 가상 인물 글만."""
from datetime import timedelta

from app.core import config
from app.repository import conversations, diary
from tests.test_api_flow import H1, H2, client, events, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, U1, env  # noqa: F401  (env 픽스처)
from tests.test_ws19_talk import say, start, talk  # noqa: F401  (talk 픽스처)


def finish(client, cid, h=H1):  # noqa: F811
    r = client.post(f"/talk/{cid}/finish/stream", headers=h)
    assert r.status_code == 200, r.text
    return events(r.text)


def talked(client, *said):  # noqa: F811
    c = start(client)
    for t in said:
        say(client, c["id"], t)
    return c["id"]


def test_finish_pauses_before_save_and_hides_draft(client, env, talk):  # noqa: F811
    cid = talked(client, "오늘부터 매일 아침 30분 걷기를 하겠다.", "민준이가 같이 걷자고 해서 고마웠다.")
    ev = finish(client, cid)
    steps = [d["step"] for k, d in ev if k == "progress"]
    assert steps == ["draft", "safety", "names", "record", "past", "observe", "voice"]   # save 앞에서 멈춤
    kind, r = ev[-1]
    assert kind == "result" and r["status"] == "confirm" and r["confirmed"] == "확인 전" and r["source"] == "대화"
    assert r["thoughts"] and r["info"]["summary"] and r["message"] is None             # 한마디는 저장한 뒤에
    assert all(t["quote"] for t in r["thoughts"])                                       # 원문 근거
    assert client.get("/diary", headers=H1).json()["entries"] == []                     # 목록 · 우주에 안 보임
    assert client.get("/universe", headers=H1).json()["planets"] == []
    assert client.get(f"/diary/{r['id']}", headers=H1).json()["status"] == "confirm"
    assert client.get(f"/talk/{cid}", headers=H1).json()["entry_id"] == r["id"]
    ev2 = finish(client, cid)                                                           # 말이 그대로면 같은 초안
    assert [k for k, _ in ev2] == ["result"] and ev2[-1][1]["id"] == r["id"]
    assert env.fake.calls["record"] == 1
    sent = "\n".join(env.fake.sent)
    assert "민준" not in sent                                                            # 초안 · 정리 요청에도 실명 0건


def test_confirm_saves_fixes_and_clears_turns(client, env, talk):  # noqa: F811
    cid = talked(client, "오늘부터 매일 아침 30분 걷기를 하겠다.", "민준이가 같이 걷자고 해서 고마웠다.")
    r = finish(client, cid)[-1][1]
    t0, t1 = r["thoughts"][0], r["thoughts"][1]
    body = {"summary": "아침 걷기를 시작했다.", "fixes": [{"id": t0["id"], "kind": "소망"}, {"id": t1["id"], "remove": True}],
            "agreed": []}
    done = client.post(f"/diary/{r['id']}/confirm", headers=H1, json=body).json()
    assert done["status"] == "done" and done["confirmed"] == "확인됨"
    assert done["info"]["summary"] == "아침 걷기를 시작했다."                               # 고친 값이 저장됨
    assert [(t["id"], t["kind"]) for t in done["thoughts"]] == [(t0["id"], "소망")]          # 종류 고침 · 생각 빼기
    assert done["message"]["text"]                                                     # 저장 뒤 한마디(대화 안 말풍선)
    with env.repo.session(U1) as s:
        notes = [(f["value"], diary.unseal(s, "feedback", f["id"], f["enc"])) for f in s.rows("feedback", target="confirm")]
        assert conversations.get(s, cid) is None                                       # 확인하면 턴은 지움
    assert sorted(v for v, _ in notes) == ["확인 고침"] * 3                                  # 오답 재료(암호문)
    assert {"item": t0["id"], "field": "kind", "before": t0["kind"], "after": "소망", "thought": t0["text"]} in [d for _, d in notes]
    assert t1["id"] not in env.repo.vectors.get(U1)                                     # 뺀 생각의 벡터도 지움
    assert [e["id"] for e in client.get("/diary", headers=H1).json()["entries"]] == [r["id"]]
    assert [p["id"] for p in client.get("/universe", headers=H1).json()["planets"]] == [r["id"]]
    again = client.post(f"/diary/{r['id']}/confirm", headers=H1, json={})
    assert again.status_code == 409 and again.json()["error"]["code"] == "not_waiting"


def test_confirm_agree_only_and_bad_input(client, env, talk):  # noqa: F811
    cid = talked(client, "아침에 30분 걸었다.")
    r = finish(client, cid)[-1][1]
    bad = client.post(f"/diary/{r['id']}/confirm", headers=H1, json={"fixes": [{"id": "e_x-t09", "remove": True}]})
    assert bad.status_code == 422 and client.get(f"/diary/{r['id']}", headers=H1).json()["status"] == "confirm"
    assert client.post(f"/diary/{r['id']}/confirm", headers=H1, json={"fixes": [{"id": r["thoughts"][0]["id"], "kind": "없는 종류"}]}
                       ).status_code == 422
    assert client.post(f"/diary/{r['id']}/confirm", headers=H2, json={}).status_code == 404   # 남의 초안
    ok = client.post(f"/diary/{r['id']}/confirm", headers=H1, json={"agreed": ["summary", r["thoughts"][0]["id"]]}).json()
    assert ok["status"] == "done" and ok["thoughts"][0]["kind"] == r["thoughts"][0]["kind"]
    with env.repo.session(U1) as s:
        assert sorted(f["value"] for f in s.rows("feedback", target="confirm")) == ["확인 맞아요"] * 2


def test_text_path_unchanged_and_confirm_flag(client, env):  # noqa: F811
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")                          # 회귀: 확인 없이 바로 저장
    assert [d["step"] for k, d in ev if k == "progress"][-1] == "save"
    r = ev[-1][1]
    assert r["status"] == "done" and r["confirmed"] is None
    nope = client.post(f"/diary/{r['id']}/confirm", headers=H1, json={})
    assert nope.status_code == 409
    x = client.post("/diary/stream", headers=H1, json={"title": "", "text": "오늘은 도서관에서 공부했다.", "confirm": True})
    res = events(x.text)[-1][1]
    assert res["status"] == "confirm" and res["source"] == "텍스트"                          # confirm 칸이면 텍스트도 멈춤
    assert client.post(f"/diary/{res['id']}/confirm", headers=H1, json={}).json()["status"] == "done"


def test_unconfirmed_draft_expires_on_next_request(client, env, talk, monkeypatch):  # noqa: F811
    cid = talked(client, "아침에 30분 걸었다.")
    r = finish(client, cid)[-1][1]
    with env.repo.session(U1) as s:
        s.update("entries", {"updated_at": diary.now() - timedelta(hours=config.DRAFT_KEEP_HOURS + 1)}, id=r["id"])
    keep = config.DRAFT_KEEP_HOURS
    monkeypatch.setattr(config, "DRAFT_KEEP_HOURS", 0)                                   # 0 = 지우지 않음
    start(client)
    assert client.get(f"/diary/{r['id']}", headers=H1).status_code == 200
    monkeypatch.setattr(config, "DRAFT_KEEP_HOURS", keep)
    start(client)                                                                      # 다음 요청 때 오래된 초안부터 지움
    assert client.get(f"/diary/{r['id']}", headers=H1).status_code == 404
    assert not [k for k in env.repo.vectors.get(U1) if k.startswith(r["id"])]
    assert client.get(f"/talk/{cid}", headers=H1).json()["turn_count"] == 1              # 대화는 남음(다시 정리할 수 있음)


def test_new_turns_redraft_and_delete_talk_removes_draft(client, env, talk):  # noqa: F811
    cid = talked(client, "아침에 30분 걸었다.")
    r1 = finish(client, cid)[-1][1]
    say(client, cid, "저녁엔 책을 읽었다.")
    r2 = finish(client, cid)[-1][1]
    assert r2["id"] != r1["id"] and client.get(f"/diary/{r1['id']}", headers=H1).status_code == 404
    assert client.delete(f"/talk/{cid}", headers=H1).status_code == 204
    assert client.get(f"/diary/{r2['id']}", headers=H1).status_code == 404               # 확인 전 초안도 같이
    c = start(client)
    assert client.post(f"/talk/{c['id']}/finish/stream", headers=H1).json()["error"]["code"] == "no_turns"


def test_list_page_stays_full_with_waiting_draft(client, env):  # noqa: F811
    base = diary.parse_dt("2026-10-01T22:00:00+09:00")
    with env.repo.session(U1) as s:
        done = [diary.new_id("e") for _ in range(21)]
        for i, eid in enumerate(done):                                                  # 완료 기록 21편
            diary.create_entry(s, eid, base + timedelta(hours=i), None, f"글 {i}", "오늘은 도서관에서 공부했다.")
        s.update("entries", {"status": "done"})
        draft = diary.new_id("e")                                                       # + 가장 새 대화 초안 1편(확인 전)
        diary.create_entry(s, draft, base + timedelta(days=5), None, "", "아침에 30분 걸었다.", source="대화")
    page = client.get("/diary", headers=H1, params={"limit": 20}).json()["entries"]
    assert len(page) == 20 and draft not in [e["id"] for e in page]                     # 초안을 걸러도 한 쪽이 꽉 참
    rest = client.get("/diary", headers=H1, params={"limit": 20, "before": page[-1]["written_at"]}).json()["entries"]
    assert [e["id"] for e in rest] == [done[0]]                                         # before 로 다음 쪽이 이어짐
