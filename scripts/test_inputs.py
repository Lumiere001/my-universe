"""
입력 4종 시험(1차 tools/test_inputs.py 의 새 판, 2차 가이드 '서로 다른 입력 4종'): 인스타 ZIP · MD · TXT · 직접 쓰기를
v8 백엔드 API 로 끝까지 돌린다. 글은 모두 가상 인물 도담(골든셋 p_student)의 지어낸 글이다.

    uv run --frozen python scripts/test_inputs.py                       # 로컬(:8001), 시험용 계정 e2e@ (로컬 Supabase)
    uv run --frozen python scripts/test_inputs.py --zip 2 --only zip    # ZIP 최근 2편만(유료 상한을 지킬 때)
    MY_UNIVERSE_TOKEN=… uv run --frozen python scripts/test_inputs.py --base https://<미리보기 백엔드>   # 미리보기 배포(가상 계정 토큰)

ZIP 은 화면(/import)과 같은 순서로 보낸다: 게시물 → POST /import/instagram/preview → 아직 안 가져온 최근 N편을 오래된 것부터
/diary/stream(source='지난 글 묶음', source_ref, written_at = 게시 시각). 같은 ZIP 을 한 번 더 보내 새 기록이 0편인지 본다.
유료: 서버가 실제 Studio · Solar 를 부르면 편당 약 $0.15. 끝나면 /stats 의 이달 추정 비용 차이를 runs/cost_ledger.jsonl 에 남긴다
(가짜 Upstage 서버 scripts/dev_fake_upstage.py 에 돌릴 때는 --no-ledger). 만든 기록은 끝나면 지운다(--keep 이면 남김).
결과(원문 없음)는 docs/ws17-inputs.md.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.service import importer  # noqa: E402
from tests.fixtures import instagram_virtual  # noqa: E402

LEDGER = Path("/Users/east_star/Projects/my-universe/runs/cost_ledger.jsonl")
SOURCE = importer.SOURCE
MD = ("2026-04-02-독서노트.md", "# 4/2 독서노트\n\n## 읽은 것\n『작은 습관의 힘』에서 습관은 의지가 아니라 환경에서 시작된다는 장을 읽었다.\n"
      "## 해 볼 것\n내일부터 책상 위에 전공책을 펴 두고 자겠다.")
TXT = ("2026-04-03-일기.txt", "4/3 금요일\n윤재랑 학교 앞에서 저녁을 먹었다. 요즘 말이 없던 이유를 처음으로 들었다.\n"
       "먼저 물어보길 잘했다. 다음엔 내가 먼저 고민을 꺼내 봐야겠다.")
DIRECT = ("4/4 토요일", "오늘은 아침에 휴대폰을 침대 밖에 두고 잤더니 일찍 일어났다. 의지보다 환경이 먼저라는 말이 맞는 것 같다.\n"
          "이번 주는 이 습관을 지켜 보자.")


def sse(r):
    """→ [(사건, 값)]. 200 이 아니면 오류 본문을 error 사건 하나로."""
    if r.status_code != 200:
        err = (r.json() or {}).get("error", {})
        return [("error", {"entry_id": None, "code": err.get("code", f"http_{r.status_code}"), "message": err.get("message", ""),
                           "resumable": False})]
    out = []
    for block in r.text.split("\n\n"):
        lines = dict(x.split(": ", 1) for x in block.split("\n") if x and not x.startswith(":") and ": " in x)
        if "event" in lines:
            out.append((lines["event"], json.loads(lines["data"])))
    return out


def send(client, body):
    """기록 하나 → (사건, 값). 멈춘 같은 원본(duplicate, 이어 하기 가능)이면 한 번 이어 한다(화면과 같음)."""
    kind, data = sse(client.post("/diary/stream", json=body))[-1]
    if kind == "error" and data.get("resumable") and data.get("entry_id"):
        kind, data = sse(client.post(f"/diary/{data['entry_id']}/resume/stream"))[-1]
    return kind, data


def trim(posts):
    """화면이 ZIP 에서 꺼내 보내는 모양: 캡션 · 시각만(사진 주소 등은 보내지 않음)."""
    out = []
    for p in posts:
        m = (p.get("media") or [{}])[0]
        out.append({"title": p.get("title", ""), "creation_timestamp": p.get("creation_timestamp"),
                    "media": [{"title": m.get("title", ""), "creation_timestamp": m.get("creation_timestamp")}]})
    return out


def preview(client, data):
    r = client.post("/import/instagram/preview", json={"posts": trim(importer.posts_from_zip(data))})
    r.raise_for_status()
    return r.json()


def body(p):
    return {"title": p["title"], "text": p["text"], "written_at": p["written_at"], "source": SOURCE, "source_ref": p["ref"]}


def import_zip(client, data, n=None):
    """→ (미리 보기, [(게시물, 사건, 값)]). 아직 안 가져온 최근 n편(None = 전부, IMPORT_MAX_POSTS 가 있으면 그 안)을 오래된 것부터."""
    pv = preview(client, data)
    new = [p for p in pv["posts"] if not p["imported"] and not p["too_long"]]
    cap = min([len(new)] + [x for x in (n, pv["max_posts"]) if x])
    return pv, [(p, *send(client, body(p))) for p in reversed(new[:cap])]


def read_file(name, raw):
    """쓰기 화면 파일 불러오기와 같은 규칙: 짧은 첫 줄 · # 줄은 제목, 파일 이름 속 날짜는 글이 다루는 날."""
    lines = raw.strip().splitlines()
    titled = len(lines) > 1 and (lines[0].startswith("#") or len(lines[0].strip()) <= 40)
    m = re.search(r"\d{4}-\d{2}-\d{2}", name)
    return {"title": re.sub(r"^#+\s*", "", lines[0]).strip() if titled else "",
            "text": "\n".join(re.sub(r"^#+\s+", "", x) for x in (lines[1:] if titled else lines)).strip(),
            **({"day": m[0]} if m else {})}


