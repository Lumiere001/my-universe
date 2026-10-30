"""Studio 요청 한도 초과(2026-10-30): Studio 는 실패 상태 + error.code 'rate_limit_exceeded' 로 알려 준다 → 쉬었다가 세 번까지 다시."""

from app.agents import studio
from app.core import config, llm

def _run(monkeypatch, errors):
    calls, waits = [], []

    def once(agent_id, config_id, html, timeout):
        calls.append(1)
        if errors:
            raise errors.pop(0)
        return {"ok": True}, 1
    monkeypatch.setattr(studio, "_once", once)
    monkeypatch.setattr(studio.time, "sleep", waits.append)
    with llm.guard([]):
        try:
            return studio.run("record", "<p>가상 글</p>"), calls, waits
        except studio.StudioError as e:
            return e.code, calls, waits

def test_rate_limited_waits_and_tries_three_times(monkeypatch):
    lim = lambda: studio.StudioError("studio_rate_limited")   # noqa: E731
    got, calls, waits = _run(monkeypatch, [lim(), lim()])
    assert got == {"ok": True} and len(calls) == 3 and waits == [config.STUDIO_RETRY_WAIT_S * 4, config.STUDIO_RETRY_WAIT_S * 8]
    got, calls, waits = _run(monkeypatch, [lim(), lim(), lim()])
    assert got == "studio_rate_limited" and len(calls) == 3

def test_other_failures_still_try_twice_without_waiting(monkeypatch):
    got, calls, waits = _run(monkeypatch, [studio.StudioError("studio_failed"), studio.StudioError("studio_failed")])
    assert got == "studio_failed" and len(calls) == 2 and waits == []
