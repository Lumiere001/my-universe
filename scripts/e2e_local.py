"""
로컬 e2e(유료): 서버(8001)를 띄우고 시험용 계정(e2e@my-universe.test)으로 가상 인물 '지호'의 일기 3편 + 위기 글 1편을
/diary/stream 으로 실제 Studio 2판 + Solar 에 돌린다. 결과는 원문 없이 docs/ws5-e2e.md 에 표로 쓴다.

    scripts/dev_up.sh                                  # 먼저(로컬 Supabase · ChromaDB · .env.local · 계정)
    uv run --frozen python scripts/e2e_local.py        # 유료(상한 CAP_USD), runs/cost_ledger.jsonl 에 한 줄

일기는 모두 지어낸 글이다(실제 일기 아님). 서버는 끝나면 끄고, 로컬 Supabase · ChromaDB 는 켜 둔다.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core import config, seed  # noqa: E402
from app.repository import PgRepo  # noqa: E402

LEDGER = Path("/Users/east_star/Projects/my-universe/runs/cost_ledger.jsonl")
CAP_USD, TOTAL_STOP_USD = 1.5, 40.0
BASE = "http://localhost:8001"
ORDER = ["safety", "names", "record", "past", "observe", "voice", "save"]
RESULT_KEYS = {"id", "status", "step", "written_at", "title", "weather", "crisis", "info", "thoughts", "relations",
               "past", "reached", "message", "next_question", "people_questions"}
NAMES = ("민준", "서윤")
DIARIES = [   # 가상 인물 지호(대학생). 다짐 → 어긋남 · 바뀜 → 다시 지킴, 사람 이름 포함
    ("2026-10-05T23:00:00+09:00", "구름 조금", "축제 부스를 맡은 날",
     "오늘 동아리 회의에서 축제 부스 준비를 맡았다. 시험 기간이랑 겹쳐서 솔직히 걱정이 된다. 그래도 맡은 일은 끝까지 해내고 싶다.\n"
     "이번 주부터 매일 밤 11시 전에 그날 할 일을 정리하고 자겠다. 회의 끝나고 민준이가 같이 하자고 해 줘서 고마웠다."),
    ("2026-10-07T23:30:00+09:00", "흐림", "또 미룬 이틀",
     "이틀 동안 할 일 정리를 못 하고 그냥 잤다. 피곤하다는 핑계로 또 미뤘다. 민준이는 벌써 부스 도안을 다 그려 왔는데 나만 뒤처진 것 같았다.\n"
     "예전에는 혼자 다 해내야 책임감 있는 거라고 생각했는데, 오늘 민준이랑 일을 나눠 보니 같이 하는 게 더 낫다는 걸 알았다."),
    ("2026-10-09T22:40:00+09:00", "맑음", "다시 지킨 밤",
     "오늘은 11시 전에 할 일을 정리하고 잤다. 사흘 만에 다시 지킨 셈이다. 부스 일은 서윤 선배가 도와주기로 했다.\n"
     "일을 나눠서 하니까 시험공부 시간도 조금 생겼다. 다음 주 축제 때까지 이 방식대로 나눠서 하겠다."),
]
CRISIS = ("2026-10-10T01:10:00+09:00", None, "", "요즘 아무것도 의미가 없다. 그냥 사라지고 싶다는 생각이 계속 든다.")
FRAGMENTS = [w for _, _, title, text in DIARIES + [CRISIS] for w in [title, *[s.strip() for s in text.replace("\n", " ").split(".")]]
             if len(w) >= 6] + list(NAMES)


def ledger_total():
    return sum(json.loads(x).get("est_usd", 0) for x in LEDGER.read_text().splitlines() if x.strip()) if LEDGER.exists() else 0.0


def sse(client, token, body):
    ev, t0, keepalive = [], time.time(), 0
    with client.stream("POST", f"{BASE}/diary/stream", json=body, headers={"Authorization": f"Bearer {token}"}) as r:
        r.raise_for_status()
        buf = ""
        for chunk in r.iter_text():
            buf += chunk
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                if block.startswith(":"):
                    keepalive += 1
                    continue
                lines = dict(x.split(": ", 1) for x in block.split("\n") if ": " in x)
                ev.append((lines["event"], json.loads(lines["data"])))
    return ev, round(time.time() - t0, 1), keepalive


def entry_cost(eid):
    with psycopg.connect(config.DATABASE_URL) as c:
        r = c.execute("select coalesce(sum(est_usd),0), coalesce(sum(calls),0) from runs where entry_id = %s", [eid]).fetchone()
    return float(r[0]), int(r[1])


def main():
    before = ledger_total()
    print(f"원장 합계(전): ${before:.3f}")
    if before > TOTAL_STOP_USD:
        sys.exit("누적 $40 을 넘어 멈춥니다.")
    token, uid = seed.token(seed.ACCOUNTS["e2e"])
    seed.wipe(PgRepo(config.DATABASE_URL), uid)
    log = config.LOG_DIR / f"agent_flow_{datetime.now():%Y%m%d}.log"
    log_start = log.stat().st_size if log.exists() else 0
    env = {**os.environ, "LOG_TO_FILE": "1"}
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", "8001"], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows, spent, calls = [], 0.0, 0
    try:
        for _ in range(60):
            try:
                if httpx.get(f"{BASE}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        with httpx.Client(timeout=httpx.Timeout(30, read=60)) as client:
            for i, (when, weather, title, text) in enumerate(DIARIES + [CRISIS], 1):
                if spent > CAP_USD - 0.3:
                    print("비용 상한 가까이라 멈춥니다.")
                    break
                ev, secs, ka = sse(client, token, {"title": title, "text": text, "written_at": when, "weather": weather})
                kind, res = ev[-1]
                steps = [d["step"] for e, d in ev if e == "progress"]
                eid = (ev[0][1] or {}).get("entry_id")
                usd, n = entry_cost(eid)
                spent, calls = spent + usd, calls + n
                crisis = i == len(DIARIES) + 1
                row = {"no": i, "day": when[:10], "crisis": crisis, "event": kind, "seconds": secs, "keepalive": ka,
                       "steps_ok": steps == ORDER,   # 위기 글도 평소 흐름(시험 단계, 2026-10-08 동규)
                       "entry_id_all": all(d.get("entry_id") == eid for e, d in ev if e in ("progress", "error")),
                       "calls": n, "usd": round(usd, 4)}
                if kind == "result":
                    row.update(keys_ok=RESULT_KEYS <= set(res), thoughts=len(res["thoughts"]), past=len(res["past"]),
                               relations=[r["type"] + ("(점선)" if r["line"] == "점선" else "") for r in res["relations"]],
                               kinds=sorted({t["kind"] for t in res["thoughts"]}), reached=len(res["reached"]),
                               mode=(res["message"] or {}).get("mode"), check_in=bool((res["message"] or {}).get("check_in")),
                               people_q=len(res["people_questions"]), next_kind=(res["next_question"] or {}).get("kind"))
                else:
                    row.update(code=res.get("code"))
                rows.append(row)
                print({k: v for k, v in row.items()}, flush=True)
            uni = client.get(f"{BASE}/universe", headers={"Authorization": f"Bearer {token}"}).json()
    finally:
        server.terminate()
        server.wait(10)
    checks = verify(uid, uni, log, log_start, rows)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "ws": "WS5",
                            "what": f"로컬 e2e 가상 인물 일기 {len(DIARIES)}편 + 위기 1편(Studio 2판 + Solar, /diary/stream)",
                            "calls": calls, "est_usd": round(spent, 3)}, ensure_ascii=False) + "\n")
    print(f"원장 합계(후): ${ledger_total():.3f} (이번 ${spent:.3f}, 호출 {calls}번)")
    write_doc(rows, uni, checks, spent, calls)


def verify(uid, uni, log, log_start, rows):
    out = {}
    with psycopg.connect(config.DATABASE_URL) as c:
        blobs = [bytes(x) for t in ("entries", "thoughts", "people", "relations", "messages", "stars")
                 for (x,) in c.execute(f"select enc from {t} where user_id = %s and enc is not null", [uid]).fetchall()]
        steps_left = c.execute("select count(*) from entries where user_id = %s and steps_enc is not null", [uid]).fetchone()[0]
    out["DB 본문 · 생각 · 이름이 암호문(원문 조각 0개)"] = bool(blobs) and not any(f.encode() in b for b in blobs for f in FRAGMENTS)
    out["끝난 기록의 단계별 저장값 지움"] = steps_left == 0
    docs, metas = PgRepo(config.DATABASE_URL).vectors.documents(uid)
    out["Chroma 에 원문 없음(문서 칸 비움, 메타는 id · 종류 · 시각만)"] = bool(metas) and all(d is None for d in docs) and \
        all(set(m) == {"user_id", "entry_id", "star_id", "written_at", "kind"} for m in metas)
    text = log.read_text(encoding="utf-8")[log_start:] if log.exists() else ""
    out["실행 기록에 원문 · 이름 없음"] = bool(text) and not any(f in text for f in FRAGMENTS)
    guards = [json.loads(x) for x in text.splitlines() if '"event": "guard"' in x]
    out[f"외부 요청 직전 실명 검사 {sum(g.get('ok') is True for g in guards)}번 통과 · 막힘 0번"] = \
        bool(guards) and all(g.get("ok") for g in guards)
    normal = [r for r in rows if not r["crisis"] and r["event"] == "result"]
    out["둘째 · 셋째 글에 지난 생각이 나옴"] = len(normal) >= 3 and all(r["past"] for r in normal[1:3])
    out["둘째 · 셋째 글에 관계가 나옴"] = len(normal) >= 3 and all(r["relations"] for r in normal[1:3])
    out["진행 순서 · result 모양(api-v8)"] = all(r["steps_ok"] and r.get("keys_ok", True) and r["entry_id_all"] for r in rows)
    out["/universe 에 해 · 작은 별 · 행성 · 선"] = all(uni.get(k) for k in ("suns", "stars", "planets", "links"))
    crisis = [r for r in rows if r["crisis"]]
    out["위기 글: 평소 결과 + 위로 한마디 + 안부 한 줄"] = bool(crisis) and crisis[0].get("mode") == "comfort" and \
        bool(crisis[0].get("check_in")) and bool(crisis[0].get("thoughts"))
    return out


def write_doc(rows, uni, checks, spent, calls):
    L = ["# WS5 로컬 e2e 결과", "",
         f"실행 {datetime.now():%Y-%m-%d %H:%M} · `uv run --frozen python scripts/e2e_local.py` · 시험용 계정 e2e@my-universe.test(로컬 Supabase).",
         "가상 인물 '지호'의 지어낸 일기 3편(다짐 → 미룸 · 생각 바뀜 → 다시 지킴, 사람 이름 2명) + 위기 글 1편을 "
         "`/diary/stream` 으로 실제 Studio 기록 · 관측 Agent 설정 2판과 Solar(solar-pro4)에 돌렸다. 이 문서에는 원문을 넣지 않는다.", "",
         "## 글마다", "",
         "| # | 날짜 | 결과 | 진행 순서 | 걸린 시간 | keep-alive | 생각 | 종류 | 지난 생각 | 관계 | 닿은 순간 | 한마디 | 다음 질문 | 이름 질문 | 외부 호출 | 추정 비용 |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        if r["event"] != "result":
            L.append(f"| {r['no']} | {r['day']} | 오류 `{r.get('code')}` | {'맞음' if r['steps_ok'] else '다름'} | {r['seconds']}초 | "
                     f"{r['keepalive']} | | | | | | | | | {r['calls']} | ${r['usd']} |")
            continue
        L.append(f"| {r['no']} | {r['day']} | {'완료(위기 · 안부 한 줄)' if r['crisis'] else '완료'} | {'맞음' if r['steps_ok'] else '다름'} | "
                 f"{r['seconds']}초 | {r['keepalive']} | {r['thoughts']} | {' · '.join(r['kinds'])} | {r['past']} | "
                 f"{' · '.join(r['relations']) or '-'} | {r['reached']} | {r['mode']} | {r['next_kind']} | {r['people_q']} | "
                 f"{r['calls']} | ${r['usd']} |")
    L += ["", "## 우주(/universe)", "",
          f"해 {len(uni['suns'])} · 작은 별 {len(uni['stars'])} · 행성 {len(uni['planets'])} · 선 {len(uni['links'])} · "
          f"쌍행성 {len(uni['twins'])} · 블랙홀 {len(uni['blackholes'])} · 사람 {len(uni['people'])}", "",
          "## 확인", "", "| 확인 | 결과 |", "| --- | --- |"]
    L += [f"| {k} | {'통과' if v else '실패'} |" for k, v in checks.items()]
    L += ["", f"비용: 외부 호출 {calls}번, 추정 ${spent:.3f}(runs 표 합계, 원장 `runs/cost_ledger.jsonl` WS5 줄).", ""]
    (ROOT / "docs" / "ws5-e2e.md").write_text("\n".join(L), encoding="utf-8")
    print("docs/ws5-e2e.md 를 썼어요.", json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