def row(kind, data, inp, extra=None):
    ok = kind == "result"
    return {"input": inp, "event": kind, "entry_id": data.get("id") or data.get("entry_id"), "code": None if ok else data.get("code"),
            "duplicate": bool(data.get("duplicate")), "source": data.get("source"), "day": data.get("day"),
            "day_basis": data.get("day_basis"), "written_at": (data.get("written_at") or "")[:16],
            "thoughts": len(data.get("thoughts") or []), "relations": len(data.get("relations") or []),
            "message": bool(data.get("message")), **(extra or {})}


def run(client, n_zip=None, only=None):
    """→ (줄들, 확인). client 는 base_url · 로그인 머리말이 붙은 httpx.Client(시험에서는 TestClient)."""
    rows, checks = [], {}
    ids = lambda: {e["id"] for e in client.get("/diary?limit=100").json()["entries"]}  # noqa: E731
    zip_bytes = instagram_virtual.zip_bytes()
    if only in (None, "zip"):
        before = ids()
        pv, sent = import_zip(client, zip_bytes, n_zip)
        rows += [row(k, d, "인스타 ZIP", {"parts": p["parts"]}) for p, k, d in sent]
        made = ids() - before
        pool = sum(1 for p in pv["posts"] if not p["imported"] and not p["too_long"])
        want = min([pool] + [x for x in (n_zip, pv["max_posts"]) if x])
        checks[f"ZIP: 글 {len(pv['posts'])}편을 찾고, 고른 {want}편만 기록이 됨"] = len(made) == want == len(sent)
        checks["ZIP: 출처 '지난 글 묶음' · 쓴 시각 = 게시 시각"] = all(
            r["source"] == SOURCE and r["written_at"] == p["written_at"][:16] for r, (p, _, _) in zip(rows, sent))
        again = [send(client, body(p)) for p, _, _ in sent]   # 같은 원본을 한 번 더
        checks["같은 ZIP 두 번: 새 기록 0편(이미 있던 글로 안내)"] = ids() - before == made and all(
            k == "result" and d.get("duplicate") for k, d in again)
        checks["다시 미리 보기: 가져온 글만 '이미 가져옴'"] = {p["ref"] for p in preview(client, zip_bytes)["posts"] if p["imported"]} == \
            {p["ref"] for p, _, _ in sent}
    if only in (None, "files"):
        for inp, (name, raw) in (("MD 파일", MD), ("TXT 파일", TXT)):
            b = {**read_file(name, raw), "source": "텍스트", "source_ref": f"파일:{name}:{len(raw.encode())}:0"}
            rows.append(row(*send(client, b), inp))
        rows.append(row(*send(client, {"title": DIRECT[0], "text": DIRECT[1]}), "직접 쓰기"))
    checks["모든 입력이 끝까지(result)"] = bool(rows) and all(r["event"] == "result" for r in rows)
    return rows, checks


