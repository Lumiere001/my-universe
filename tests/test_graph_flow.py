"""그래프 순서 · 위기 글(평소 흐름 + 안부 한 줄) · 이어 하기 · 외부 요청 실명 0건 · 원문 없는 로그 (외부 클라이언트는 가짜, 저장소는 메모리)."""
import hashlib
import json
import re
import types

import pytest

from app.agents import graph, studio
from app.core import config, llm, security
from app.repository import MemRepo, diary, views
from app.service import voice
from app.service.safety.crisis import LLM_PROMPT

U1 = "11111111-1111-1111-1111-111111111111"
NAMES = ("민준", "서윤")                      # 가상 인물 지호의 친구들(실명 역할)
DAY1 = ("아침 걷기 시작", "오늘부터 매일 아침 30분 걷기를 하겠다. 민준이가 같이 걷자고 해서 고맙다.")
DAY2 = ("걷기 사흘째", "아침 걷기를 사흘째 이어 가고 있다. 민준이랑 걸으니 덜 힘들다. 서윤이도 다음 주에 같이 걷기로 했다.")
CRISIS = ("", "요즘 너무 지쳐서 죽고 싶다는 생각이 든다.")


def _o(**kw):
    return types.SimpleNamespace(**kw)


class FakeUpstage:
    """Studio(files · responses) + Solar(chat · embeddings)를 흉내 낸다. 보낸 글을 모두 sent 에 남긴다."""

    def __init__(self):
        self.sent, self.store, self.calls = [], {}, {"record": 0, "observe": 0, "chat": 0, "embed": 0}
        self.fail_observe = 0
        self.classify = "생각·성찰"   # 기록 Agent Classify 갈래(글 유형)
        self.crisis_llm = '{"crisis": false, "reason": "평범한 하루"}'   # 위기 2차 판정 답(예외면 실패)
        self.deleted = []
        self.files = _o(create=self._file, delete=self.deleted.append)
        self.responses = _o(create=self._run, retrieve=None)
        self.chat = _o(completions=_o(create=self._chat))
        self.embeddings = _o(create=self._embed)

    # Studio
    def _file(self, file, purpose):
        html = file[1].decode()
        self.sent.append(html)
        fid = f"f{len(self.store)}"
        self.store[fid] = html
        return _o(id=fid)

    def _run(self, model, include, input, extra_body):
        html = self.store[input[0]["content"][0]["file_id"]]
        kind = "record" if model == "rec-agent" else "observe"
        self.calls[kind] += 1
        if kind == "observe" and self.fail_observe:
            self.fail_observe -= 1
            return _o(status="failed", output=[], id="j")
        data = self._record(html) if kind == "record" else self._observe(html)
        out = [_o(content=[_o(text=json.dumps({"elements": [{"page": 1}]}))]), _o(content=[_o(text=self.classify)]),
               _o(content=[_o(text=json.dumps(data, ensure_ascii=False))])]
        return _o(status="completed", output=out, id="j")

    def _record(self, html):
        body = " ".join(re.findall(r"<p>(.*?)</p>", html))
        thoughts = []
        for s in re.findall(r"[^.]+\.", body):
            s = s.strip()
            kind = "다짐" if "겠다" in s or "기로 했다" in s else "감정(감사)" if "고맙" in s else "해석"
            thoughts.append({"thought": [s], "kind": [kind], "certainty": ["단정"], "value": [""], "quote": [s],
                             "self_change": [""], "topic": ["아침 걷기"], "people": [""]})
        return {"summary": ["걷기에 대한 글"], "addressee": ["나"], "events": ["걷기"], "thoughts": thoughts}

    def _observe(self, html):
        ids = re.findall(r"<li>([TP]\d+) · ", html)
        today = [i for i in ids if i.startswith("T")]
        past = [i for i in ids if i.startswith("P")]
        rels = []
        if past and today:
            q = re.search(r"T1 · [^<]*?원문: &quot;(.*?)&quot;", html)
            rels.append({"type": ["이어짐"], "past_id": [past[0]], "today_id": [today[0]], "same_target": ["걷기"],
                         "topic": ["아침 걷기"], "evidence": [q.group(1) if q else ""], "explanation": ["걷기가 이어짐"],
                         "axis": [""], "author_stated": ["아니오"]})
        return {"state": ["이어짐" if rels else "처음 쓰는 주제"], "summary": ["관측"], "question": [""],
                "relations": rels, "reached": []}

    # Solar
    def _chat(self, model, messages, **kw):
        self.calls["chat"] += 1
        self.sent.append(json.dumps(messages, ensure_ascii=False))
        if messages[0]["content"] == LLM_PROMPT:
            if isinstance(self.crisis_llm, Exception):
                raise self.crisis_llm
            return _o(choices=[_o(message=_o(content=self.crisis_llm))], usage=_o(prompt_tokens=100, completion_tokens=10))
        user = messages[-1]["content"]
        who = next((n for n in re.findall(r"([가-힣]{2})(?:이가|이랑|이도)", user)), "")
        msg = f"오늘도 걷기를 적어 줬네요. {who}와 함께한 시간이 힘이 됐겠어요."
        return _o(choices=[_o(message=_o(content=json.dumps({"message": msg, "next_question": ""}, ensure_ascii=False)))],
                  usage=_o(prompt_tokens=100, completion_tokens=20))

    def _embed(self, model, input):
        self.calls["embed"] += 1
        self.sent.append(json.dumps(input, ensure_ascii=False))
        vec = lambda t: [b / 255 for b in hashlib.sha256(t.encode()).digest()[:8]]   # noqa: E731
        return _o(data=[_o(embedding=vec(t)) for t in input], usage=_o(total_tokens=10))


