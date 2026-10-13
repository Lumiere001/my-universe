"""WS19 대화 Agent · 이야기하기: 첫 말(상황별) · 턴(SSE) · 지난 기록 인용 · 지난 기록 물음 · 위기 턴 · 마칠 때 · 지금까지 정리 ·
외부 요청 실명 0건 · 동의 · 지우기. 외부 호출은 가짜(FakeUpstage + 대화 프롬프트 가짜), 저장소는 메모리, 가상 인물 글만."""
import json
import re
import types

import pytest

from app.agents import chat_graph
from app.repository import conversations, diary
from app.service import chat, voice
from app.service.voice import checks
from tests.test_api_flow import H1, H2, client, events, write  # noqa: F401  (client 픽스처)
from tests.test_graph_flow import CRISIS, DAY1, NAMES, U1, _o, env  # noqa: F401  (env 픽스처)

TALK_SYS = "너는 일기장 '나의 우주'의 별지기다. 사용자와"
REPLIES = ["그랬군요. 그때 기분은 어땠어요?", "아침 공기가 좋았겠어요. 걷고 나서는 뭘 했어요?",
           "이야기해 줘서 고마워요. 내일 아침도 걸을 생각이에요?", "좋은 시간이었네요. 오늘 하루 중 언제가 제일 편했어요?",
           "듣고 있어요. 그다음엔 어떻게 됐어요?"]


def fake_talk(fake):
    """FakeUpstage 에 대화 · 정리 · 초안 · 판정 프롬프트 답을 더한다. queue: 다음 대화 답(dict 또는 함수), reply_calls: 대화 요청."""
    base = fake.chat.completions.create
    st = types.SimpleNamespace(queue=[], reply_calls=[], summary="나는 아침에 걸었다.", draft=None, fail=False, n=0)

    def create(model, messages, **kw):
        sys_ = messages[0]["content"]
        out = None
        if sys_.startswith(TALK_SYS):
            fake.sent.append(json.dumps(messages, ensure_ascii=False))
            st.reply_calls.append(messages)
            if st.fail:
                raise RuntimeError("down")
            d = st.queue.pop(0) if st.queue else {"reply": REPLIES[st.n % len(REPLIES)], "found": False}
            st.n += 1
            out = json.dumps(d(messages) if callable(d) else d, ensure_ascii=False)
        elif sys_ == checks.CRISIS_JUDGE:
            out = "ok"
        elif sys_ == checks.LINE_JUDGE:
            out = '{"violation": false, "line": 0, "reason": "없음"}'
        elif sys_ == chat.SUMMARY_SYS:
            fake.sent.append(json.dumps(messages, ensure_ascii=False))
            out = st.summary
        elif sys_.startswith(chat.DRAFT_SYS):
            fake.sent.append(json.dumps(messages, ensure_ascii=False))
            said = re.findall(r"^- (.*)$", messages[1]["content"], re.M)
            out = json.dumps(st.draft or {"title": "아침 걷기 이야기", "text": " ".join(said)}, ensure_ascii=False)
        if out is None:
            return base(model=model, messages=messages, **kw)
        return _o(choices=[_o(message=_o(content=out))], usage=_o(prompt_tokens=80, completion_tokens=20))

    fake.chat.completions.create = create
    return st


@pytest.fixture
def talk(client, env):  # noqa: F811
    return fake_talk(env.fake)


def start(client, h=H1, **body):  # noqa: F811
    r = client.post("/talk", headers=h, json=body or None)
    assert r.status_code == 200, r.text
    return r.json()


def say(client, cid, text, h=H1):  # noqa: F811
    r = client.post(f"/talk/{cid}/turn/stream", headers=h, json={"text": text})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    return events(r.text)


def past_quote(msgs):
    """대화 요청(가명 글)에 들어간 첫 지난 생각의 원문 인용."""
    u = msgs[-1]["content"]
    ctx = json.loads(u.split("대화:\n", 1)[1].split("\n\n지금 사용자 말:", 1)[0])
    return ctx["past"][0]["quote"]


def last(ev):
    kind, data = ev[-1]
    assert kind == "turn", ev
    return data


##################################################
# 첫 말 · 규칙 (LLM 없음)
##################################################

