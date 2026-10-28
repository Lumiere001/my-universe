"""추적(app/core/trace.py): 허용 목록 밖 속성 · 이름꼴이 아닌 글(한글 · 빈칸)은 버리고, 일기 한 편 · 대화 한 턴이 기대한 span 나무가 된다(메모리 exporter)."""
import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import trace
from tests.test_api_flow import H1, client, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import DAY1, NAMES, env  # noqa: F401  (env 픽스처)
from tests.test_ws19_talk import say, start, talk  # noqa: F401  (talk 픽스처)

STEPS = ["safety", "names", "record_input", "record_agent", "record_clean", "past", "observe", "rules", "voice", "save"]


@pytest.fixture
def spans(monkeypatch):
    monkeypatch.setattr(trace, "_tracer", None)   # 끝나면 다시 꺼짐
    exp = InMemorySpanExporter()
    trace.setup(exp)
    return exp


def tree(exp):
    got = exp.get_finished_spans()
    kids = {}
    for s in sorted(got, key=lambda s: s.start_time):
        kids.setdefault(s.parent.span_id if s.parent else None, []).append(s)
    return got, kids


def names(kids, s):
    return [c.name for c in kids.get(s.context.span_id, [])]


def assert_metadata_only(got, *words):
    allowed = set(trace.ALLOWED.values())
    for s in got:
        assert set(s.attributes) <= allowed, s.name
        assert not s.events   # 예외 메시지 · 스택(exception 사건)도 없음
        for v in s.attributes.values():
            assert not (isinstance(v, str) and any(w in v for w in words)), (s.name, v)


def test_text_like_attributes_are_dropped(spans):
    diary_text = DAY1[1]
    assert trace.clean({"text": diary_text, "quote": "민준이가", "prompt": "너는 별지기", "user_id": "u1",
                        "model": "solar-pro4", "calls": 2, "error_code": diary_text, "status": "하늘", "agent": "a b",
                        "entry_id": None}) == {"gen_ai.request.model": "solar-pro4", "app.step.calls": 2}   # 허용 이름이어도 글이면 버림
    with pytest.raises(ValueError):
        with trace.span("solar.chat", text=diary_text, model="solar-pro4"):
            trace.set(output=diary_text, tokens_in=10)
            raise ValueError(diary_text)   # 예외 메시지에 원문이 있어도 span 에는 종류만
    (s,) = spans.get_finished_spans()
    assert dict(s.attributes) == {"gen_ai.request.model": "solar-pro4", "gen_ai.usage.input_tokens": 10,
                                  "error.type": "ValueError"}
    assert s.status.status_code.name == "ERROR" and not s.status.description and not s.events


def test_off_without_endpoint(monkeypatch):
    monkeypatch.setattr(trace, "_tracer", None)
    with trace.span("x", model="m"):
        trace.set(calls=1)
    assert trace.start("y") is trace.otel.INVALID_SPAN


def test_diary_stream_span_tree(client, env, spans):  # noqa: F811
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    got, kids = tree(spans)
    (root,) = kids[None]
    assert root.name == "diary.stream" and root.attributes["app.status"] == "done"
    assert names(kids, root) == STEPS   # Trajectory: 그래프 순서 그대로
    step = {c.name: c for c in kids[root.context.span_id]}
    assert names(kids, step["safety"]) == ["solar.chat"]
    assert names(kids, step["record_agent"]) == ["studio.run"] and names(kids, step["record_clean"]) == ["embed"]
    assert "solar.chat" in names(kids, step["voice"])
    studio = kids[step["record_agent"].context.span_id][0].attributes
    assert studio["gen_ai.agent.name"] == "record" and studio["app.studio.attempts"] == 1 and studio["app.pages"] == 1
    assert step["record_agent"].attributes["app.step.calls"] == 1 and step["record_agent"].attributes["app.est_usd"] > 0
    chat = kids[step["safety"].context.span_id][0].attributes
    assert chat["gen_ai.system"] == "upstage" and chat["gen_ai.usage.input_tokens"] == 100
    assert {s.attributes.get("app.entry_id") for s in got} - {None} == {root.attributes["app.entry_id"]}
    assert_metadata_only(got, *NAMES, "걷기", "아침")


def test_resume_marks_skipped_steps(client, env, spans):  # noqa: F811
    env.fake.fail_observe = 2
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    eid = ev[-1][1]["entry_id"]
    got, kids = tree(spans)
    (root,) = kids[None]
    assert root.attributes["app.error_code"] == "studio_failed" and root.status.status_code.name == "ERROR"
    observe = next(s for s in got if s.name == "observe")
    assert observe.attributes["app.error_code"] == "studio_failed"
    spans.clear()
    client.post(f"/diary/{eid}/resume/stream", headers=H1)
    got, kids = tree(spans)
    (root,) = kids[None]
    assert root.name == "diary.resume"
    skipped = [s.name for s in kids[root.context.span_id] if s.attributes.get("app.step.skipped")]
    assert skipped == STEPS[:6] and names(kids, root) == STEPS


def test_talk_turn_span_tree(client, env, talk, spans):  # noqa: F811
    cid = start(client)["id"]
    say(client, cid, "오늘 아침에 민준이랑 걸었어")
    got, kids = tree(spans)
    (root,) = kids[None]
    assert root.name == "talk.turn" and root.attributes["app.turn"] == 1
    assert names(kids, root) == ["safety", "past", "reply", "summary"]
    assert root.attributes["app.step.calls"] >= 2
    assert_metadata_only(got, *NAMES, "아침", "걸었")


def test_talk_finish_nests_diary_run(client, env, talk, spans):  # noqa: F811
    cid = start(client)["id"]
    say(client, cid, "오늘 아침에 민준이랑 걸었어")
    spans.clear()
    client.post(f"/talk/{cid}/finish/stream", headers=H1)
    got, kids = tree(spans)
    (root,) = kids[None]
    assert root.name == "talk.finish" and names(kids, root) == ["draft", "diary.stream"]
    run = kids[root.context.span_id][1]
    assert names(kids, run) == STEPS[:-1]   # 확인 전 초안: save 앞에서 멈춤(WS20)
    assert run.attributes["app.status"] == "confirm"
    assert_metadata_only(got, *NAMES, "아침", "걸었")