@pytest.fixture
def env(monkeypatch, tmp_path):
    fake = FakeUpstage()
    monkeypatch.setattr(config, "DIARY_ENC_KEY", security.new_master_key())
    monkeypatch.setattr(config, "LOG_TO_FILE", True)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(config, "RECORD_AGENT_ID", "rec-agent")
    monkeypatch.setattr(config, "OBSERVE_AGENT_ID", "obs-agent")
    monkeypatch.setattr(studio, "_client", fake)
    monkeypatch.setattr(llm, "_client", _o(chat=fake.chat, embeddings=fake.embeddings))
    return types.SimpleNamespace(fake=fake, repo=MemRepo(), logs=tmp_path / "logs")


def write(env, uid, title, text, when):
    eid = diary.new_id("e")
    with env.repo.session(uid) as s:
        diary.create_entry(s, eid, diary.parse_dt(when), None, title, text)
    steps = []
    graph.run(env.repo, uid, eid, lambda p: steps.append(p["step"]))
    with env.repo.session(uid) as s:
        return eid, steps, views.entry_result(s, eid)


def test_order_result_and_no_real_names(env):
    e1, steps1, r1 = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    assert steps1 == graph.ORDER
    assert r1["status"] == "done" and r1["crisis"] is False and len(r1["thoughts"]) == 2
    assert {t["kind"] for t in r1["thoughts"]} == {"다짐", "감정"}
    assert any(t["grateful"] for t in r1["thoughts"])
    assert r1["thoughts"][0]["state"] == {"type": "다짐", "status": "열림", "mistake": False}
    assert "민준" in r1["message"]["text"]                    # 가명으로 받은 답을 원래 이름으로 되돌림
    assert r1["message"]["mode"] == "normal" and r1["message"]["check_in"] is None   # 평범한 글에는 안부 한 줄 없음
    e2, steps2, r2 = write(env, U1, *DAY2, "2026-10-03T22:00:00+09:00")
    assert steps2 == graph.ORDER
    assert r2["past"] and r2["past"][0]["entry_id"] == e1      # 둘째 글에서 지난 생각이 나옴
    assert r2["relations"] and r2["relations"][0]["from_entry"] == e1 and r2["relations"][0]["to_entry"] == e2
    with env.repo.session(U1) as s:
        people = {p["name"] for p in diary.people(s)}
        u = views.universe(s)
    assert set(NAMES) <= people                               # 새 이름 자동 등록
    assert u["suns"] and u["stars"] and len(u["planets"]) == 2 and u["links"]
    # 외부로 나간 모든 요청에 실명이 0건
    sent = "\n".join(env.fake.sent)
    assert sent and not [n for n in NAMES if n in sent]
    assert env.fake.calls["record"] == 2 and env.fake.calls["observe"] == 2


