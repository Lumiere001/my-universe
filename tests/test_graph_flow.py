"""그래프 순서 · 위기 분기 · 이어 하기 · 외부 요청 실명 0건 · 원문 없는 로그 (외부 클라이언트는 가짜, 저장소는 메모리)."""
import hashlib
import json
import re
import types

import pytest

from app.agents import graph, studio
from app.core import config, llm, security
from app.repository import MemRepo, diary, views

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
        self.files = _o(create=self._file)
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
        out = [_o(content=[_o(text=json.dumps({"elements": [{"page": 1}]}))]), _o(content=[_o(text="생각·성찰")]),
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


def test_stored_text_is_encrypted_and_vectors_have_no_text(env):
    e1, _, _ = write(env, U1, *DAY1, "2026-10-01T22:00:00+09:00")
    raw = json.dumps({t: [{k: (v.hex() if isinstance(v, bytes) else str(v)) for k, v in r.items()} for r in rows]
                      for t, rows in env.repo.store.tables.items()}, ensure_ascii=False)
    for word in ("걷기", "민준", "아침"):
        assert word not in raw
    docs, metas = env.repo.vectors.documents(U1)
    assert docs and all(d is None for d in docs)
    assert all(set(m) == {"entry_id", "star_id", "written_at", "kind"} for m in metas)


def test_crisis_goes_to_care_without_paid_calls(env):
    _, steps, r = write(env, U1, *CRISIS, "2026-10-02T23:30:00+09:00")
    assert steps == ["safety", "save"]
    assert r["crisis"] is True and "109" in r["care"]["message"] and r["message"]["mode"] == "care"
    assert {x["name"] for x in r["care"]["resources"]} >= {"자살예방 상담전화"}
    assert env.fake.calls == {"record": 0, "observe": 0, "chat": 0, "embed": 0}


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
