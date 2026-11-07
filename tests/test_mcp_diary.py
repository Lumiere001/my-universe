"""tools/mcp_diary.py(MCP 서버 시험판): 도구가 맞는 요청을 만드는지. httpx 를 가짜로 바꿔 밖으로 나가지 않는다(mcp SDK 없이 돎)."""

import httpx
import pytest

from tools import mcp_diary as m

D = m.Diary


@pytest.fixture
def api(monkeypatch):
    """가짜 서버: 부른 요청을 calls 에 쌓고, answers[(method, path)] 로 답한다."""
    calls, answers = [], {("GET", "/consent"): (200, {"needed": False}), ("POST", "/diary"): (200, {"status": "done"})}

    def fake(method, url, headers=None, timeout=None, json=None, params=None):
        path = url.removeprefix(m.API)
        calls.append({"method": method, "path": path, "auth": headers["Authorization"], "json": json, "params": params})
        code, body = answers[(method, path)]
        return httpx.Response(code, json=body)

    monkeypatch.setenv("MY_UNIVERSE_TOKEN", "tok-test")
    monkeypatch.setattr(m.httpx, "request", fake)
    m._problems.clear()
    yield calls, answers
    m._jobs.join()   # 일꾼이 가짜 서버로 다 보낸 뒤 끝냄


def test_import_sends_oldest_first_as_imported_files(api):
    calls, _ = api
    out = m.import_diaries([D(text="둘째 날", date="2026-10-02"), D(text="날짜 없음"), D(text=" 첫날 ", date="2026-10-01", title="  첫  날 ")])
    m._jobs.join()
    assert out["accepted"] == 3
    assert calls[0]["path"] == "/consent" and calls[0]["auth"] == "Bearer tok-test"
    sent = [c["json"] for c in calls[1:]]
    assert [c["path"] for c in calls[1:]] == ["/diary"] * 3
    assert [b["text"] for b in sent] == ["첫날", "둘째 날", "날짜 없음"]   # 오래된 것부터, 날짜 없는 글은 뒤로
    first = sent[0]
    assert first["title"] == "첫 날" and first["source"] == "지난 글 묶음" and first["day"] == "2026-10-01"
    assert first["written_at"] == "2026-10-01T12:00:00+09:00"
    assert "day" not in sent[2] and "written_at" not in sent[2]
    assert all(b["source_ref"].startswith("mcp:") for b in sent)
    assert m._body(1, D(text="첫날", date="2026-10-01", title="첫 날"), m.IMPORTED)["source_ref"] == first["source_ref"]   # 다시 넣어도 같은 표시


@pytest.mark.parametrize("entries, why", [
    ([D(text="   ")], "비어"),
    ([D(text="글", date="2026/10/01")], "YYYY-MM-DD"),
    ([D(text="글", date="2026-02-30")], "YYYY-MM-DD"),
    ([D(text="글", date="2999-01-01")], "앞으로"),
    ([D(text="가" * (m.MAX_TEXT + 1))], "8,000자"),
    ([D(text="글")] * (m.MAX_BATCH + 1), "50편"),
    ([], "없어요"),
])
def test_import_rejects_bad_input_before_any_call(api, entries, why):
    calls, _ = api
    with pytest.raises(ValueError, match=why):
        m.import_diaries(entries)
    assert calls == []


def test_one_bad_entry_blocks_the_whole_batch(api):
    calls, _ = api
    with pytest.raises(ValueError, match="2번 글"):
        m.import_diaries([D(text="좋은 글"), D(text="")])
    assert calls == []


def test_consent_or_token_problem_stops_before_queueing(api, monkeypatch):
    calls, answers = api
    answers[("GET", "/consent")] = (200, {"needed": True})
    with pytest.raises(RuntimeError, match="동의"):
        m.import_diaries([D(text="글")])
    answers[("GET", "/consent")] = (401, {"error": {"code": "unauthorized", "message": "로그인이 풀렸어요. 다시 로그인해 주세요."}})
    with pytest.raises(RuntimeError, match="로그인이 풀렸어요"):
        m.write_diary("글")
    monkeypatch.delenv("MY_UNIVERSE_TOKEN")
    with pytest.raises(RuntimeError, match="MY_UNIVERSE_TOKEN"):
        m.recent_diaries()
    m._jobs.join()
    assert all(c["path"] == "/consent" for c in calls)   # /diary 는 한 번도 안 감


def test_write_diary_is_plain_text_source_and_failures_show_in_recent(api):
    calls, answers = api
    answers[("POST", "/diary")] = (429, {"error": {"code": "daily_limit", "message": "오늘은 글을 3편까지 정리할 수 있어요."}})
    answers[("GET", "/diary")] = (200, {"entries": [{"id": "e1", "day": "2026-11-07", "title": "", "status": "done", "source": "텍스트",
                                                     "summary": "요약(돌려주면 안 됨)", "written_at": "2026-11-07T09:00:00+09:00"}]})
    m.write_diary("오늘 일기", title="오늘")
    m._jobs.join()
    b = calls[1]["json"]
    assert b == {"text": "오늘 일기", "title": "오늘", "source": "텍스트"}   # 날짜 없으면 서버가 지금으로, 원본 표시 없음
    out = m.recent_diaries(500)
    assert calls[-1]["params"] == {"limit": 100}
    assert out["diaries"] == [{"date": "2026-11-07", "title": "", "status": "done", "source": "텍스트"}]
    assert out["problems"] == ["날짜 없음 오늘: 오늘은 글을 3편까지 정리할 수 있어요."]
