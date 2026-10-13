"""
로컬 e2e(유료, WS21): 골든셋 가상 인물 '서강'(p_office, 팀장 고민석 · 입사 동기 보람)의 지어낸 말을 macOS `say -v Yuna` 로 읽힌
가상 음성으로 말로 이야기하기 → 요약 확인까지 실제 ElevenLabs 받아쓰기(Scribe v2) · 읽어 주기 · Solar · Studio 2판 · 로컬
Supabase · ChromaDB 로 돌린다. 서버는 띄우지 않고 앱을 프로세스 안에서 부른다(포트를 다른 갈래와 나누지 않음).

  ① 짧은 턴 2개: 휴대폰 음성 메모 같은 m4a(4MB 아래라 그대로 보냄)
  ② 3분짜리 긴 이야기: 44.1kHz WAV(4.5MB 넘음 → 한 번에 보내면 413) → 화면(MicButton)처럼 16kHz 모노 2분 조각으로 나눠 받아쓰기
     → 대화 턴(via=voice) · '지금까지 정리' → 별지기가 이어 물음 → 읽어 주기 한 번 → 정리하기 → 요약 확인 → 저장

    scripts/dev_up.sh                                  # 먼저(로컬 Supabase · ChromaDB · .env.local)
    uv run --frozen python scripts/e2e_voice.py        # 유료(상한 CAP_USD), runs/cost_ledger.jsonl 에 한 줄

계정은 이 시험 전용(ws21-voice@my-universe.test, 로컬에만). 결과: docs/ws21-e2e.md. 음성 파일은 임시 폴더에만 만들고 지운다.
"""

import array
import difflib
import json
import subprocess
import sys
import tempfile
import time
import wave
from datetime import datetime
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core import config, seed  # noqa: E402
from app.repository import PgRepo  # noqa: E402

LEDGER = Path("/Users/east_star/Projects/my-universe/runs/cost_ledger.jsonl")
CAP_USD, TOTAL_STOP_USD = 0.5, 40.0
EMAIL = "ws21-voice@my-universe.test"
NAMES = ("고민석", "민석", "보람")
SHORT = ["오늘 신제품 시식 행사 기획안을 팀장님께 올렸어요. 민석 팀장님이 숫자를 다시 보자고 하셔서 조금 긴장했어요.",
         "점심엔 보람이랑 회사 앞 국숫집에 갔는데 같이 웃으니까 마음이 좀 풀렸어요."]
LONG = (ROOT / "scripts" / "e2e_voice_story.txt").read_text(encoding="utf-8").strip()
RATE, PIECE_S, TAIL_S = 16000, 120, 5     # components/MicButton.tsx 와 같은 값


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


def voices(tmp):
    """가상 음성: 짧은 말 둘은 m4a(AAC), 긴 이야기는 44.1kHz 16비트 WAV(약 3분)."""
    out = []
    for i, t in enumerate(SHORT):
        p = tmp / f"short{i + 1}.m4a"
        subprocess.run(["say", "-v", "Yuna", "-o", str(p), "--file-format=m4af", "--data-format=aac", t], check=True)
        out.append(p)
    (tmp / "long.txt").write_text(LONG, encoding="utf-8")
    p = tmp / "long.wav"
    subprocess.run(["say", "-v", "Yuna", "-r", "100", "-o", str(p), "--file-format=WAVE", "--data-format=LEI16@44100",
                    "-f", str(tmp / "long.txt")], check=True)
    return out, p


