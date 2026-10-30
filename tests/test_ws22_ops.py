"""운영 화면 · 지표 · 피드백 모으기(WS22). 수용 기준: 운영자 아닌 계정은 403, 원문 0건(숫자 · 코드만), 지표 계산 단위 시험,
동의한 사용자 피드백만 가명으로 풀고 볼 때마다 열람 기록, 오답 모으기 스크립트가 가상 계정 데이터로 돈다."""
import json
import types
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import main
from app.api import consent
from app.core import config
from app.deps import get_repo, get_user
from app.exceptions import ApiError
from app.repository import diary, ops
from scripts import collect_feedback
from tests.test_api_flow import H1, H2, TOKENS, U2, write
from tests.test_graph_flow import DAY1, DAY2, NAMES, U1, env  # noqa: F401  (env 픽스처)

ADMIN = "admin@my-universe.test"
U3 = "33333333-3333-3333-3333-333333333333"
HA = {"Authorization": "Bearer toka"}
SECRET = "민준이가 한 말이 서운했다는 건 아니고 그냥 설교 같았어요"   # 불편한 점 한 줄(가상)


@pytest.fixture
def c(env, monkeypatch):  # noqa: F811  U1 · U2 는 일기를 쓰는 가상 사용자, U3 은 운영자
    from fastapi import Header
    tokens = {**TOKENS, "toka": {"id": U3, "email": ADMIN}}

    def user(authorization: str = Header(default="")):
        u = tokens.get(authorization.removeprefix("Bearer "))
        if not u:
            raise ApiError(401, "unauthorized", "로그인이 필요해요.")
        return u
    monkeypatch.setattr(config, "ADMIN_EMAILS", {ADMIN})
    main.app.dependency_overrides[get_user] = user
    main.app.dependency_overrides[get_repo] = lambda: env.repo
    with env.repo.session(U1) as s:
        consent.save(s, operator_read=True)   # U1 은 운영자 열람에 동의
    with env.repo.session(U2) as s:
        consent.save(s)                        # U2 는 동의하지 않음
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def _fill(c):
    """가상 인물 지호(U1) 두 편 + U2 한 편, 그리고 버튼 피드백 · 불편한 점 한 줄."""
    write(c, *DAY1, "2026-10-01T22:00:00+09:00")
    _, ev = write(c, *DAY2, "2026-10-03T22:00:00+09:00")
    res = ev[-1][1]
    rel = res["relations"][0]["id"]
    assert c.post("/feedback", headers=H1, json={"target": "relation", "target_id": rel, "value": "아니에요"}).status_code == 200
    c.post("/feedback", headers=H1, json={"target": "message", "target_id": res["id"], "value": "별로"})
    c.post("/feedback", headers=H1, json={"target": "message", "target_id": res["id"], "value": "불편한 점 한 줄", "text": SECRET})
    c.post("/feedback", headers=H1, json={"target": "message", "target_id": res["id"], "value": "오늘은 위로만"})
    _, ev2 = write(c, *DAY1, "2026-10-02T22:00:00+09:00", h=H2)
    c.post("/feedback", headers=H2, json={"target": "entry", "target_id": ev2[-1][1]["id"], "value": "불편한 점 한 줄",
                                          "text": "서윤이 얘기를 잘못 알아들었어요"})
    return res


def _fragments():
    return [w.strip() for t in DAY1 + DAY2 for w in t.replace(".", "\n").split("\n") if len(w.strip()) >= 6] + list(NAMES) \
        + [SECRET, "잘못 알아들었어요"]


##################################################
# 운영자만 · 원문 0건
##################################################

def test_not_admin_403(c, monkeypatch):
    for h in (H1, H2):
        for method, path in (("get", "/ops/summary"), ("get", "/ops/feedback"), ("post", "/ops/feedback/summarize")):
            r = getattr(c, method)(path, headers=h)
            assert r.status_code == 403 and r.json()["error"]["code"] == "not_admin", path
    assert c.get("/ops/summary").status_code == 401
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())      # 비우면 아무도 못 봄
    assert c.get("/ops/summary", headers=HA).status_code == 403
    monkeypatch.setattr(config, "ADMIN_EMAILS", {ADMIN})
    assert c.get("/ops/summary", headers=HA).status_code == 200