def test_opening_by_situation():
    first = {"kind": "first", "text": voice.FIRST_QUESTIONS[0], "vow": None}
    vow = {"kind": "free", "text": "다음엔 뭘 써 볼까요?", "vow": {"thought_id": "t1", "text": "매일 30분 걷겠다", "overdue": True}}
    asked = {"kind": "free", "text": "요즘 진로 고민은 어떻게 돼 가요?", "vow": None}
    none = {"kind": "none", "text": "", "vow": None}
    lead = {"day": "2026-10-01", "title": "아침 걷기 시작", "summary": "걷기", "quotes": ["매일 아침 30분 걷기를 하겠다"]}
    assert chat.opening(first) == {"kind": "first", "text": voice.FIRST_QUESTIONS[0], "sources": []}   # 첫 만남: 정해 둔 질문
    o = chat.opening(vow)
    assert o["kind"] == "vow" and "매일 30분 걷겠다" in o["text"] and "왜" not in o["text"]               # 다짐 안부(추궁 없이)
    assert chat.opening(asked) == {"kind": "question", "text": asked["text"], "sources": []}         # 남겨 둔 질문
    assert chat.opening(none, invite=True)["text"] == voice.INVITE                                  # 되고 싶은 모습 계기
    assert chat.opening(none)["kind"] == "free"
    o = chat.opening(vow, from_entry=lead)                                                          # 지난 기록에서 시작이 먼저
    assert o["kind"] == "continue" and "2026-10-01" in o["text"] and "아침 걷기 시작" in o["text"]
    assert o["sources"] == lead["quotes"]


@pytest.mark.parametrize("text,want", [
    ("예전에 진로 얘기 뭐라고 했지?", True), ("지난번에 걷기에 대해 어떻게 썼더라?", True), ("나 전에 운동 얘기 했었나?", True),
    ("그때 엄마가 뭐라고 했는지 모르겠어.", False), ("오늘은 진로 생각을 많이 했다.", False)])
def test_is_recall(text, want):
    assert chat.is_recall(text) is want


@pytest.mark.parametrize("text,turns,crisis,want", [
    ("이제 그만 잘게", 2, False, True), ("오늘은 여기까지 할게요", 1, False, True), ("회사를 그만두고 싶다", 2, False, False),
    ("아침에 걸었어", chat.WRAP_AFTER, False, True), ("이제 그만하고 싶어", 2, True, False)])
def test_should_wrap(text, turns, crisis, want):
    assert chat.should_wrap(text, turns, crisis) is want


def test_reply_checks():
    src = ["오늘 아침에 걸었다.", "매일 아침 30분 걷기를 하겠다"]
    ok = "지난 10/1에 '매일 아침 30분 걷기를 하겠다'라고 하셨는데, 오늘도 걸었네요. 어땠어요?"
    assert chat.problems(ok, sources=src, past_replies=[]) == []
    bad = "지난번에 '저녁마다 달리겠다'고 하셨죠. 오늘은 어땠어요?"                # 지난 기록에 없는 인용
    assert any("원문에 없는 인용" in p for p in chat.problems(bad, sources=src, past_replies=[]))
    assert chat.problems("'오늘 뭐 했지?'라고 하셨죠. 어디까지 했어요?", sources=["오늘 뭐 했지?"], past_replies=[]) == []   # 인용 속 ? 는 안 셈
    two = "걸었군요. 누구랑 걸었어요? 내일도 걸을 거예요?"                         # 질문 둘
    assert any("질문 2개" in p for p in chat.problems(two, sources=src, past_replies=[]))
    assert any("질문" in p for p in chat.problems("많이 힘들었겠어요. 어떤 일이 있었어요?", sources=src, past_replies=[],
                                                 crisis=True))                     # 위기 턴은 질문 없이
    assert chat.parse('{"reply": "네", "found": true}') == ("네", True)
    assert chat.parse('{"reply": "", "found": "false"}') == ("", False)
    assert chat.parse("그냥 글만 온 답") == ("그냥 글만 온 답", None)          # found 칸이 없으면 모름
    assert chat.parse("reply: 속상했겠어요.  \nfound: false") == ("속상했겠어요.", False)   # 2026-10-14 --live 에서 온 꼴
    past = [{"day": "2026-09-20", "thought": "주 3번 헬스", "quote": "이번 학기엔 주 3번 헬스 가야지"}]
    assert chat.cited("9/20에 '이번 학기엔 주 3번 헬스 가야지'라고 적었어요.", past)        # 글만 와도 원문 인용이면 찾은 것
    assert not chat.cited("9/20에 '매일 헬스'라고 적었어요.", past) and not chat.cited("헬스 이야기가 있었어요.", past)
    assert chat.recall_fallback([], "다정하게") == chat.NOT_FOUND["다정하게"]
    assert chat.recall_fallback([{"day": "2026-10-01", "quote": "매일 걷겠다", "thought": ""}], "담백하게") == \
        "2026-10-01에 '매일 걷겠다'라고 적었어요."


