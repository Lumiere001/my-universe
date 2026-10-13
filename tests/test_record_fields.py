"""WS11 기록 칸: 출처 · 글이 다루는 날(G2) · 확인 상태 · 글 유형 · 목록 밖 원래 말 · 설정 번호 · 지운 관계 보존 · 같은 글 다시 보내지 않기.
외부 호출은 가짜(FakeUpstage), 저장소는 메모리. 가상 인물 글만."""
import re
from datetime import date
from pathlib import Path

import pytest

from app.core import config
from app.repository import diary
from app.service.rules.dates import read_day
from tests.test_api_flow import H1, client, events, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, DAY2, U1, env  # noqa: F401  (env 픽스처)

W = date(2026, 4, 1)


@pytest.mark.parametrize("title,text,written,picked,want", [
    ("3/27 비 오는 날", "", W, None, (date(2026, 3, 27), "확실", False)),          # 있음
    ("3월 27일", "", W, None, (date(2026, 3, 27), "확실", False)),
    ("2026.3.27 일기", "", W, None, (date(2026, 3, 27), "확실", False)),           # 3.27 을 따로 다시 읽지 않음
    ("260327 일기", "", W, None, (date(2026, 3, 27), "확실", False)),
    ("12/31", "", date(2026, 1, 2), None, (date(2025, 12, 31), "확실", False)),   # 1월에 쓴 12월 일기
    ("3월 27일", "", date(2026, 10, 13), None, (date(2026, 3, 27), "확실", False)),   # 10월에 올린 3월 일기 → 내년 아님
    ("1/3 정도 읽음", "", date(2026, 10, 13), None, (date(2026, 1, 3), "확실", False)),
    ("10/13", "", date(2026, 10, 13), None, (date(2026, 10, 13), "확실", False)),     # 쓴 날 그날
    ("10/14", "", date(2026, 10, 13), None, (date(2025, 10, 14), "확실", False)),     # 다음 날은 지난해로
    ("2/29", "", date(2026, 10, 13), None, (date(2026, 10, 13), "추정", True)),       # 그해에 없는 날
    ("", "2026년 3월 27일 금요일\n오늘은 걸었다.", W, None, (date(2026, 3, 27), "확실", False)),   # 본문 첫 줄
    ("걷기", "", W, None, (W, "추정", False)),                                      # 없음
    ("3.5km 달리기", "", W, None, (W, "추정", False)),                              # 날짜 아님
    ("", "어제 민준이가 3월 27일에 시험이 있다고 해서 같이 공부하기로 했다.", W, None, (W, "추정", False)),   # 긴 첫 문장은 안 봄
    ("13/45 이상한 날", "", W, None, (W, "추정", True)),                            # 애매: 못 읽음
    ("2/30", "", W, None, (W, "추정", True)),
    ("3/27~3/29 여행", "", W, None, (W, "추정", True)),                             # 애매: 둘 이상
    ("3/27", "", W, date(2026, 3, 1), (date(2026, 3, 1), "확실", False)),          # 사용자가 고른 날이 먼저
])
def test_g2_read_day(title, text, written, picked, want):
    assert read_day(title, text, written, picked) == want


def _write(env, title, text, when="2026-10-01T22:00:00+09:00", **kw):  # noqa: F811
    from app.agents import graph
    from app.repository import views
    eid = diary.new_id("e")
    with env.repo.session(U1) as s:
        diary.create_entry(s, eid, diary.parse_dt(when), None, title, text, **kw)
    graph.run(env.repo, U1, eid)
    with env.repo.session(U1) as s:
        return views.entry_result(s, eid)


def test_new_fields_saved_and_read(env):  # noqa: F811
    r = _write(env, *DAY1)
    assert {k: r[k] for k in ("source", "day", "day_basis", "day_check", "confirmed", "record_type")} == {
        "source": "텍스트", "day": "2026-10-01", "day_basis": "추정", "day_check": False, "confirmed": None,
        "record_type": "생각·성찰"}                               # Classify 단계 결과를 읽음(전에는 버림)
    r = _write(env, "9/30 걷기", DAY2[1], source="사진")
    assert (r["source"], r["day"], r["day_basis"]) == ("사진", "2026-09-30", "확실")
    r = _write(env, "13/45 걷기", "오늘은 쉬었다.")
    assert (r["day"], r["day_basis"], r["day_check"]) == ("2026-10-01", "추정", True)   # 보고서의 '날짜 확인 필요'
    r = _write(env, "", "대화 정리: 오늘 걷기를 했다.", source="대화")
    assert (r["confirmed"], r["day_basis"]) == ("확인 전", "확실")
    with env.repo.session(U1) as s:
        lst = {e["id"]: e for e in diary.entries(s)}
        assert all(row["studio_config"] == "2/2" for row in s.rows("runs"))          # 실행 기록의 설정 번호
    assert lst[r["id"]]["source"] == "대화"


