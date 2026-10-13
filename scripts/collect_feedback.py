"""
scripts/collect_feedback.py — 주 1회 오답 모으기(운영자만, PRD §8.7 '모아서 개선' · 결정 10, WS22).

운영 DB 를 직접 읽지 않고 백엔드 API `GET /ops/feedback?wrong=true` 로 받는다: 운영자 열람에 동의한 사용자의
'아니에요' · '별로' · '불편한 점 한 줄'과 그 대상 문장(다른 사람 이름은 가명). 받을 때마다 서버에 열람 기록(ops_reads)이 남는다.
동의하지 않은 사용자 것은 숫자로만 온다. 결과는 runs/wrong/YYYY-MM-DD.jsonl(git 에 올리지 않음) — 평가 세트 후보로 사람이 고른다.

    OPS_TOKEN=<운영 화면 '스크립트용 토큰 복사'> uv run --frozen python scripts/collect_feedback.py --api https://my-universe-api.vercel.app
    uv run --frozen python scripts/collect_feedback.py --local     # 로컬 서버(8001) + 시험 계정 tester@(백엔드 ADMIN_EMAILS 에 넣어 띄움)

토큰은 화면에 찍지 않는다.
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def collect(get, days=7):
    """get(경로) → 응답(httpx 모양). 운영자가 아니면 raise_for_status 가 예외(403)."""
    r = get(f"/ops/feedback?wrong=true&days={days}")
    r.raise_for_status()
    return r.json()


def write(data, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{date.today().isoformat()}.jsonl"
    lines = [json.dumps(x, ensure_ascii=False) for x in data["items"]]
    out.write_text("".join(f"{x}\n" for x in lines), encoding="utf-8")
    return out, len(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="오답 모으기(운영자만)")
    p.add_argument("--api", default="http://localhost:8001")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--out", default=str(ROOT / "runs" / "wrong"))
    p.add_argument("--local", action="store_true", help="로컬 시험 계정 tester@ 토큰을 씀(로컬 Supabase 만)")
    a = p.parse_args(argv)
    token = os.environ.get("OPS_TOKEN", "")
    if not token and a.local:
        sys.path.insert(0, str(ROOT))
        from app.core import seed
        token = seed.token(seed.ACCOUNTS["tester"])[0]
    if not token:
        print("OPS_TOKEN(운영자 로그인 토큰)이 필요해요. 운영 화면의 '스크립트용 토큰 복사'를 쓰세요.", file=sys.stderr)
        return 2
    with httpx.Client(base_url=a.api, headers={"Authorization": f"Bearer {token}"}, timeout=120) as c:
        data = collect(c.get, a.days)
    out, n = write(data, a.out)
    print(f"오답 재료 {n}건 → {out} (동의한 사용자 {data['users']}명 · 동의 안 한 사용자 것은 숫자만: {data['not_consented']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