def test_recall_finds_sentences_in_entry_text():
    entries = [("e1", "2026-10-01", "동아리 회의에서 축제 부스 준비를 맡았다. 시험 기간이랑 겹쳐서 걱정된다."),
               ("e2", "2026-10-05", "오늘은 도서관에서 공부했다.\n부스 도안을 그렸다.")]
    hits = chat.sentence_hits("예전에 축제 부스 얘기 뭐라고 했지?", entries)
    assert [h["quote"] for h in hits] == ["부스 도안을 그렸다.", "동아리 회의에서 축제 부스 준비를 맡았다."]   # 최근 기록부터
    assert hits[0]["day"] == "2026-10-05" and hits[0]["entry_id"] == "e2"
    assert chat.sentence_hits("예전에 이사 얘기 뭐라고 했지?", entries) == []          # 없는 이야기는 못 찾음
    assert chat.sentence_hits("전에 뭐라고 했더라?", entries) == []                    # 찾을 낱말이 없음
    asked = [("e3", "2026-10-07", "예전에 축제 부스 얘기 뭐라고 했지? 부스는 서윤 선배가 돕기로 했다.")]
    assert [h["quote"] for h in chat.sentence_hits("지난번에 부스 얘기 어떻게 썼더라?", asked)] == ["부스는 서윤 선배가 돕기로 했다."]


def test_draft_checks_and_fallback(monkeypatch):
    said = ["오늘 아침에 민준이랑 걸었다.", "걷고 나니 머리가 맑았다."]
    assert chat.draft_problems("오늘 아침에 민준이랑 걸었다. 머리가 맑았다.", said) == []
    assert chat.draft_problems("나는 '매일 달리겠다'고 다짐했다.", said)              # 사용자 말에 없는 인용
    assert chat.draft_problems("오늘은 걸었다.", ["요즘 너무 지쳐서 죽고 싶다는 생각이 든다."], crisis=True) == ["위기였던 말이 빠짐"]
    monkeypatch.setattr(chat.llm, "chat", lambda *a, **k: "형식이 깨진 답")
    d = chat.draft(said)
    assert d == {"title": "", "text": "\n".join(said), "fallback": True}             # 두 번 다 실패 → 사용자 말 그대로


##################################################
# API: 열기 · 턴 · 가명 · 지난 기록
##################################################

def test_start_and_turn_without_real_names(client, env, talk):  # noqa: F811
    c = start(client)
    assert c["turns"] == [{"role": "keeper", "kind": "first", "text": voice.FIRST_QUESTIONS[0], "at": c["turns"][0]["at"]}]
    talk.queue.append(lambda msgs: {"reply": "그랬군요. " + msgs[-1]["content"].split("지금 사용자 말:\n")[1].split()[0]
                                    + " 함께 걸어서 어땠어요?", "found": False})
    ev = say(client, c["id"], "민준이랑 아침에 30분 걸었다.")
    assert [d["step"] for k, d in ev if k == "progress"] == ["safety", "past", "reply", "summary"]
    v = last(ev)
    assert v["turn_count"] == 1 and [t["role"] for t in v["turns"]] == ["keeper", "user", "keeper"]
    assert v["turns"][-1]["text"].startswith("그랬군요. 민준이랑")              # 가명으로 받은 답을 원래 이름으로 되돌림
    assert v["turns"][-1]["mode"] == "normal" and v["turns"][-1]["check_in"] is None
    sent = "\n".join(env.fake.sent)
    assert talk.reply_calls and not [n for n in NAMES if n in sent]             # 사람 목록에 없는 새 이름도 가명으로
    with env.repo.session(U1) as s:
        assert diary.people(s) == []                                            # 대화 중에는 사람 목록에 등록하지 않음
        raw = s.rows("conversations")[0]
        assert b"\xeb\xaf\xbc\xec\xa4\x80" not in bytes(raw["enc"])             # '민준'이 평문으로 없음(암호문)
        runs = [r for r in s.rows("runs") if r["step"] == "talk_turn"]
        assert runs and runs[0]["meta"]["turn"] == 1 and runs[0]["calls"] >= 2 and "민준" not in json.dumps(runs[0]["meta"])
    assert client.get("/talk", headers=H1).json()["conversations"][0]["id"] == c["id"]
    assert client.get(f"/talk/{c['id']}", headers=H2).status_code == 404            # 남의 대화
    assert client.post(f"/talk/{c['id']}/turn/stream", headers=H2, json={"text": "x"}).status_code == 404