def write_doc(rows, checks, base, spent, fake=False):
    L = ["# WS17 입력 4종 시험 결과", "",
         f"실행 {datetime.now():%Y-%m-%d %H:%M} · `uv run --frozen python scripts/test_inputs.py` · 서버 {base}"
         f"{'(가짜 Upstage, 정리 결과는 가짜 · 유료 호출 0)' if fake else '(실제 Studio · Solar)'} · "
         "가상 인물 도담(골든셋 p_student)의 지어낸 글. 이 문서에는 원문을 넣지 않는다.", "",
         "| 입력 | 결과 | 출처 | 글이 다루는 날 | 쓴 시각 | 묶은 게시물 | 생각 | 관계 | 한마디 |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    L += [f"| {r['input']} | {r['event'] if r['event'] == 'result' else '오류 `' + str(r['code']) + '`'}{' (이미 있던 글)' if r['duplicate'] else ''} | "
          f"{r['source']} | {r['day']} ({r['day_basis']}) | {r['written_at']} | {r.get('parts', '')} | {r['thoughts']} | {r['relations']} | "
          f"{'있음' if r['message'] else '-'} |" for r in rows]
    L += ["", "| 확인 | 결과 |", "| --- | --- |", *[f"| {k} | {'통과' if v else '실패'} |" for k, v in checks.items()], "",
          f"비용: /stats 이달 추정 비용 차이 ${spent:.3f}.", ""]
    (ROOT / "docs" / "ws17-inputs.md").write_text("\n".join(L), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8001")
    ap.add_argument("--zip", type=int, default=None, help="ZIP 에서 가져올 최근 글 수(비우면 전부)")
    ap.add_argument("--only", choices=["zip", "files"])
    ap.add_argument("--keep", action="store_true", help="만든 기록을 지우지 않음")
    ap.add_argument("--no-ledger", action="store_true", help="가짜 Upstage 서버일 때")
    a = ap.parse_args()
    token = os.getenv("MY_UNIVERSE_TOKEN")
    if not token:
        from app.core import seed
        token, _ = seed.token(seed.ACCOUNTS["e2e"])   # 로컬 Supabase 시험용 계정
    with httpx.Client(base_url=a.base, headers={"Authorization": f"Bearer {token}"}, timeout=httpx.Timeout(30, read=120)) as c:
        start = set(e["id"] for e in c.get("/diary?limit=100").json()["entries"])
        cost0 = c.get("/stats").json()["month_cost_usd"]
        try:
            rows, checks = run(c, a.zip, a.only)
        finally:
            spent = c.get("/stats").json()["month_cost_usd"] - cost0
            if not a.keep:
                for e in c.get("/diary?limit=100").json()["entries"]:
                    if e["id"] not in start:
                        c.delete(f"/diary/{e['id']}")
            if spent > 0 and not a.no_ledger and LEDGER.parent.exists():
                with LEDGER.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "ws": "WS17",
                                        "what": f"입력 4종 시험(가상 인물 도담, {a.base}, zip={a.zip}, only={a.only})",
                                        "calls": None, "est_usd": round(spent, 4)}, ensure_ascii=False) + "\n")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    print(json.dumps(checks, ensure_ascii=False, indent=1))
    write_doc(rows, checks, a.base, spent, fake=a.no_ledger)
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == "__main__":
    main()