def test_past_only_from_earlier_written_entries(env):
    """옛 글을 나중에 가져와도(WS17) 지난 생각 후보는 지금 글보다 먼저 쓴 기록만."""
    e_new, _, _ = write(env, U1, *DAY2, "2026-10-03T22:00:00+09:00")
    e_old, _, r_old = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")   # 뒤늦게 정리한 더 옛 글
    assert r_old["past"] == [] and r_old["relations"] == []                 # 나중에 쓴 글의 생각은 '지난 생각'이 아님
    _, _, r3 = write(env, U1, "걷기 닷새째", "아침 걷기를 닷새째 했다. 민준이랑 걸으니 즐겁다.", "2026-10-05T22:00:00+09:00")
    assert {p["entry_id"] for p in r3["past"]} <= {e_new, e_old} and r3["past"]   # 먼저 쓴 두 글은 그대로 후보


def test_stored_text_is_encrypted_and_vectors_have_no_text(env):
    e1, _, _ = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    raw = json.dumps({t: [{k: (v.hex() if isinstance(v, bytes) else str(v)) for k, v in r.items()} for r in rows]
                      for t, rows in env.repo.store.tables.items()}, ensure_ascii=False)
    for word in ("걷기", "민준", "아침"):
        assert word not in raw
    docs, metas = env.repo.vectors.documents(U1)
    assert docs and all(d is None for d in docs)
    assert all(set(m) == {"entry_id", "star_id", "written_at", "kind"} for m in metas)


SHOWN_BAD = re.compile(r"(?<!\d)(?:109|112|119)(?!\d)|마들랜|상담")   # 시험 단계: 보이는 글에 단체 · 번호 없음


def test_crisis_keeps_usual_result_with_check_in(env):
    """동규 2026-10-08 시험 단계 결정: 위기여도 평소 결과(생각 · 우주 행성) + 위로 한마디(팩폭은 다정하게) + 안부 한 줄."""
    with env.repo.session(U1) as s:
        diary.save_profile(s, settings={"tone": "팩폭", "fact_bomb_ack": True})
    eid, steps, r = write(env, U1, *CRISIS, "2026-10-02T23:30:00+09:00")
    assert steps == graph.ORDER and r["status"] == "done" and r["thoughts"]
    m = r["message"]
    assert r["crisis"] is True and "care" not in r
    assert m["mode"] == "comfort" and m["tone"] == "다정하게" and r["next_question"]["kind"] == "none"
    assert m["check_in"] in voice.CHECK_IN["다정하게"]
    shown = " ".join([m["text"], m["check_in"], r["next_question"]["text"], *[t["text"] for t in r["thoughts"]]])
    assert not SHOWN_BAD.search(shown)
    assert env.fake.calls["record"] == 1 and env.fake.calls["observe"] == 1
    with env.repo.session(U1) as s:
        assert eid in [p["id"] for p in views.universe(s)["planets"]]
        assert diary.entry(s, eid)["data"]["crisis"] is True                   # 감지 결과는 enc 안에 남김


def test_crisis_check_failure_adds_check_in_only(env):
    env.fake.crisis_llm = RuntimeError("network")      # 규칙은 위기 아님, Solar 2차 판정 실패(llm_error)
    _, steps, r = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    assert steps == graph.ORDER and r["crisis"] is False
    assert r["message"]["mode"] == "normal" and r["message"]["check_in"] in voice.CHECK_IN["다정하게"]