def test_turn_cites_real_past_and_rejects_made_up_quote(client, env, talk):  # noqa: F811
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    c = start(client)
    assert c["turns"][0]["kind"] in ("vow", "question", "free")                  # 기록이 있으면 첫 만남 질문이 아님
    talk.queue.append(lambda msgs: {"reply": f"10/1에 '{past_quote(msgs)}'라고 하셨는데, 오늘도 걸었네요. 어땠어요?",
                                    "found": False})
    v = last(say(client, c["id"], "오늘 아침에도 걸었다."))
    said = re.findall(r"[^.]+\.", DAY1[1])
    assert any(f"'{q.strip()}'" in v["turns"][-1]["text"] for q in said)       # 실제 지난 생각의 원문 인용(이름은 되돌림)
    talk.queue += [{"reply": "지난번에 '저녁마다 달리겠다'고 하셨죠. 오늘은요?", "found": False}] * 2
    v = last(say(client, c["id"], "내일도 걸을 거야."))
    assert "저녁마다" not in v["turns"][-1]["text"] and v["turns"][-1]["text"] in chat.SAFE["다정하게"]   # 지어낸 인용 → 기본 문장


def test_recall_question(client, env, talk):  # noqa: F811
    c = start(client)
    v = last(say(client, c["id"], "예전에 걷기 얘기 뭐라고 했지?"))               # 기록이 없음 → Solar 없이 없다고
    assert v["turns"][-1]["text"] == chat.NOT_FOUND["다정하게"] and v["turns"][-1]["kind"] == "recall"
    assert talk.reply_calls == []
    write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    talk.queue.append(lambda msgs: {"reply": f"10/1에 '{past_quote(msgs)}'라고 적었어요.", "found": True})
    v = last(say(client, c["id"], "지난번에 걷기에 대해 뭐라고 썼더라?"))
    assert v["turns"][-1]["kind"] == "recall" and any(f"'{q.strip()}'" in v["turns"][-1]["text"]
                                                      for q in re.findall(r"[^.]+\.", DAY1[1]))
    talk.queue.append({"reply": "", "found": False})
    v = last(say(client, c["id"], "예전에 이사 얘기 뭐라고 했지?"))                # 맞는 기록이 없다고 판단 → 지어내지 않음
    assert v["turns"][-1]["text"] == chat.NOT_FOUND["다정하게"]


def test_crisis_turn_comforts_with_check_in(client, env, talk):  # noqa: F811
    with env.repo.session(U1) as s:
        diary.save_profile(s, settings={"tone": "팩폭", "fact_bomb_ack": True})
    c = start(client)
    talk.queue.append({"reply": "많이 힘들었겠어요. 이렇게 말해 줘서 고마워요. 여기 함께 있을게요.", "found": False})
    v = last(say(client, c["id"], CRISIS[1]))
    k = v["turns"][-1]
    assert k["mode"] == "comfort" and k["tone"] == "다정하게" and "?" not in k["text"]   # 팩폭도 다정하게, 질문 없이
    assert k["check_in"] in voice.CHECK_IN["다정하게"]
    assert "다정하게" in talk.reply_calls[-1][0]["content"] and "질문 · 제안을 넣지 않는다" in talk.reply_calls[-1][0]["content"]
    with env.repo.session(U1) as s:
        assert conversations.get(s, c["id"])["crisis"] is True                  # 감지 결과는 암호문 안에