def test_summary_numbers_only(c, env):  # noqa: F811
    _fill(c)
    r = c.get("/ops/summary", headers=HA)
    assert r.status_code == 200
    body = r.json()
    dump = json.dumps(body, ensure_ascii=False)
    assert not [f for f in _fragments() if f in dump]          # 원문 0건(본문 · 이름 · 불편한 점 한 줄)
    assert body["users"]["total"] >= 2 and body["users"]["operator_read"] == 1
    assert body["runs"]["count"] > 0 and {"voice", "save"} <= {x["step"] for x in body["runs"]["by_step"]}
    assert body["runs"]["per_entry"]["entries"] == 3
    assert body["satisfaction"]["no"] == 1 and body["satisfaction"]["yes_ratio"] == 0.0
    assert body["satisfaction"]["reactions"]["별로"] == 1
    assert "오늘은 위로만" not in dump                           # 마음 상태 버튼 값은 평문 칸에 없음
    assert body["voice"]["messages"] == 3 and body["voice"]["suggested_ratio"] is not None   # 새 칸(제안 표시)이 채워짐
    assert body["voice"]["repeat_ratio"] is not None
    assert body["feedback_text"] == {"consented": 1, "not_consented": 1}
    assert body["cost"]["budget_usd"] == 50 and body["cost"]["warn"] is False
    assert body["direction"]["closer_feeling"] is None          # 묻지 않음(2026-10-13)
    assert body["direction"]["multi_sun"]["users"] == 2


def test_reader_never_returns_ciphertext(env):  # noqa: F811
    with env.repo.session(U1) as s:
        diary.create_entry(s, "e1", diary.now(), None, "제목", "본문 글")
    with ops.reader(env.repo) as r:
        rows = r.rows("entries")
    assert rows and all("enc" not in x and "steps_enc" not in x for x in rows)
    assert all("enc" not in cols and "steps_enc" not in cols for cols in ops.COLS.values())


def test_messages_get_flags(c, env):  # noqa: F811
    write(c, *DAY1, "2026-10-01T22:00:00+09:00")
    with env.repo.session(U1) as s:
        m = s.rows("messages")[0]
    assert isinstance(m["suggested"], bool) and isinstance(m["repeated"], bool)


##################################################
# 동의한 사용자 피드백만 · 가명 · 열람 기록
##################################################

def test_feedback_only_consented_masked_and_logged(c, env):  # noqa: F811
    _fill(c)
    body = c.get("/ops/feedback", headers=HA).json()
    assert body["users"] == 1 and {x["user"] for x in body["items"]} == {"사용자 1"}
    dump = json.dumps(body, ensure_ascii=False)
    assert not [n for n in NAMES if n in dump]                  # 다른 사람 이름은 가명
    assert "서운했다는 건 아니고 그냥 설교 같았어요" in dump      # 동의한 U1 의 글은 풀어 보임
    assert "잘못 알아들었어요" not in dump                       # 동의하지 않은 U2 의 글은 안 보임
    assert body["not_consented"] == {"불편한 점 한 줄": 1}       # 숫자로만
    rel = next(x for x in body["items"] if x["target"] == "relation")
    assert rel["value"] == "아니에요" and rel["target_text"].startswith("[이어짐]") and "→" in rel["target_text"]
    mood = next(x for x in body["items"] if x["value"] == diary.MOOD_LABEL)
    assert mood["text"] is None                                 # 마음 상태 버튼은 풀지 않음
    logs = env.repo.store.tables["ops_reads"]
    assert [(x["admin_id"], x["user_id"], x["what"]) for x in logs] == [(U3, U1, "feedback")]
    assert logs[0]["items"] == len(body["items"])
    c.get("/ops/feedback?wrong=true", headers=HA)
    assert [x["what"] for x in env.repo.store.tables["ops_reads"]] == ["feedback", "wrong"]
    # 선택 동의를 거두면 숫자로만
    with env.repo.session(U1) as s:
        consent.save(s, operator_read=False)
    body = c.get("/ops/feedback", headers=HA).json()
    assert body["items"] == [] and body["not_consented"]["불편한 점 한 줄"] == 2
    assert len(env.repo.store.tables["ops_reads"]) == 2