def test_other_original_round_trip(env, monkeypatch):  # noqa: F811
    """목록 밖 값: 종류뿐 아니라 확신 · 가치 · 말 거는 대상 · 글 유형의 원래 말도 저장하고 다시 읽는다."""
    def record(html):
        s = "오늘 걷기로 조금 자란 것 같다."
        return {"summary": ["걷기"], "addressee": ["기타(친구들)"], "events": [],
                "thoughts": [{"thought": [s], "kind": ["기타(성장)"], "certainty": ["기타(반반)"], "value": ["기타(성장)"],
                              "quote": [s], "self_change": [""], "topic": ["아침 걷기"], "people": [""]}]}
    monkeypatch.setattr(env.fake, "_record", record)
    run = env.fake.responses.create

    def create(**kw):
        r = run(**kw)
        if kw["model"] == "rec-agent":
            r.output[1].content[0].text = "일기장"   # Classify 가 목록 밖 갈래를 냄
        return r
    monkeypatch.setattr(env.fake.responses, "create", create)
    r = _write(env, "걷기", "오늘 걷기로 조금 자란 것 같다.")
    t = r["thoughts"][0]
    assert (t["kind"], t["certainty"], t["value"]) == ("기타", "기타", "기타")
    assert t["original"] == {"kind": "성장", "certainty": "반반", "value": "성장"} and t["other"] == "성장"
    assert r["info"]["addressee"] == "기타" and r["info"]["original"] == {"addressee": "친구들", "record_type": "일기장"}
    assert r["record_type"] == "기타"


def test_feedback_config_and_removed_relation_kept(client, env):  # noqa: F811
    _, ev1 = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    _, ev2 = write(client, *DAY2, "2026-10-03T22:00:00+09:00")
    rel = ev2[-1][1]["relations"][0]
    assert client.post("/feedback", headers=H1, json={"target": "relation", "target_id": rel["id"], "value": "아니에요"}).json()["ok"]
    with env.repo.session(U1) as s:
        fb = s.rows("feedback")[0]
        assert fb["studio_config"] == "2/2" and fb["value"] == "아니에요"
        assert diary.unseal(s, "feedback", fb["id"], fb["enc"]) == {"relation": {"type": rel["type"], "from": rel["from"],
                                                                                 "to": rel["to"]}}
        assert not s.rows("relations")
    assert client.delete(f"/diary/{ev2[-1][1]['id']}", headers=H1).status_code == 204
    with env.repo.session(U1) as s:
        assert s.rows("feedback") == []   # 기록을 지우면 지운 관계의 오답 재료도 같이


def test_same_text_not_sent_again(client, env, monkeypatch):  # noqa: F811
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    first = ev[-1][1]
    _, ev = write(client, DAY1[0], "  " + DAY1[1].replace(" ", "  ") + "\n", "2026-10-02T22:00:00+09:00")   # 띄어쓰기만 다름
    assert [e for e, _ in ev] == ["result"] and ev[0][1]["duplicate"] is True and ev[0][1]["id"] == first["id"]
    assert env.fake.calls["record"] == 1 and env.fake.calls["observe"] == 1   # Studio 를 다시 부르지 않음
    r = client.post("/diary", headers=H1, json={"title": DAY1[0], "text": DAY1[1]})
    assert r.json()["duplicate"] is True and r.json()["id"] == first["id"]
    assert len(client.get("/diary", headers=H1).json()["entries"]) == 1
    monkeypatch.setattr(config, "V8_RECORD_CONFIG_ID", "3")   # 설정이 바뀌면 같은 글도 새로 정리
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    assert ev[-1][1]["id"] != first["id"] and "duplicate" not in ev[-1][1] and env.fake.calls["record"] == 2


def test_same_text_unfinished_points_to_resume(client, env):  # noqa: F811
    env.fake.fail_observe = 2
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    eid = ev[-1][1]["entry_id"]
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    assert ev == [("error", {"entry_id": eid, "code": "duplicate", "message": ev[0][1]["message"], "resumable": True})]
    r = client.post("/diary", headers=H1, json={"title": DAY1[0], "text": DAY1[1]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "duplicate"
    assert env.fake.calls["record"] == 1


def test_same_source_ref_not_imported_again(client, env):  # noqa: F811
    body = {"title": "", "text": "인스타 글 하나.", "source": "지난 글 묶음", "source_ref": "ig:1700000000"}
    first = events(client.post("/diary/stream", headers=H1, json=body).text)[-1][1]
    again = events(client.post("/diary/stream", headers=H1, json={**body, "text": "인스타 글 하나(고침)."}).text)
    assert again[-1][1]["duplicate"] is True and again[-1][1]["id"] == first["id"]
    with env.repo.session(U1) as s:
        ref = s.rows("entries")[0]["source_ref"]
    assert re.fullmatch(r"[0-9a-f]{64}", ref)   # 원본 표시는 평문이 아니라 HMAC
    assert client.post("/diary/stream", headers=H1, json={**body, "source": "편지"}).status_code == 422


def test_migrations_after_v8_security_only_add():
    """운영 DB 를 깨지 않게 새 마이그레이션은 덧붙이기만(지우기 · 이름 바꾸기 · 기존 칸 NOT NULL · 형 바꾸기 금지)."""
    bad = re.compile(r"\b(drop|rename|truncate|delete\s+from)\b|set\s+not\s+null|alter\s+column\s+\S+\s+(set\s+data\s+)?type",
                     re.I)
    files = sorted(Path("supabase/migrations").glob("*.sql"))
    new = [f for f in files if f.name >= "20261013"]
    assert new
    for f in new:
        sql = re.sub(r"--[^\n]*", "", f.read_text(encoding="utf-8"))
        assert not bad.search(sql), f.name
