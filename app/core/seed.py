"""
app/core/seed.py — 로컬 개발 준비(로컬 Supabase · ChromaDB 전용). 키 · 비밀번호는 파일에만 쓰고 출력하지 않는다.

    uv run --frozen python -m app.core.seed env        # .env.local · infra/frontend/.env.local 만들기(새 암호화 키면 DB 초기화)
    uv run --frozen python -m app.core.seed accounts   # 시험용 계정(tester@ · e2e@my-universe.test) 만들기 · 비밀번호 맞추기
    uv run --frozen python -m app.core.seed demo       # tester@ 의 우주를 가상 인물 하늘의 정리된 데이터로 채우기(유료 호출 없음)

이 파일은 로컬 Supabase(127.0.0.1)가 아니면 계정 · 데모를 만들지 않는다.
"""

import json
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_LOCAL = ROOT / ".env.local"
FRONT_ENV = ROOT / "infra" / "frontend" / ".env.local"
ACCOUNTS = {"tester": "tester@my-universe.test", "e2e": "e2e@my-universe.test"}
DEMO = ROOT / "data" / "demo" / "universe-haneul.json"
DEMO_PEOPLE = {"민수": "선배", "지은": "동생"}   # 하늘의 사람(가상)


def _read(path):
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def _write(path, values, note):
    path.write_text(f"# {note}\n" + "".join(f"{k}={v}\n" for k, v in values.items()))
    path.chmod(0o600)


def supabase_status():
    r = subprocess.run(["supabase", "status", "-o", "env"], cwd=ROOT, capture_output=True, text=True, check=True)
    return {k: v.strip('"') for k, v in (line.split("=", 1) for line in r.stdout.splitlines() if "=" in line)}


def env():
    st = supabase_status()
    old = _read(ENV_LOCAL)
    from app.core.security import new_master_key
    fresh = "DIARY_ENC_KEY" not in old
    values = {
        "SUPABASE_URL": st["API_URL"], "SUPABASE_ANON_KEY": st["ANON_KEY"], "DATABASE_URL": st["DB_URL"],
        "SUPABASE_SERVICE_ROLE_KEY": st["SERVICE_ROLE_KEY"],          # 로컬 계정 만들기 · 시험용, 백엔드는 DELETE /me 에서만 씀
        "DIARY_ENC_KEY": old.get("DIARY_ENC_KEY") or new_master_key(),
        "CHROMA_HOST": "localhost", "CHROMA_PORT": "8000", "FRONTEND_ORIGIN": "http://localhost:3000", "LOG_TO_FILE": "1",
        "API_DOCS": "1",                                              # /docs 는 로컬만
        "DEV_TEST_PASSWORD": old.get("DEV_TEST_PASSWORD") or secrets.token_urlsafe(18),
    }
    _write(ENV_LOCAL, values, "로컬 전용(scripts/dev_up.sh 가 만듦, 커밋 금지). 로컬 Supabase 데모 키 · 시험용 비밀번호.")
    _write(FRONT_ENV, {"NEXT_PUBLIC_API_BASE": "http://localhost:8001", "NEXT_PUBLIC_SUPABASE_URL": st["API_URL"],
                       "NEXT_PUBLIC_SUPABASE_ANON_KEY": st["ANON_KEY"], "NEXT_PUBLIC_DEV_LOGIN": "1", "NEXT_PUBLIC_MOCK": "0"},
           "로컬 전용(scripts/dev_up.sh 가 만듦, 커밋 금지).")
    if fresh:   # 새 암호화 키로는 예전 암호문을 못 푼다 → 로컬 DB 를 비우고 시작
        print("새 암호화 키를 만들었어요. 로컬 DB 를 초기화합니다(supabase db reset).")
        subprocess.run(["supabase", "db", "reset", "--local"], cwd=ROOT, check=True, capture_output=True)
        try:
            import chromadb
            chromadb.HttpClient(host="localhost", port=8000).delete_collection("thoughts")
        except Exception:   # 컬렉션이 아직 없음
            pass
    print(".env.local · infra/frontend/.env.local 을 만들었어요(값은 출력하지 않음).")


def _local(url):
    if not url.startswith(("http://127.0.0.1", "http://localhost")):
        sys.exit("로컬 Supabase 가 아니라서 멈춥니다.")