def pieces(src, tmp):
    """화면(MicButton)처럼: 16kHz 모노로 줄이고 2분마다, 그 앞 5초 안 가장 조용한 50ms 에서 자른 WAV 조각들."""
    mono = tmp / "long16.wav"
    subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{RATE}", "-c", "1", str(src), str(mono)], check=True)
    with wave.open(str(mono)) as w:
        x = array.array("h", w.readframes(w.getnframes()))
    size, tail, win = PIECE_S * RATE, TAIL_S * RATE, RATE // 20
    out, at = [], 0
    while len(x) - at > size + tail:
        cut, low = at + size, None
        for s in range(at + size - tail, at + size - win + 1, win):
            e = sum(v * v for v in x[s:s + win])
            if low is None or e < low:
                low, cut = e, s + win // 2
        out.append(x[at:cut])
        at = cut
    out.append(x[at:])
    blobs = []
    for part in out:
        b = tmp / f"piece{len(blobs) + 1}.wav"
        with wave.open(str(b), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(part.tobytes())
        blobs.append(b.read_bytes())
    return blobs


def similar(a, b):
    keep = lambda s: "".join(ch for ch in s if ch.isalnum())   # noqa: E731
    return round(difflib.SequenceMatcher(None, keep(a), keep(b)).ratio(), 3)


def main():
    from fastapi.testclient import TestClient

    import main as app_main
    from app.core import llm
    from app.deps import get_repo
    before = ledger_total()
    print(f"원장 합계(전): ${before:.3f}")
    if before > TOTAL_STOP_USD:
        sys.exit("누적 $40 을 넘어 멈춥니다.")
    if not config.ELEVENLABS_API_KEY:
        sys.exit("ELEVENLABS_API_KEY 가 없어요(.env).")
    pw = seed._read(seed.ENV_LOCAL)["DEV_TEST_PASSWORD"]
    seed.admin_user(EMAIL, pw)
    tok, uid = seed.token(EMAIL, pw)
    repo = PgRepo(config.DATABASE_URL)
    seed.wipe(repo, uid)
    seed.agree(repo, uid)
    app_main.app.dependency_overrides[get_repo] = lambda: repo
    c = TestClient(app_main.app)
    sent = []   # Solar(대화 · 정리 · 판정 · 임베딩)로 실제 나간 글(시스템 말 빼고) — 실명이 나갔는지 본다
    chat_create, embed_create = llm.client().chat.completions.create, llm.client().embeddings.create
    llm.client().chat.completions.create = lambda **kw: (sent.append(json.dumps(
        [m["content"] for m in kw["messages"] if m["role"] != "system"], ensure_ascii=False)), chat_create(**kw))[1]
    llm.client().embeddings.create = lambda **kw: (sent.append(json.dumps(kw["input"], ensure_ascii=False)), embed_create(**kw))[1]
    h = {"Authorization": f"Bearer {tok}"}
    log = config.LOG_DIR / f"agent_flow_{datetime.now():%Y%m%d}.log"
    log_start = log.stat().st_size if log.exists() else 0
    t_start = datetime.now().astimezone()
    row = {"turns": []}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        shorts, long_wav = voices(tmp)
        row["files"] = [{"name": p.name, "bytes": p.stat().st_size} for p in shorts + [long_wav]]
        try:
            conv = c.post("/talk", headers=h).json()
            row["opening"] = conv["turns"][0]["text"]
            said = []
            for p in shorts:
                r = c.post("/voice/transcribe", headers={**h, "Content-Type": "audio/mp4"}, content=p.read_bytes())
                said.append((r.json()["text"], r.json()["seconds"], 1))
            big = long_wav.read_bytes()
            row["whole_long"] = {"bytes": len(big), "status": c.post("/voice/transcribe", headers={**h, "Content-Type": "audio/wav"},
                                                                      content=big).status_code}
            parts = pieces(long_wav, tmp)
            row["pieces"] = [len(b) for b in parts]
            got = [c.post("/voice/transcribe", headers={**h, "Content-Type": "audio/wav"}, content=b).json() for b in parts]
            said.append((" ".join(g["text"] for g in got), sum(g["seconds"] for g in got), len(parts)))
            for (text, sec, n), src in zip(said, SHORT + [LONG]):
                ev = events(c.post(f"/talk/{conv['id']}/turn/stream", headers=h, json={"text": text, "via": "voice"}).text)
                kind, data = ev[-1]
                t = {"source": src, "heard": text, "seconds": sec, "pieces": n, "similar": similar(src, text)}
                if kind == "turn":
                    t.update(via=data["turns"][-2].get("via"), reply=data["turns"][-1]["text"], kind=data["turns"][-1]["kind"],
                             summary=data["summary"])
                else:
                    t["error"] = data.get("code")
                row["turns"].append(t)
                print(json.dumps({k: v for k, v in t.items() if k not in ("source", "heard")}, ensure_ascii=False)[:300], flush=True)
            last = row["turns"][-1].get("reply") or ""
            r = c.post("/voice/speak", headers=h, json={"text": last})
            mp3 = tmp / "reply.mp3"
            mp3.write_bytes(r.content)
            info = subprocess.run(["afinfo", str(mp3)], capture_output=True, text=True).stdout if r.status_code == 200 else ""
            row["speak"] = {"status": r.status_code, "type": r.headers.get("content-type"), "bytes": len(r.content), "chars": len(last),
                            "duration": next((x.split(":")[1].strip() for x in info.splitlines() if "duration" in x), "")}
            ev = events(c.post(f"/talk/{conv['id']}/finish/stream", headers=h).text)
            kind, draft = ev[-1]
            row["draft_status"] = draft.get("status") if kind == "result" else f"error {draft.get('code')}"
            if kind == "result":
                row["draft"] = {"source": draft.get("source"), "summary": draft["info"]["summary"],
                                "thoughts": [(t["kind"], t["quote"]) for t in draft["thoughts"]]}
                done = c.post(f"/diary/{draft['id']}/confirm", headers=h,
                              json={"agreed": ["summary", *[t["id"] for t in draft["thoughts"]]]}).json()
                row["confirm"] = {"confirmed": done.get("confirmed"), "message": (done.get("message") or {}).get("text")}
                row["talk_deleted"] = c.get(f"/talk/{conv['id']}", headers=h).status_code == 404
            audio = [p.read_bytes() for p in shorts] + parts
        finally:
            app_main.app.dependency_overrides.clear()
            llm.client().chat.completions.create, llm.client().embeddings.create = chat_create, embed_create
    row["leaked"] = sorted({n for n in NAMES if any(n in x for x in sent)})
    row["solar_requests"] = len(sent)
    spent, calls = cost(uid, t_start)
    checks = verify(uid, row, audio, log, log_start)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "ws": "WS21",
                            "what": "로컬 e2e 말로 이야기하기(가상 음성 say -v Yuna: 짧은 m4a 2 + 3분 WAV 조각 받아쓰기, 읽어 주기 1) → "
                                    "요약 확인 → 저장(ElevenLabs STT · TTS + Solar + Studio 2판, 골든셋 인물 서강)",
                            "calls": calls, "est_usd": round(spent, 4)}, ensure_ascii=False) + "\n")
    print(f"원장 합계(후): ${ledger_total():.3f} (이번 ${spent:.3f}, 호출 {calls}번)")
    write_doc(row, checks, spent, calls)