def test_one_line_needs_visible_text_and_lands_in_its_row(c):
    """불편한 점 한 줄: 글이 없거나 안 보이는 글자뿐이면 422(남지 않음), 보낸 글은 운영 화면 그 줄의 '남긴 말'에 그대로.
    (10/15 운영 '남긴 말' 빈 칸 — 서버가 글 없는 한 줄을 받았고, 화면 trim 은 폭 없는 글자 · 채움 문자를 못 걸렀다)"""
    _, ev = write(c, *DAY1, "2026-10-01T22:00:00+09:00")
    one = {"target": "entry", "target_id": ev[-1][1]["id"], "value": "불편한 점 한 줄"}
    for blank in ({}, {"text": ""}, {"text": "  "}, {"text": "\u200b"}, {"text": "\u3164"}, {"text": "\ufffc"}):
        r = c.post("/feedback", headers=H1, json={**one, **blank})
        assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"
    assert c.post("/feedback", headers=H1, json={**one, "text": "생각을 너무 잘게 나눈 것 같아요"}).status_code == 200
    items = c.get("/ops/feedback", headers=HA).json()["items"]
    assert [(x["target"], x["value"], x["text"]) for x in items] == [("entry", "불편한 점 한 줄", "생각을 너무 잘게 나눈 것 같아요")]


def test_other_candidates_from_consented(c, env):  # noqa: F811
    _fill(c)
    with env.repo.session(U1) as s:
        t = s.rows("thoughts")[0]
        enc = diary.unseal(s, "thoughts", t["id"], t["enc"])
        s.update("thoughts", {"enc": diary.seal(s, "thoughts", t["id"], {**enc, "original": {"kind": "민준 회상"}})}, id=t["id"])
    cands = c.get("/ops/feedback", headers=HA).json()["other_candidates"]
    assert cands and cands[0]["field"] == "kind" and "회상" in cands[0]["original"] and "민준" not in cands[0]["original"]


##################################################
# 피드백 정리 Agent(Solar)
##################################################

def test_summarize(c, env, monkeypatch):  # noqa: F811
    _fill(c)
    sent = []

    def create(model, messages, **kw):
        sent.append(messages)
        out = {"groups": [{"reason": "설교 같음", "items": [1, 2, 99], "fix_where": "말 걸기 규칙", "suggestion": "제안을 질문형으로"}]}
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=json.dumps(out, ensure_ascii=False)))],
                                     usage=types.SimpleNamespace(prompt_tokens=1000, completion_tokens=100))
    monkeypatch.setattr(env.fake.chat.completions, "create", create)
    r = c.post("/ops/feedback/summarize", headers=HA)
    assert r.status_code == 200
    body = r.json()
    assert body["groups"][0]["items"] == [1, 2] and body["groups"][0]["count"] == 2
    assert len(body["lines"]) == 3 and body["est_usd"] > 0     # 오답 재료(아니에요 · 별로 · 불편한 점 한 줄)만
    out = json.dumps(sent, ensure_ascii=False)
    assert not [n for n in NAMES if n in out] and "잘못 알아들었어요" not in out   # 실명 0건 · 동의 안 한 글 0건
    with env.repo.session(U3) as s:
        run = s.rows("runs", step="ops_summarize")
    assert len(run) == 1 and run[0]["calls"] == 1 and run[0]["error_code"] is None
    assert [x["what"] for x in env.repo.store.tables["ops_reads"]] == ["summarize"]