def test_value_or_empty_topic_goes_to_other_star(env, monkeypatch):
    """가치 이름(배려) · 빈 주제는 '기타 생각' 작은 별로 모으고, 그 별은 기록 Agent 의 기존 작은 별 목록에 넣지 않는다."""
    first = env.fake._record

    def record(html):
        d = first(html)
        for t, topic in zip(d["thoughts"], ["배려", ""]):
            t["topic"] = [topic]
        return d
    monkeypatch.setattr(env.fake, "_record", record)
    _, _, r = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    assert [t["topic"] for t in r["thoughts"]] == [graph.OTHER_TOPIC] * 2
    write(env, U1, *DAY2, "2026-10-03T22:00:00+09:00")
    with env.repo.session(U1) as s:
        assert [x["name"] for x in diary.stars(s)].count(graph.OTHER_TOPIC) == 1   # 두 글이 한 별에 모임
    assert not [h for h in env.fake.sent if f"<li>{graph.OTHER_TOPIC}</li>" in h]


def test_creative_record_gets_no_relations(env):
    """품질 3판: 시 · 창작 글(Classify '창작')의 생각은 다른 글과 잇지 않는다. 지난 생각으로는 고르되 관계는 버리고,
    관측 입력에 '글 유형: 창작'을 적어 Agent 도 알게 한다."""
    env.fake.classify = "창작"
    e1, _, r1 = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    env.fake.classify = "생각·성찰"
    _, _, r2 = write(env, U1, *DAY2, "2026-10-03T22:00:00+09:00")
    assert r1["record_type"] == "창작" and r1["thoughts"]                     # 생각 · 행성은 그대로 남음
    assert r2["past"] and r2["past"][0]["entry_id"] == e1 and r2["relations"] == []
    assert any("글 유형: 창작" in h for h in env.fake.sent if "관측 입력" in h)


def test_resume_skips_finished_steps(env):
    env.fake.fail_observe = 2          # 관측 Agent 가 두 번(다시 시도 포함) 실패 → 기록 failed
    eid = diary.new_id("e")
    with env.repo.session(U1) as s:
        diary.create_entry(s, eid, diary.parse_dt("2026-10-01T22:00:00+09:00"), "맑음", *DAY1)
    with pytest.raises(studio.StudioError):
        graph.run(env.repo, U1, eid)
    with env.repo.session(U1) as s:
        e = diary.entry(s, eid)
    assert e["status"] == "failed" and e["error_code"] == "studio_failed" and e["step"] == "past"
    assert env.fake.calls["record"] == 1
    steps = []
    graph.run(env.repo, U1, eid, lambda p: steps.append(p["step"]))
    assert steps == graph.ORDER                        # 진행은 처음부터 다시 알리되
    assert env.fake.calls["record"] == 1               # 끝난 기록 Agent 는 다시 부르지 않음
    with env.repo.session(U1) as s:
        assert diary.entry(s, eid)["status"] == "done"
        assert diary.entry(s, eid)["steps_enc"] is None   # 다 끝나면 단계별 저장값(원문 포함)을 지운다


def test_real_name_leak_blocks_external_call(env, monkeypatch):
    from app.agents import tools
    monkeypatch.setattr(tools, "mask_obj", lambda obj, people: (obj, {}))   # 가명 처리가 고장 났다고 치면
    eid = diary.new_id("e")
    with env.repo.session(U1) as s:
        diary.create_entry(s, eid, diary.parse_dt("2026-10-01T22:00:00+09:00"), None, *DAY1)
    with pytest.raises(Exception) as e:
        graph.run(env.repo, U1, eid)
    assert graph.error_code(e.value) == "real_name_leak"
    assert env.fake.calls["record"] == 0                           # 기록 Agent 로 보내기 전에 막음
    # 앞서 나간 위기 2차 판정은 detect_crisis 가 스스로 가명 처리한다
    assert not [n for p in env.fake.sent for n in NAMES if n in p]


def test_logs_have_no_raw_text(env):
    write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    write(env, U1, *DAY2, "2026-10-03T22:00:00+09:00")
    text = "".join(p.read_text() for p in env.logs.glob("agent_flow_*.log"))
    assert '"event": "step"' in text and '"event": "guard"' in text
    for w in (*NAMES, "걷기", "아침", "고맙", "사흘"):
        assert w not in text, w
    for line in text.splitlines():
        assert set(json.loads(line)) <= {"ts", "event"} | __import__("app.core.logger", fromlist=["ALLOWED"]).ALLOWED