def test_wrap_and_summary(client, env, talk):  # noqa: F811
    c = start(client)
    for t in ("아침에 걸었다.", "공원 한 바퀴를 돌았다."):
        v = last(say(client, c["id"], t))
    assert v["summary"] == ""
    v = last(say(client, c["id"], "점심엔 친구를 만났다."))                       # 세 턴마다 '지금까지 정리'
    assert v["summary"] == talk.summary
    talk.queue.append({"reply": "오늘은 걷기로 하루를 열었네요.", "found": False})
    v = last(say(client, c["id"], "이제 그만 잘게"))
    assert v["wrap"] and v["turns"][-1]["kind"] == "wrap"
    assert v["turns"][-1]["text"] == "오늘은 걷기로 하루를 열었네요.\n" + chat.WRAP["다정하게"]   # 한 줄 되짚기 + 정리 제안
    talk.summary = "나는 '하늘을 날았다'."                                          # 사용자 말에 없는 인용 → 앞 정리 유지
    for t in ("하나", "둘", "셋"):
        v = last(say(client, c["id"], t))
    assert v["summary"] == "나는 아침에 걸었다."


def test_turn_failure_keeps_nothing_and_consent(client, env, talk):  # noqa: F811
    c = start(client)
    talk.fail = True
    ev = say(client, c["id"], "아침에 걸었다.")
    assert ev[-1][0] == "error" and ev[-1][1]["code"] == "internal" and ev[-1][1]["resumable"]
    assert client.get(f"/talk/{c['id']}", headers=H1).json()["turn_count"] == 0  # 실패한 말은 저장 안 함(화면이 다시 보냄)
    with env.repo.session(U1) as s:
        s.delete("consents")
    assert client.post("/talk", headers=H1).json()["error"]["code"] == "consent_required"
    r = client.post(f"/talk/{c['id']}/turn/stream", headers=H1, json={"text": "x"})
    assert r.status_code == 403


def test_delete_talk_forget_person_and_wipe(client, env, talk):  # noqa: F811
    c = start(client)
    say(client, c["id"], "서윤이랑 저녁을 먹었다.")
    with env.repo.session(U1) as s:
        p = diary.add_person(s, "서윤", relation="친구")
        diary.delete_person(s, p["id"])                                         # 사람 지우기 = 대화 속 이름도 관계 말로
        assert "서윤" not in json.dumps(conversations.get(s, c["id"]), ensure_ascii=False, default=str)
        assert "conversations" in diary.WIPE
    assert client.delete(f"/talk/{c['id']}", headers=H1).status_code == 204
    assert client.get(f"/talk/{c['id']}", headers=H1).status_code == 404
    start(client)
    start(client)                                                               # 말 없이 둔 대화는 새로 열 때 치움
    with env.repo.session(U1) as s:
        assert len(s.rows("conversations")) == 1


def test_continue_from_entry(client, env, talk):  # noqa: F811
    _, ev = write(client, *DAY1, "2026-10-01T22:00:00+09:00")
    eid = ev[-1][1]["id"]
    c = start(client, from_entry=eid)
    assert c["from_entry"] == eid and c["turns"][0]["kind"] == "continue" and "아침 걷기 시작" in c["turns"][0]["text"]

    def lead(msgs):
        u = msgs[-1]["content"]
        assert "매일 아침 30분 걷기를 하겠다" in u                                 # 그 기록의 생각이 첫 맥락으로
        return {"reply": "'오늘부터 매일 아침 30분 걷기를 하겠다.'라고 하셨죠. 요즘은 어때요?", "found": False}
    talk.queue.append(lead)
    v = last(say(client, c["id"], "요즘은 이틀에 한 번 걷고 있어."))
    assert v["turns"][-1]["text"].startswith("'오늘부터")
    assert client.post("/talk", headers=H1, json={"from_entry": "bad id!"}).status_code == 422
    with env.repo.session(U1) as s:
        assert chat_graph._lead(s, "e_none") == (None, [])