def test_summarize_failures(c, env, monkeypatch):  # noqa: F811
    _fill(c)
    bad = types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="모르겠어요"))], usage=None)
    monkeypatch.setattr(env.fake.chat.completions, "create", lambda **kw: bad)
    r = c.post("/ops/feedback/summarize", headers=HA)
    assert r.status_code == 502 and r.json()["error"]["code"] == "summarize_failed"
    # 가명 처리가 고장 나면 실명 관문이 보내기 전에 막는다
    from app.agents import tools
    monkeypatch.setattr(tools, "mask_obj", lambda obj, people: (obj, {}))
    calls = []
    monkeypatch.setattr(env.fake.chat.completions, "create", lambda **kw: calls.append(kw) or bad)
    assert c.post("/ops/feedback/summarize", headers=HA).status_code == 502
    assert calls == []
    with env.repo.session(U3) as s:
        assert [x["error_code"] for x in s.rows("runs", step="ops_summarize")] == ["format", "real_name_leak"]
    assert "ops_reads" not in env.repo.store.tables               # 실패하면 운영자가 본 것이 없음


##################################################
# 오답 모으기 스크립트(가상 계정 데이터)
##################################################

def test_collect_feedback_script(c, env, tmp_path):  # noqa: F811
    _fill(c)
    data = collect_feedback.collect(lambda path: c.get(path, headers=HA), days=7)
    out, n = collect_feedback.write(data, tmp_path)
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert n == len(rows) == 3 and {x["value"] for x in rows} == set(ops.WRONG)
    assert not [w for w in NAMES if w in out.read_text(encoding="utf-8")]
    assert env.repo.store.tables["ops_reads"][-1]["what"] == "wrong"
    with pytest.raises(Exception):   # 운영자가 아니면 받지 못함
        collect_feedback.collect(lambda path: c.get(path, headers=H1), days=7)


##################################################
# 지표 계산(순수 함수)
##################################################

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
TODAY = NOW.astimezone(diary.TZ).date()


def _at(d, h=12):
    return datetime(d.year, d.month, d.day, h, tzinfo=diary.TZ)


def test_next_day():
    d = date(2026, 10, 10)
    days = {"a": {d, d + timedelta(days=1), d + timedelta(days=5)}}
    got = ops.next_day([("a", x) for x in days["a"]], days, d + timedelta(days=8))
    assert got == {"pairs": 3, "returned": 1, "ratio": 0.333}
    # 어제 쓴 날은 오늘이 끝나야 알 수 있어 세지 않는다
    assert ops.next_day([("a", d + timedelta(days=1))], days, d + timedelta(days=2))["pairs"] == 0


def test_cost_warn_and_over():
    runs = [{"est_usd": 30, "step": "record_agent", "created_at": NOW}, {"est_usd": 11, "step": "voice", "created_at": NOW - timedelta(days=40)}]
    c = ops.cost(runs, 50, NOW)
    assert c["total_usd"] == 41 and c["month_usd"] == 30 and c["warn"] and not c["over"] and c["by_step"]["record_agent"] == 30
    assert ops.cost(runs + [{"est_usd": 9, "step": "x", "created_at": NOW}], 50, NOW)["over"]
    assert not ops.cost(runs[:1], 50, NOW)["warn"]