def test_other_user_cannot_read(env):
    e1, _, _ = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    with env.repo.session("22222222-2222-2222-2222-222222222222") as s:
        assert views.entry_result(s, e1) is None and diary.people(s) == []


def test_studio_files_deleted_after_success_and_failure(env):
    env.fake.fail_observe = 2
    eid = diary.new_id("e")
    with env.repo.session(U1) as s:
        diary.create_entry(s, eid, diary.parse_dt("2026-10-01T22:00:00+09:00"), None, *DAY1)
    with pytest.raises(studio.StudioError):
        graph.run(env.repo, U1, eid)
    graph.run(env.repo, U1, eid)
    assert env.fake.store and sorted(env.fake.deleted) == sorted(env.fake.store)   # 올린 파일 = 지운 파일(실패한 실행 포함)


def test_studio_file_delete_failure_only_logged(env, monkeypatch):
    def boom(fid):
        raise RuntimeError("x")
    monkeypatch.setattr(env.fake.files, "delete", boom)
    _, steps, r = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    assert r["status"] == "done"
    text = "".join(p.read_text() for p in env.logs.glob("agent_flow_*.log"))
    assert '"what": "studio_file_delete"' in text and '"code": "RuntimeError"' in text


def test_mood_marks_only_inside_enc(env):
    _, _, r = write(env, U1, *CRISIS, "2026-10-02T23:30:00+09:00")
    assert r["crisis"] is True and r["message"]["mode"] == "comfort"
    write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    t = env.repo.store.tables
    assert all("crisis" not in e for e in t["entries"])
    assert all("mode" not in m and "check_in" not in m for m in t["messages"])
    assert all(set(r["meta"]) <= {"checks"} and isinstance(r["meta"].get("checks", 0), int) for r in t["runs"])
    with env.repo.session(U1) as s:
        assert [e["crisis"] for e in diary.entries(s)].count(True) == 1
        assert {views.entry_result(s, e["id"])["message"]["mode"] for e in diary.entries(s)} == {"comfort", "normal"}


def test_quality_tool_measures_service_path(env):
    """품질 3판 측정 도구(tools/quality_v3.py)가 서비스 길을 끝까지 돌고 생각 · 관계(날것 + 규칙 판정) · 비용 · 판정 양식을 낸다.
    유료로 29편을 돌리기 전에 끝에서 깨지지 않는지 가짜 Studio 로 본다."""
    import importlib.util
    from pathlib import Path
    from app.agents import tools
    spec = importlib.util.spec_from_file_location("quality_v3", Path(__file__).resolve().parents[1] / "tools/quality_v3.py")
    q = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(q)
    with env.repo.session(U1) as s:
        for n in NAMES:
            diary.add_person(s, n, relation="친구")
    recs = [{"id": f"R{i}", "day": w[:10], "written_at": w, "title": t, "body": b} for i, ((t, b), w) in
            enumerate([(DAY1, "2026-10-01T22:00:00+09:00"), (DAY2, "2026-10-03T22:00:00+09:00")])]
    lines, observe = [], tools.run_observe_agent
    res, rows = q.measure(env.repo, U1, recs, "t", ledger=lambda *a: lines.append(a))
    assert res["done"] == 2 and res["failed_first_run"] == 0 and len(lines) == 2 and res["est_usd"] > 0.2
    assert res["thoughts"] == sum(len(r["thoughts"]) for r in res["detail"]) > 0 and "다짐" in res["kinds"]
    assert res["record_types"] == {"생각·성찰": 2}
    assert res["detail"][1]["relations_raw"][0]["service"] == "남음 → 이어짐"
    assert res["relations_raw"]["relations_cross_record"] == res["relations_shown"]["relations_cross_record"] == 1
    assert [(r["from_day"], r["to_day"], r["service"]) for r in rows] == [("2026-10-01", "2026-10-03", "남음 → 이어짐")]
    from app.service.rules import filter_relations
    assert tools.run_observe_agent is observe and graph.filter_relations is filter_relations   # 엿보기를 풀었음
    assert not [n for n in NAMES if n in "\n".join(env.fake.sent)]
