"""
tools/mcp_diary_live.py — MCP 서버(tools/mcp_diary.py)를 실제로 돌려 보기(로컬 전용, 유료 호출 3편분).

로컬 백엔드(기본 http://localhost:8001)에 새 시험 계정을 만들어 동의하고, MCP 클라이언트(stdio)로 서버를 띄워
가상 일기 3편을 import_diaries 로 넣은 뒤 recent_diaries 로 정리가 끝나는지(done) 본다. 같은 3편을 다시 넣어 새 기록이
생기지 않는지도 본다. 끝나면 DELETE /me 로 시험 계정과 그 기록을 모두 지운다. 비밀번호 · 토큰은 출력하지 않는다.

    uv run --with "mcp>=2,<3" python -m tools.mcp_diary_live
"""

import json
import os
import secrets
import time

import anyio
import httpx
from mcp import Client, StdioServerParameters

from app.core import seed

API = os.environ.get("MY_UNIVERSE_API", "http://localhost:8001")
EMAIL = "mcp-test-1107@my-universe.test"
WAIT_S = 900
# 가상 인물 서윤(대학 동아리 회장)의 일기 — 실제 사람 글 아님. 넣는 순서를 섞어 오래된 것부터 정리하는지도 본다
DIARIES = [
    {"date": "2026-10-24", "title": "회의 끝나고",
     "text": "오늘 회의에서 후배들이 먼저 의견을 냈다. 내가 다 정하지 않아도 일이 굴러간다는 게 이상하게 서운하면서도 편했다. "
             "그만두고 싶다는 마음이 조금 줄었다. 내가 지친 건 일이 많아서가 아니라 혼자 짊어진다고 생각해서였나 보다."},
    {"date": "2026-10-20", "title": "회장 그만둘까",
     "text": "동아리 회장을 계속하는 게 맞는지 모르겠다. 공지 하나 올리는 것도 버겁고, 다들 나만 쳐다보는 것 같다. "
             "이번 학기 끝나면 그만둔다고 말할까. 근데 그만두면 도망치는 것 같아서 싫다."},
    {"date": "2026-10-29", "title": "",
     "text": "회장은 학기 끝까지 하기로 했다. 대신 행사 준비는 후배 둘에게 나눠 맡겼다. 도망이 아니라 나누는 거라고 생각하니 마음이 가볍다. "
             "다음 주에는 내가 하고 싶었던 사진 전시 기획을 다시 꺼내 봐야지."},
]


def call(c, name, args):
    async def go():
        r = await c.call_tool(name, args)
        if r.is_error:
            raise RuntimeError(r.content[0].text)
        return json.loads(r.content[0].text)
    return go()


async def run(token):
    env = {"MY_UNIVERSE_TOKEN": token, "MY_UNIVERSE_API": API}
    async with Client(StdioServerParameters(command="uv", args=["run", "--quiet", "tools/mcp_diary.py"], env=env)) as c:
        print("도구:", [t.name for t in (await c.list_tools()).tools])
        print("넣기 전:", (await call(c, "recent_diaries", {"n": 10}))["diaries"])
        t0 = time.monotonic()
        print("import_diaries:", await call(c, "import_diaries", {"entries": DIARIES}))
        seen = {}
        while time.monotonic() - t0 < WAIT_S:
            r = await call(c, "recent_diaries", {"n": 10})
            for d in r["diaries"]:
                if d["status"] != "processing" and d["date"] not in seen:
                    seen[d["date"]] = round(time.monotonic() - t0)
                    print(f"  {seen[d['date']]:>4}초  {d['date']} {d['title'] or '(제목 없음)'} → {d['status']}")
            if r["problems"] or (r["waiting"] == 0 and len(seen) == len(DIARIES)):
                break
            await anyio.sleep(5)
        total = round(time.monotonic() - t0)
        print("끝:", json.dumps(r, ensure_ascii=False))
        again = await call(c, "import_diaries", {"entries": DIARIES})   # 같은 글 다시 → 새 기록 없이 끝나야
        while (r2 := await call(c, "recent_diaries", {"n": 10}))["waiting"]:
            await anyio.sleep(1)
        print("다시 넣기:", again["accepted"], "편 →", len(r2["diaries"]), "편 그대로", r2["problems"] or "")
        return r, total, r2


def main():
    pw = secrets.token_urlsafe(18)
    seed.admin_user(EMAIL, pw)   # 로컬 Supabase 가 아니면 멈춤
    token, _ = seed.token(EMAIL, pw)
    h = {"Authorization": f"Bearer {token}"}
    try:
        v = httpx.get(f"{API}/consent", headers=h).json()["version"]
        httpx.post(f"{API}/consent", headers=h, json={"version": v, "required": True, "sensitive": True, "age14": True}).raise_for_status()
        r, total, r2 = anyio.run(run, token)
        st = httpx.get(f"{API}/stats", headers=h).json()
        ok = all(d["status"] == "done" for d in r["diaries"]) and len(r["diaries"]) == 3 and len(r2["diaries"]) == 3
        print(f"결과: {'통과' if ok else '실패'} · {total}초 · 정리 {st['entries_done']}/{st['entries']}편 · 추정 비용 ${st['month_cost_usd']}")
    finally:
        for _ in range(60):   # 정리 중인 기록이 있으면 409 → 끝날 때까지 기다렸다 지움
            d = httpx.delete(f"{API}/me", headers=h)
            if d.status_code != 409:
                break
            time.sleep(10)
        print("시험 계정 지움:", d.status_code == 204)


if __name__ == "__main__":
    main()