def test_run_stats_gates_failures():
    runs = [{"entry_id": "e1", "step": "record_agent", "ms": 2000, "calls": 1, "est_usd": 0.05, "error_code": None, "meta": {},
             "studio_config": "2/2", "created_at": NOW},
            {"entry_id": "e1", "step": "voice", "ms": 1000, "calls": 2, "est_usd": 0.01, "error_code": None, "meta": {"checks": 1},
             "studio_config": "2/2", "created_at": NOW},
            {"entry_id": "e2", "step": "voice", "ms": 3000, "calls": 1, "est_usd": 0, "error_code": None, "meta": {},
             "studio_config": "2/2", "created_at": NOW},
            {"entry_id": "e3", "step": "record_agent", "ms": 0, "calls": 0, "est_usd": 0, "error_code": "real_name_leak", "meta": {},
             "studio_config": "2/2", "created_at": NOW}]
    s = ops.run_stats(runs)
    assert s["per_entry"] == {"entries": 3, "avg_s": 2.0, "avg_usd": 0.02}
    voice = next(x for x in s["by_step"] if x["step"] == "voice")
    assert voice["count"] == 2 and voice["avg_ms"] == 2000
    g = ops.gates(runs)
    assert g == {"real_name_leak": 1, "voice_runs": 2, "voice_regenerated": 1, "voice_regenerated_ratio": 0.5}
    entries = [{"id": "e3", "status": "failed", "error_code": "real_name_leak", "step": "names", "created_at": NOW},
               {"id": "e1", "status": "done", "error_code": None, "step": "save", "created_at": NOW}]
    f = ops.failures(entries, runs)
    assert f["entries"] == 1 and f["by_code"] == {"real_name_leak": 1} and f["run_errors"][0]["count"] == 1


def test_talk_metrics():
    def turn(conv, n, ago, sug=False):
        return {"user_id": "u", "entry_id": conv, "step": "chat_turn", "meta": {"turn": n, "suggested": sug}, "created_at": NOW - ago}
    h = timedelta(hours=1)
    runs = [turn("A", 1, 50 * h), turn("A", 2, 49 * h), turn("A", 3, 48 * h, sug=True),       # 제안 직후 그만둠(3턴)
            turn("B", 1, 30 * h), turn("B", 2, 29 * h, sug=True),
            {"user_id": "u", "entry_id": "B", "step": "chat_done", "meta": {"turns": 2}, "created_at": NOW - 29 * h},
            turn("C", 1, h),                                                                   # 아직 하는 중
            {"user_id": "u", "entry_id": "e1", "step": "confirm", "meta": {"items": 4, "edited": 1}, "created_at": NOW},
            {"user_id": "u", "entry_id": "e2", "step": "confirm", "meta": {"items": 2, "edited": 0}, "created_at": NOW}]
    t = ops.talk(runs, NOW)
    assert t["conversations"] == 3 and t["finished"] == 1 and t["dropped"] == 1 and t["drop_at"] == {"3": 1}
    assert t["avg_turns"] == 2.0
    assert t["stop_after_suggestion"] == 0.5 and t["stop_without_suggestion"] == 0.0
    assert t["edited_ratio"] == 0.167 and t["confirms_with_edit"] == 0.5
    assert ops.talk([], NOW)["avg_turns"] is None


def test_voice_and_satisfaction_metrics():
    d1, d2, d3 = TODAY - timedelta(days=5), TODAY - timedelta(days=4), TODAY - timedelta(days=3)
    msgs = [{"user_id": "a", "entry_id": "e1", "suggested": True, "repeated": False, "created_at": _at(d1)},
            {"user_id": "a", "entry_id": "e2", "suggested": False, "repeated": True, "created_at": _at(d2)},
            {"user_id": "b", "entry_id": "e3", "suggested": False, "repeated": False, "created_at": _at(d1)},
            {"user_id": "b", "entry_id": "e4", "suggested": None, "repeated": None, "created_at": _at(d3)}]   # 이 칸 전의 행
    days = {"a": {d1, d2}, "b": {d1, d3}}
    fb = [{"user_id": "a", "target": "message", "value": "별로", "studio_config": "2/2"},
          {"user_id": "a", "target": "relation", "value": "맞아요", "studio_config": "2/2"},
          {"user_id": "b", "target": "relation", "value": "맞아요", "studio_config": None},
          {"user_id": "b", "target": "relation", "value": "아니에요", "studio_config": "2/2"}]
    v = ops.voice(msgs, [], fb, days, TODAY)
    assert v["suggested_ratio"] == 0.333 and v["repeat_ratio"] == 0.333 and v["dislike_ratio"] == 0.25
    assert v["next_day_with_suggestion"] == {"pairs": 1, "returned": 1, "ratio": 1.0}         # a: d1(제안) → d2 다시 씀
    assert v["next_day_without_suggestion"] == {"pairs": 2, "returned": 0, "ratio": 0.0}      # a: d2, b: d1
    s = ops.satisfaction(fb, days, TODAY)
    assert s["yes"] == 2 and s["no"] == 1 and s["yes_ratio"] == 0.667
    assert s["by_config"] == {"2/2": {"별로": 1, "맞아요": 1, "아니에요": 1}, "없음": {"맞아요": 1}}
    assert s["next_day"] == {"pairs": 4, "returned": 1, "ratio": 0.25}