def verify(uid, row, audio, log, log_start):
    out = {}
    t = row["turns"]
    out["받아쓴 말 3개가 모두 대화 턴(via=voice)"] = len(t) == 3 and all(x.get("via") == "voice" and x.get("reply") for x in t)
    out["4.5MB 넘는 3분 녹음: 통째로는 413, 2분 조각으로 끝까지 받아씀"] = (
        row["whole_long"]["bytes"] > 4.5 * 1024 * 1024 and row["whole_long"]["status"] == 413 and len(row["pieces"]) >= 2
        and all(b < config.VOICE_MAX_BYTES for b in row["pieces"]) and t[-1]["seconds"] >= 170)
    out["받아쓰기가 원문과 비슷함(글자 일치율 0.8 이상)"] = all(x["similar"] >= 0.8 for x in t)
    out["긴 이야기는 바로 '지금까지 정리'에"] = bool(t[-1].get("summary")) and not t[0].get("summary")
    from app.service import chat
    canned = {x for v in (*chat.SAFE.values(), *chat.HEAVY_SAFE.values()) for x in v}
    # '…있는지 궁금해요.'처럼 물음표 없이 묻는 답도 있어 물음표는 보지 않는다. 두 번(긴 이야기는 세 번) 다 걸리면 기본 문장이 된다.
    out["별지기가 긴 이야기를 들고 이어 물음(기본 문장 아님)"] = t[-1].get("kind") == "reply" and t[-1].get("reply") not in canned
    out["읽어 주기: mp3 를 받음"] = row["speak"]["status"] == 200 and row["speak"]["type"] == "audio/mpeg" and row["speak"]["bytes"] > 1000
    out["정리하기는 save 앞에서 멈춤(source 대화)"] = row.get("draft_status") == "confirm" and row["draft"]["source"] == "대화"
    out["확인 뒤 저장(확인됨) · 대화 턴 지움"] = (row.get("confirm") or {}).get("confirmed") == "확인됨" and row.get("talk_deleted")
    with psycopg.connect(config.DATABASE_URL) as c:
        blobs = [bytes(x) for t_ in ("entries", "thoughts", "people", "messages", "feedback", "conversations")
                 for (x,) in c.execute(f"select enc from {t_} where user_id = %s and enc is not null", [uid]).fetchall()]
        stt = c.execute("select meta, est_usd from runs where user_id = %s and step = 'stt' and error_code is null", [uid]).fetchall()
        tts = c.execute("select meta, est_usd from runs where user_id = %s and step = 'tts'", [uid]).fetchall()
        raw = []   # 로컬 DB 의 모든 bytea 칸(모든 표 · 모든 행)
        for tb, cols in c.execute("select table_schema || '.' || table_name, string_agg(column_name, ', ') from information_schema.columns"
                                  " where table_schema in ('public', 'storage') and data_type = 'bytea' group by 1").fetchall():
            raw += [bytes(v) for r in c.execute(f"select {cols} from {tb}").fetchall() for v in r if v]
    snippets = [a[len(a) // 2:len(a) // 2 + 256] for a in audio]
    out["서버 저장 녹음 0건(모든 bytea 칸에 녹음 조각 없음)"] = not any(s in b for s in snippets for b in raw + blobs)
    out[f"원장(runs): 받아쓰기 {len(stt)}번 · 분당 비용 · 읽어 주기 {len(tts)}번 · 글자당 비용"] = (
        len(stt) == 2 + len(row["pieces"]) and all(set(m) == {"seconds", "bytes", "format"} and float(u) > 0 for m, u in stt)
        and len(tts) == 1 and set(tts[0][0]) == {"chars"})
    frags = [s.strip() for x in SHORT + [LONG] for s in x.split(".") if len(s.strip()) >= 8] + list(NAMES)
    out["DB 에 원문 조각 0개(암호문만)"] = bool(blobs) and not any(f.encode() in b for b in blobs for f in frags)
    text = log.read_text(encoding="utf-8")[log_start:] if log.exists() else ""
    out["실행 기록에 원문 · 이름 없음"] = bool(text) and not any(f in text for f in frags)
    guards = [json.loads(x) for x in text.splitlines() if '"event": "guard"' in x]
    out[f"외부 AI 요청 직전 실명 검사 {sum(g.get('ok') is True for g in guards)}번 통과 · 막힘 0번"] = bool(guards) and all(g.get("ok") for g in guards)
    out[f"Solar 로 나간 글 {row['solar_requests']}건에 실명 0건" + (f" (나간 이름: {', '.join(row['leaked'])})" if row["leaked"] else "")] = \
        not row["leaked"]
    return out


def write_doc(row, checks, spent, calls):
    t = row["turns"]
    L = ["# WS21 로컬 e2e 결과 — 말로 이야기하기", "",
         f"실행 {datetime.now():%Y-%m-%d %H:%M} · `uv run --frozen python scripts/e2e_voice.py` · 시험 전용 계정 {EMAIL}(로컬 Supabase · ChromaDB).",
         "골든셋 가상 인물 '서강'(p_office: 식품 회사 마케터, 팀장 고민석 · 입사 동기 보람)의 지어낸 말을 macOS `say -v Yuna` 로 읽힌 "
         "가상 음성으로 실제 ElevenLabs 받아쓰기(Scribe v2) · 읽어 주기 · Solar · Studio 2판에 돌렸다. 모두 지어낸 글이라 받아쓴 글 · 별지기 "
         "답을 그대로 적는다. 음성 파일은 임시 폴더에서 만들고 끝나면 지웠다.", "",
         "## 음성 파일", ""]
    L += [f"- {f['name']}: {f['bytes']:,} 바이트" for f in row["files"]]
    L += [f"- 3분 WAV 통째로 보내기: HTTP {row['whole_long']['status']} (Vercel 본문 한도 4.5MB 넘음) → 2분 조각 {len(row['pieces'])}개 "
          f"({', '.join(f'{b:,}' for b in row['pieces'])} 바이트)", "", "## 대화", "", f"- 첫 말: {row['opening']}"]
    for x in t:
        L += [f"- 나(말, {x['seconds']:.1f}초 · 조각 {x['pieces']}개 · 원문과 글자 일치율 {x['similar']}): {x['heard']}",
              f"  - 별지기(`{x.get('kind', '오류')}`): " + (x.get("reply") or x.get("error", "")).replace("\n", " / ")]
    L += [f"- 지금까지 정리(긴 이야기 뒤): {t[-1].get('summary', '')}",
          f"- 읽어 주기(마지막 답 {row['speak']['chars']}자): HTTP {row['speak']['status']} · {row['speak']['type']} · "
          f"{row['speak']['bytes']:,} 바이트 · {row['speak']['duration']}"]
    d = row.get("draft") or {}
    L += [f"- 정리하기: `{row.get('draft_status')}` · source {d.get('source')} · 요약 \"{d.get('summary', '')}\" · 생각 {len(d.get('thoughts', []))}개("
          + ", ".join(f"{k} \"{' '.join(q.split())}\"" for k, q in d.get("thoughts", [])) + ")",
          f"- 요약 확인(모두 맞아요): {(row.get('confirm') or {}).get('confirmed')} · 대화 턴 지움: {'예' if row.get('talk_deleted') else '아니오'}",
          f"- 저장 뒤 한마디: {(row.get('confirm') or {}).get('message')}", "", "## 확인", "", "| 확인 | 결과 |", "| --- | --- |"]
    L += [f"| {k} | {'통과' if v else '실패'} |" for k, v in checks.items()]
    L += ["", f"비용: 외부 호출 {calls}번, 추정 ${spent:.3f}(runs 표 합계, 원장 `runs/cost_ledger.jsonl` WS21 줄).", ""]
    (ROOT / "docs" / "ws21-e2e.md").write_text("\n".join(L), encoding="utf-8")
    print("docs/ws21-e2e.md 를 썼어요.", json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"{time.time() - t0:.0f}초")