def admin_user(email, password):
    """로컬 Supabase 에 계정을 만들거나 비밀번호를 맞춘다 → user id."""
    import httpx
    from app.core import config
    _local(config.SUPABASE_URL)
    key = _read(ENV_LOCAL)["SUPABASE_SERVICE_ROLE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    base = f"{config.SUPABASE_URL}/auth/v1/admin/users"
    r = httpx.post(base, headers=h, json={"email": email, "password": password, "email_confirm": True}, timeout=10)
    if r.status_code in (200, 201):
        return r.json()["id"]
    users = httpx.get(base, headers=h, params={"per_page": 1000}, timeout=10).json()["users"]
    uid = next(u["id"] for u in users if u["email"] == email)
    httpx.put(f"{base}/{uid}", headers=h, json={"password": password}, timeout=10).raise_for_status()
    return uid


def token(email, password=None):
    """시험용 계정의 access token(로컬 전용)."""
    import httpx
    from app.core import config
    _local(config.SUPABASE_URL)
    r = httpx.post(f"{config.SUPABASE_URL}/auth/v1/token", params={"grant_type": "password"}, timeout=10,
                   headers={"apikey": config.SUPABASE_ANON_KEY},
                   json={"email": email, "password": password or _read(ENV_LOCAL)["DEV_TEST_PASSWORD"]})
    r.raise_for_status()
    return r.json()["access_token"], r.json()["user"]["id"]


def agree(repo, uid):
    """시험용 계정은 지금 판 동의를 이미 한 상태로 둔다(동의 화면 시험은 새 계정 · 가짜 데이터 모드로)."""
    from app.api import consent
    with repo.session(uid) as s:
        if consent.needed(s):
            consent.save(s)


def accounts():
    from app.core import config
    from app.repository import PgRepo
    pw = _read(ENV_LOCAL)["DEV_TEST_PASSWORD"]
    repo = PgRepo(config.DATABASE_URL)
    for email in ACCOUNTS.values():
        agree(repo, admin_user(email, pw))
    print(f"시험용 계정 {len(ACCOUNTS)}개 준비(비밀번호는 .env.local 의 DEV_TEST_PASSWORD, 지금 판 동의 포함).")


def wipe(repo, uid):
    from app.repository import diary
    with repo.session(uid) as s:
        diary.wipe(s)
    repo.vectors.delete(uid)


def demo(repo, uid):
    """가상 인물 하늘의 이미 정리된 기록 29편(v7 결과 + 저장된 벡터)을 v8 규칙으로 옮겨 넣는다. 외부 호출 없음."""
    from app.repository import diary
    from app.service.rules import advance, clean_record, filter_relations
    d = json.loads(DEMO.read_text(encoding="utf-8"))
    wipe(repo, uid)
    agree(repo, uid)
    vecs, ids, ts, states = [], {}, {}, {}
    with repo.session(uid) as s:
        people = [diary.add_person(s, n, relation=r) for n, r in DEMO_PEOPLE.items()]
        stars = {}
        for rid in d["order"]:
            r, rep = d["records"][rid], d["reports"][rid]
            eid = diary.new_id("e")
            written = diary.parse_dt(r["written_at"])
            diary.create_entry(s, eid, written, None, r["title"], r["body"])
            t7 = [d["thoughts"][i] for i in r.get("thought_ids") or []]
            raw = {"summary": rep.get("summary", ""), "addressee": "나", "events": [],
                   "thoughts": [{**t, "people": [p["name"] for p in people if p["name"] in t["thought"] + t["quote"]]} for t in t7]}
            rec = clean_record(raw, people, {n: sun for n, (_, sun) in stars.items()})
            today = []
            for i, (a, t) in enumerate(zip(t7, rec["thoughts"])):
                sun = t["domain"] or d["hubs"].get(a.get("hub"), {}).get("name") or "삶의 성취"
                sun_id = diary.ensure_sun(s, sun)
                if t["topic"] not in stars:
                    stars[t["topic"]] = (diary.new_id("s"), sun)
                    diary.add_star(s, stars[t["topic"]][0], t["topic"], sun_id)
                tid = ids[a["id"]] = diary.thought_id(eid, i)
                row = {**t, "id": tid, "record_id": eid, "day": r["day"], "position": i, "star_id": stars[t["topic"]][0],
                       "sun_id": sun_id, "domain": sun,
                       "people": [p["id"] for p in people if p["name"] in t["people"]]}
                ts[tid] = row
                today.append(row)
                vecs.append({"id": tid, "emb": a["emb"], "entry_id": eid, "star_id": row["star_id"],
                             "written_at": diary.iso(written), "kind": t["kind"]})
            for p in people:   # 생각 글에는 없고 본문에만 나온 사람도 그 행성에 잇는다(첫 생각에)
                if today and p["name"] in f"{r['title']}\n{r['body']}" and not any(p["id"] in x["people"] for x in today):
                    today[0]["people"].append(p["id"])
            for row in today:
                diary.save_thought(s, eid, row)
            cands = [{"a": ids.get(x["from"]), "b": ids.get(x["to"]), "type": x["type"], "explanation": x.get("explanation", ""),
                      "axis": x.get("axis", ""), "topic": x.get("topic", ""), "quoted": True}
                     for x in d["relations"] if x["to_record"] == rid]
            kept, _ = filter_relations([c for c in cands if c["a"] and c["b"]], ts, states)
            for k in kept:
                diary.save_relation(s, k)
            states = advance(states, ts, kept, eid)
            star = today[0]["star_id"] if today else None
            s.update("entries", {"status": "done", "step": "save", "addressee": "나", "star_id": star,
                                 "sun_id": today[0]["sun_id"] if today else None,
                                 "enc": diary.seal(s, "entries", eid, {"title": r["title"], "text": r["body"],
                                                                      "summary": rep.get("summary", ""), "events": [],
                                                                      "past": []})}, id=eid)
        diary.save_states(s, states, {})
        diary.add_aspiration(s, "", "어디서든 배우며, 한 약속은 지키는 사람", "바쁘면 미룬다",
                             "바쁘다는 생각이 들면 10분만 먼저 하겠다", ["성취", "규범"])
        diary.save_profile(s, onboarding={"aspiration": "set", "weather_asked": True})
    repo.vectors.upsert(uid, vecs)
    return len(d["order"])


def main(cmd):
    if cmd == "env":
        return env()
    from app.core import config
    from app.repository import PgRepo
    if cmd == "accounts":
        return accounts()
    if cmd == "demo":
        _local(config.SUPABASE_URL)
        _, uid = token(ACCOUNTS["tester"])
        n = demo(PgRepo(config.DATABASE_URL), uid)
        print(f"tester@ 의 우주에 하늘의 기록 {n}편을 넣었어요.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "env")