def test_multi_sun_and_other_counts():
    recent, old = _at(TODAY - timedelta(days=2)), _at(TODAY - timedelta(days=40))
    entries = [{"user_id": "a", "status": "done", "sun_id": "s1", "created_at": recent},
               {"user_id": "a", "status": "done", "sun_id": "s2", "created_at": recent},
               {"user_id": "b", "status": "done", "sun_id": "s1", "created_at": recent},
               {"user_id": "b", "status": "done", "sun_id": "s3", "created_at": old},
               {"user_id": "b", "status": "failed", "sun_id": None, "created_at": recent}]
    m = ops.multi_sun(entries, TODAY)
    assert m == {"window_days": 14, "users": 2, "avg_suns": 1.5, "share_2plus": 0.5, "avg_suns_all": 2.0}
    o = ops.other_counts([{"kind": "기타", "certainty": "단정", "value": None}, {"kind": "해석", "certainty": "기타", "value": "기타"}])
    assert o == {"thoughts": 2, "kind": 1, "certainty": 1, "value": 1}


def test_consenting():
    t = lambda n: NOW + timedelta(minutes=n)   # noqa: E731
    rows = [{"user_id": "a", "version": "v2", "operator_read": True, "created_at": t(0)},
            {"user_id": "b", "version": "v2", "operator_read": True, "created_at": t(0)},
            {"user_id": "b", "version": "v2", "operator_read": False, "created_at": t(1)},   # 거둠
            {"user_id": "c", "version": "v1", "operator_read": True, "created_at": t(0)},    # 옛 판
            {"user_id": "d", "version": "v2", "operator_read": False, "created_at": t(0)}]
    assert ops.consenting(rows, "v2") == ["a"]


def test_eval_results(tmp_path):
    assert ops.eval_results(tmp_path / "없음") is None
    (tmp_path / "baseline.json").write_text("{}")
    (tmp_path / "2026-10-08-all.json").write_text(json.dumps({"summary": {"categories": {"crisis": {"passed": 3, "total": 4}},
                                                                          "gate_ok": True, "regressions": ["x"], "cost": {"est_usd": 0}}}))
    (tmp_path / "broken.json").write_text("{")
    got = ops.eval_results(tmp_path)
    assert got == [{"file": "2026-10-08-all.json", "gate_ok": True, "regressions": 1, "passed": 3, "total": 4, "est_usd": 0,
                    "categories": {"crisis": {"passed": 3, "total": 4}}}]


##################################################
# 선호 맞추기 제안("이 설정으로 바꿀까요?")
##################################################

def test_pref_suggestions_rules():
    st = {"cross_links": "눌렀을 때", "suggestions": "보통"}
    got = ops.pref_suggestions(st, {"cross_links": (0, 3), "suggestions": (3, 1)})
    assert [(x["setting"], x["to"]) for x in got] == [("cross_links", "숨김"), ("suggestions", "많이")]
    assert ops.pref_suggestions(st, {"cross_links": (2, 2), "suggestions": (2, 0)}) == []        # 적거나 섞여 있으면 안 물음
    assert ops.pref_suggestions({"cross_links": "숨김", "suggestions": "적게"},
                                {"cross_links": (0, 5), "suggestions": (0, 5)}) == []            # 더 내려갈 곳 없음


