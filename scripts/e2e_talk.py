"""
로컬 e2e(유료, WS19 · WS20): 가상 인물 '지호'로 대화 3번 — ① 첫 만남 ② 다짐 안부(지난 기록 물음 포함) ③ 지난 기록에서 시작
('이 이야기 이어 하기'). 대화마다 턴 → 대화 마치고 정리하기(save 앞에서 멈춤) → 요약 확인(고치기) → 저장을 실제 Solar ·
Studio 2판 · 로컬 Supabase · ChromaDB 로 돌린다. 서버를 따로 띄우지 않고 앱을 프로세스 안에서 부른다(포트를 다른 갈래와 나누지 않음).

    scripts/dev_up.sh                                  # 먼저(로컬 Supabase · ChromaDB · .env.local)
    uv run --frozen python scripts/e2e_talk.py         # 유료(상한 CAP_USD), runs/cost_ledger.jsonl 에 한 줄

말은 모두 지어낸 글이다(실제 일기 아님). 계정은 이 시험 전용(ws19-talk@my-universe.test, 로컬에만).
결과: docs/ws19-e2e.md(가상 인물 글이라 별지기 답은 그대로 적는다).
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core import config, seed  # noqa: E402
from app.repository import PgRepo  # noqa: E402

LEDGER = Path("/Users/east_star/Projects/my-universe/runs/cost_ledger.jsonl")
CAP_USD, TOTAL_STOP_USD = 0.6, 40.0
EMAIL = "ws19-talk@my-universe.test"
NAMES = ("민준", "서윤")
TALKS = [   # (이름, 여는 방법, 사용자 말들, 확인 화면에서 할 일)
    ("첫 만남", None, ["분주함이요. 동아리 회의에서 축제 부스 준비를 맡았어요.",
                    "시험 기간이랑 겹쳐서 걱정돼요. 그래도 이번 주부터 매일 밤 11시 전에 할 일을 정리하고 자겠다고 다짐했어요.",
                    "회의 끝나고 민준이가 같이 하자고 해 줘서 고마웠어요. 오늘은 여기까지 할게요."], "agree"),
    ("다짐 안부", None, ["이틀 동안 못 지켰어요. 피곤하다는 핑계로 또 미뤘어요.",
                     "예전에 축제 부스 얘기 뭐라고 했지?",
                     "민준이랑 일을 나눠 보니 혼자 다 하는 것보다 같이 하는 게 낫다는 걸 알았어요. 이만 잘게요."], "fix_kind"),
    ("지난 기록에서 시작", "first_entry", ["부스 도안은 서윤 선배가 도와주기로 했어요. 일을 나누니까 시험공부 시간도 생겼어요.",
                                    "다음 주 축제 때까지 이 방식대로 나눠서 하겠다고 마음먹었어요. 오늘은 여기까지."], "remove"),
]
FRAGMENTS = [s.strip() for _, _, said, _ in TALKS for t in said for s in t.split(".") if len(s.strip()) >= 8] + list(NAMES)


def ledger_total():
    return sum(json.loads(x).get("est_usd", 0) for x in LEDGER.read_text().splitlines() if x.strip()) if LEDGER.exists() else 0.0


def events(text):
    out = []
    for block in text.split("\n\n"):
        lines = [x for x in block.split("\n") if x and not x.startswith(":")]
        if lines:
            out.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return out


def cost(uid, since):
    with psycopg.connect(config.DATABASE_URL) as c:
        r = c.execute("select coalesce(sum(est_usd),0), coalesce(sum(calls),0) from runs where user_id = %s and created_at >= %s",
                      [uid, since]).fetchone()
    return float(r[0]), int(r[1])


def main():
    from fastapi.testclient import TestClient

    import main as app_main
    from app.deps import get_repo
    before = ledger_total()
    print(f"원장 합계(전): ${before:.3f}")
    if before > TOTAL_STOP_USD:
        sys.exit("누적 $40 을 넘어 멈춥니다.")
    pw = seed._read(seed.ENV_LOCAL)["DEV_TEST_PASSWORD"]
    seed.admin_user(EMAIL, pw)
    tok, uid = seed.token(EMAIL, pw)
    repo = PgRepo(config.DATABASE_URL)
    seed.wipe(repo, uid)
    seed.agree(repo, uid)
    app_main.app.dependency_overrides[get_repo] = lambda: repo
    c = TestClient(app_main.app)
    h = {"Authorization": f"Bearer {tok}"}
    log = config.LOG_DIR / f"agent_flow_{datetime.now():%Y%m%d}.log"
    log_start = log.stat().st_size if log.exists() else 0
    t_start = datetime.now().astimezone()
    rows, first_entry = [], None
    try:
        for name, how, said, act in TALKS:
            if cost(uid, t_start)[0] > CAP_USD - 0.15:
                print("비용 상한 가까이라 멈춥니다.")
                break
            body = {"from_entry": first_entry} if how == "first_entry" else None
            conv = c.post("/talk", headers=h, json=body).json()
            row = {"talk": name, "opening_kind": conv["turns"][0]["kind"], "opening": conv["turns"][0]["text"], "turns": []}
            t0 = time.time()
            for t in said:
                ev = events(c.post(f"/talk/{conv['id']}/turn/stream", headers=h, json={"text": t}).text)
                kind, data = ev[-1]
                if kind != "turn":
                    row["turns"].append({"said": t, "error": data.get("code")})
                    continue
                k = data["turns"][-1]
                row["turns"].append({"said": t, "kind": k["kind"], "mode": k["mode"], "reply": k["text"],
                                     "steps": [d["step"] for e, d in ev if e == "progress"]})
                row["summary"] = data["summary"]
            ev = events(c.post(f"/talk/{conv['id']}/finish/stream", headers=h).text)
            kind, draft = ev[-1]
            row["finish_steps"] = [d["step"] for e, d in ev if e == "progress"]
            row["draft_status"] = draft.get("status") if kind == "result" else f"error {draft.get('code')}"
            if kind != "result":
                rows.append(row)
                continue
            row["hidden_before_confirm"] = (draft["id"] not in [e["id"] for e in c.get("/diary", headers=h).json()["entries"]]
                                            and draft["id"] not in [p["id"] for p in c.get("/universe", headers=h).json()["planets"]])
            ts = draft["thoughts"]
            row["draft"] = {"summary": draft["info"]["summary"], "thoughts": [(t["kind"], t["quote"]) for t in ts],
                            "relations": [r["type"] + ("(점선)" if r["line"] == "점선" else "") for r in draft["relations"]],
                            "past": len(draft["past"])}
            fix = {"agree": {"agreed": ["summary", *[t["id"] for t in ts]]},
                   "fix_kind": {"fixes": [{"id": ts[0]["id"], "kind": "자기평가(부정)" if ts[0]["kind"] != "자기평가(부정)" else "해석"}]
                                if ts else [], "agreed": ["summary"]},
                   "remove": {"fixes": [{"id": ts[-1]["id"], "remove": True}] if len(ts) > 1 else [],
                              "summary": draft["info"]["summary"] + " (확인하며 고침)"}}[act]
            done = c.post(f"/diary/{draft['id']}/confirm", headers=h, json=fix).json()
            row["confirm"] = {"act": act, "status": done.get("status"), "confirmed": done.get("confirmed"),
                              "thoughts": len(done.get("thoughts") or []), "kinds": [t["kind"] for t in done.get("thoughts") or []],
                              "message": (done.get("message") or {}).get("text"), "check_in": (done.get("message") or {}).get("check_in")}
            row["talk_deleted"] = c.get(f"/talk/{conv['id']}", headers=h).status_code == 404
            row["seconds"] = round(time.time() - t0, 1)
            first_entry = first_entry or draft["id"]
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in ("turns",)}, ensure_ascii=False)[:600], flush=True)
        uni = c.get("/universe", headers=h).json()
    finally:
        app_main.app.dependency_overrides.clear()
    spent, calls = cost(uid, t_start)
    checks = verify(uid, rows, uni, log, log_start)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "ws": "WS19",
                            "what": f"로컬 e2e 대화 {len(rows)}번(첫 만남 · 다짐 안부 · 지난 기록에서 시작) → 요약 확인 → 저장"
                                    "(Solar + Studio 2판, 가상 인물 지호)", "calls": calls, "est_usd": round(spent, 4)},
                           ensure_ascii=False) + "\n")
    print(f"원장 합계(후): ${ledger_total():.3f} (이번 ${spent:.3f}, 호출 {calls}번)")
    write_doc(rows, uni, checks, spent, calls)


def verify(uid, rows, uni, log, log_start):
    out = {}
    out["첫 말: 첫 만남 · 다짐 안부 · 이어 하기"] = [r["opening_kind"] for r in rows] == ["first", "vow", "continue"]
    out["모든 턴에 답(오류 0)"] = all("reply" in t and t["reply"] for r in rows for t in r["turns"])
    out["턴 진행 순서 safety → past → reply → summary"] = all(t.get("steps") == ["safety", "past", "reply", "summary"]
                                                       for r in rows for t in r["turns"])
    recall = [t for r in rows for t in r["turns"] if t.get("kind") == "recall"]
    out["지난 기록 물음에 답함(물음으로 알아봄)"] = bool(recall)
    out["끝낼 말에 정리 제안(wrap)"] = all(any(t.get("kind") == "wrap" for t in r["turns"]) for r in rows)
    out["정리하기는 save 앞에서 멈춤(status confirm)"] = all(r.get("draft_status") == "confirm" and "save" not in r["finish_steps"]
                                                      for r in rows)
    out["확인 전에는 목록 · 우주에 안 보임"] = all(r.get("hidden_before_confirm") for r in rows)
    out["확인 뒤 저장(확인됨) · 대화 턴 지움"] = all((r.get("confirm") or {}).get("confirmed") == "확인됨" and r.get("talk_deleted")
                                              for r in rows)
    out["우주에 행성 3개"] = len(uni.get("planets") or []) == len(rows) == 3
    with psycopg.connect(config.DATABASE_URL) as c:
        blobs = [bytes(x) for t in ("entries", "thoughts", "people", "messages", "feedback", "conversations")
                 for (x,) in c.execute(f"select enc from {t} where user_id = %s and enc is not null", [uid]).fetchall()]
        left = c.execute("select count(*) from conversations where user_id = %s", [uid]).fetchone()[0]
        notes = c.execute("select value, count(*) from feedback where user_id = %s and target = 'confirm' group by value",
                          [uid]).fetchall()
    out["DB 에 원문 조각 0개(암호문만)"] = bool(blobs) and not any(f.encode() in b for b in blobs for f in FRAGMENTS)
    out["확인한 뒤 남은 대화 0개"] = left == 0
    out[f"확인 화면 피드백(오답 재료) {dict(notes)}"] = bool(notes)
    text = log.read_text(encoding="utf-8")[log_start:] if log.exists() else ""
    out["실행 기록에 원문 · 이름 없음"] = bool(text) and not any(f in text for f in FRAGMENTS)
    guards = [json.loads(x) for x in text.splitlines() if '"event": "guard"' in x]
    out[f"외부 요청 직전 실명 검사 {sum(g.get('ok') is True for g in guards)}번 통과 · 막힘 0번"] = bool(guards) and all(g.get("ok") for g in guards)
    return out


def write_doc(rows, uni, checks, spent, calls):
    L = ["# WS19 · WS20 로컬 e2e 결과 — 대화 3번", "",
         f"실행 {datetime.now():%Y-%m-%d %H:%M} · `uv run --frozen python scripts/e2e_talk.py` · 시험 전용 계정 {EMAIL}(로컬 Supabase · ChromaDB).",
         "가상 인물 '지호'(대학생, 친구 민준 · 선배 서윤)의 지어낸 말로 대화 → 정리하기 → 요약 확인 → 저장을 실제 Solar(solar-pro4) · "
         "Studio 기록 · 관측 Agent 2판에 돌렸다. 모두 지어낸 글이라 별지기 답을 그대로 적는다.", ""]
    for r in rows:
        L += [f"## {r['talk']}", "", f"- 첫 말(`{r['opening_kind']}`): {r['opening']}"]
        for t in r["turns"]:
            L += [f"- 나: {t['said']}", f"  - 별지기(`{t.get('kind', '오류')}`{' · ' + t['mode'] if t.get('mode') else ''}): "
                  + (t.get("reply") or t.get("error", "")).replace("\n", " / ")]
        if r.get("summary"):
            L.append(f"- 지금까지 정리: {r['summary']}")
        d = r.get("draft") or {}
        L += [f"- 정리하기: 진행 {' → '.join(r.get('finish_steps', []))} → `{r.get('draft_status')}`, 확인 전 목록 · 우주에 안 보임: "
              f"{'예' if r.get('hidden_before_confirm') else '아니오'}",
              f"- 초안 정리: 요약 \"{d.get('summary', '')}\" · 생각 {len(d.get('thoughts', []))}개("
              + ", ".join(f"{k} \"{' '.join(q.split())}\"" for k, q in d.get("thoughts", [])) + f") · 지난 생각 {d.get('past', 0)} · 관계 "
              + (" · ".join(d.get("relations", [])) or "-")]
        cf = r.get("confirm") or {}
        L += [f"- 요약 확인(`{cf.get('act')}`): {cf.get('confirmed')} · 생각 {cf.get('thoughts')}개({' · '.join(cf.get('kinds') or [])}) · "
              f"대화 턴 지움: {'예' if r.get('talk_deleted') else '아니오'} · {r.get('seconds')}초",
              f"- 저장 뒤 한마디: {cf.get('message')}" + (f" (안부: {cf['check_in']})" if cf.get("check_in") else ""), ""]
    L += ["## 우주(/universe)", "",
          f"해 {len(uni['suns'])} · 작은 별 {len(uni['stars'])} · 행성 {len(uni['planets'])} · 선 {len(uni['links'])} · 사람 {len(uni['people'])}", "",
          "## 확인", "", "| 확인 | 결과 |", "| --- | --- |"]
    L += [f"| {k} | {'통과' if v else '실패'} |" for k, v in checks.items()]
    L += ["", f"비용: 외부 호출 {calls}번, 추정 ${spent:.3f}(runs 표 합계, 원장 `runs/cost_ledger.jsonl` WS19 줄).", ""]
    (ROOT / "docs" / "ws19-e2e.md").write_text("\n".join(L), encoding="utf-8")
    print("docs/ws19-e2e.md 를 썼어요.", json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