def test_pref_suggestions_api(c, env):  # noqa: F811
    """개인 고리(2026-10-30): 반응이 한쪽으로 3번 이상 쌓이면 묻지 않고 그 사람 설정을 한 칸 옮기고 알린다. 되돌리기 · 본 것으로 하기."""
    res = _fill(c)
    assert c.get("/settings/suggestions", headers=H1).json() == {"suggestions": [], "applied": []}
    with env.repo.session(U1) as s:
        s.update("messages", {"suggested": True})
        ts = s.rows("thoughts")
        s.update("thoughts", {"sun_id": "d_other"}, id=ts[0]["id"])   # 두 생각이 다른 해 → 영역을 넘는 관계
        for _ in range(3):
            diary.add_feedback(s, "relation", f"{ts[0]['id']}>{ts[-1]['id']}", "아니에요")
    first = c.post("/feedback", headers=H1, json={"target": "message", "target_id": res["id"], "value": "별로"}).json()
    assert [(x["setting"], x["to"]) for x in first["tuned"]] == [("cross_links", "숨김")]   # 누르는 순간 그 사람 것만 한 칸
    for _ in range(2):
        c.post("/feedback", headers=H1, json={"target": "message", "target_id": res["id"], "value": "별로"})
    got = c.get("/settings/suggestions", headers=H1).json()["applied"]
    assert [(x["setting"], x["from"], x["to"]) for x in got] == [("cross_links", "눌렀을 때", "숨김"), ("suggestions", "보통", "적게")]
    assert got[0]["reason"].endswith("자주 눌렀어요.")   # 한 다이얼을 옮겨도 다른 다이얼에 쌓인 반응은 그대로
    with env.repo.session(U1) as s:
        assert diary.profile(s)[0]["cross_links"] == "숨김"
    undo = c.post(f"/settings/suggestions/{got[0]['id']}/undo", headers=H1).json()
    assert undo["settings"]["cross_links"] == "눌렀을 때" and undo["settings"]["suggestions"] == "적게"
    assert [x["setting"] for x in c.get("/settings/suggestions", headers=H1).json()["applied"]] == ["suggestions"]
    assert c.post("/settings/suggestions/seen", headers=H1).json() == {"ok": True}
    assert c.get("/settings/suggestions", headers=H1).json()["applied"] == []
    assert c.post("/feedback", headers=H1, json={"target": "message", "target_id": res["id"], "value": "별로"}).json()["tuned"] == []
    assert c.get("/settings/suggestions", headers=H2).json()["applied"] == []   # 남의 피드백과 상관없음
    assert c.post("/settings/suggestions/nope/undo", headers=H1).status_code == 404


def test_personal_loop_two_users_move_apart(c, env):  # noqa: F811
    """개인 맞춤 Ops: 같은 공통 틀에서 취향이 반대인 두 사람 — 각자 누른 반응대로 각자 설정만 반대쪽으로 한 칸씩 옮겨지고(알림도 각자),
    운영 화면에는 사람 id 없이 분포만 나온다."""
    res1 = _fill(c)                                                   # U1: 아니에요 1 · 별로 1 이미 있음
    _, ev = write(c, *DAY2, "2026-10-04T22:00:00+09:00", h=H2)
    res2 = ev[-1][1]
    for uid, value, n in ((U1, "아니에요", 4), (U2, "맞아요", 5)):     # 영역을 넘는 선에 U1 은 '아니에요', U2 는 '맞아요'
        with env.repo.session(uid) as s:
            s.update("messages", {"suggested": True})
            ts = s.rows("thoughts")
            s.update("thoughts", {"sun_id": "d_other"}, id=ts[0]["id"])
            for _ in range(n):
                diary.add_feedback(s, "relation", f"{ts[0]['id']}>{ts[-1]['id']}", value)
    for h, res, value in ((H1, res1, "별로"), (H2, res2, "좋아요")):   # 제안 든 한마디에 U1 은 '별로', U2 는 '좋아요'
        for _ in range(3):
            c.post("/feedback", headers=h, json={"target": "message", "target_id": res["id"], "value": value})
    want = {U1: {"cross_links": "숨김", "suggestions": "적게"}, U2: {"cross_links": "항상", "suggestions": "많이"}}
    for uid, h in ((U1, H1), (U2, H2)):
        with env.repo.session(uid) as s:
            st = diary.profile(s)[0]
        assert {k: st[k] for k in want[uid]} == want[uid]              # 같은 틀, 반대 방향 — 사람마다 따로
        assert {x["setting"] for x in c.get("/settings/suggestions", headers=h).json()["applied"]} == {"cross_links", "suggestions"}
    personal = c.get("/ops/summary", headers=HA).json()["personal"]
    assert personal["links_yes"] == {"users": 2, "median": 0.5, "worse": 0} and personal["dislike"]["users"] == 0
    assert U1 not in json.dumps(personal) and U2 not in json.dumps(personal)
    note = next(x for x in c.get("/settings/suggestions", headers=H1).json()["applied"] if x["setting"] == "cross_links")
    c.post(f"/settings/suggestions/{note['id']}/undo", headers=H1)   # U1 이 하나를 되돌림
    c.post(f"/settings/suggestions/{note['id']}/undo", headers=H1)   # 두 번 눌러도 한 번
    loop = c.get("/ops/summary", headers=HA).json()["personal_loop"]   # 운영: 개인 고리가 도는 모습(사람 id 없이)
    dials = {d["setting"]: d for d in loop["dials"]}
    assert dials["cross_links"] == {"setting": "cross_links", "moved": 2, "users": 2, "undone": 1, "to": {"숨김": 1, "항상": 1}}
    assert dials["suggestions"]["to"] == {"적게": 1, "많이": 1} and loop["on"]["auto"] == 2 and loop["min"] == 3
    assert U1 not in json.dumps(loop) and U2 not in json.dumps(loop)


##################################################
# 로컬 Supabase: app_ops 역할은 암호문 칸을 못 읽는다(원문 0건을 DB 권한으로)
##################################################

def _local_pg():
    if not config.DATABASE_URL.startswith("postgresql://postgres:postgres@127.0.0.1"):
        return False
    import psycopg
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=2) as conn:
            return bool(conn.execute("select 1 from pg_roles where rolname = 'app_ops'").fetchone())
    except Exception:
        return False


@pytest.mark.skipif(not _local_pg(), reason="로컬 Supabase 에 WS22 마이그레이션(app_ops)이 없음")
def test_pg_app_ops_reads_plain_columns_only():
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        uid = (conn.execute("select id from auth.users limit 1").fetchone() or {}).get("id")
        conn.commit()
        for table, col in (("entries", "enc"), ("entries", "steps_enc"), ("thoughts", "enc"), ("messages", "enc"),
                           ("feedback", "enc"), ("profiles", "enc"), ("people", "id"), ("stars", "id"), ("suns", "name")):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction(force_rollback=True):
                    conn.execute("set local role app_ops")
                    conn.execute(f"select {col} from {table} limit 1")
        with conn.transaction(force_rollback=True):
            conn.execute("set local role app_ops")
            got = ops.summary(ops.PgReader(conn), consent.VERSION, 50)   # 칸 목록(COLS)이 모두 권한 안에 있음
            assert set(got) >= {"cost", "runs", "talk", "voice"}
            if uid:
                ops.PgReader(conn).log_read(uid, uid, "feedback", 0)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction(force_rollback=True):
                conn.execute("set local role app_ops")
                conn.execute("update ops_reads set items = 1")      # 열람 기록은 고치지 않음
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction(force_rollback=True):
                conn.execute("set local role app_user")             # 사용자 역할은 열람 기록을 못 봄
                conn.execute("select * from ops_reads")
