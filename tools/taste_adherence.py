"""
tools/taste_adherence.py — 취향 고리 지시를 Solar 가 따르는지(유료, 작게). 2026-11-07

가상 인물 G(eval/personas/pG.json) 일기 4편 × 방식 조합 4개(반쪽 배치: 제안 · 지난 기록 · 짧게 각각 켬 8번 · 끔 8번) = 생성 16번.
voice.generate 를 최소 ctx 로 부르고, 나온 한마디를 taste.ways() 로 재서 지시와 맞는지 센다.
uv run python -m tools.taste_adherence [v2]
"""
import json
import re
import sys
from pathlib import Path

from app.core import llm
from app.service import voice
from app.service.voice import taste

V2 = sys.argv[1:] == ["v2"]   # 2판: 방식 지시를 [답 형식] 바로 앞으로 옮기고 말을 구체적으로 한 뒤, 일기 2편 × 4 = 8번만 다시
TODAY, PAST = ((6, 10) if V2 else (6, 8, 10, 11)), (1, 4)
COMBOS = [(True, True, True), (True, False, False), (False, True, False), (False, False, True)]   # (suggest, recall, short)
OUT = Path(f"eval/results/2026-11-07-taste-adherence{'-v2' if V2 else ''}.json")


def first_sentence(body):
    return re.split(r"(?<=[.?!])\s+", body)[0]


def main():
    es = {e["n"]: e for e in json.loads(Path("eval/personas/pG.json").read_text())["entries"]}
    past = [{"thought": es[n]["title"], "quote": first_sentence(es[n]["body"]), "day": es[n]["written_at"][:10]} for n in PAST]
    rows = []
    with llm.guard([]) as m:   # 가상 인물(fictional) 글 — 실명 없음
        for n in TODAY:
            for s, r, sh in COMBOS:
                plan = {"suggest": s, "recall": r, "short": sh}
                ctx = {"tone": "다정하게", "text": es[n]["body"], "summary": es[n]["title"],
                       "written_at": es[n]["written_at"][:10] + "T20:00:00+09:00", "days_written": 8,
                       "past_messages": ["회의 뒤에 메모를 다시 펼쳐 본 마음이 보여요. 적어 둔 문장이 멀쩡하다는 걸 알아챈 것도요."],
                       "past_thoughts": past, "taste": plan}
                out = voice.generate(ctx)
                got = taste.ways(out["message"])
                rows.append({"entry": n, "plan": plan, "got": got, "mode": out["mode"], "len": len(out["message"]),
                             "message": out["message"]})
                print(n, plan, got, out["mode"], len(out["message"]))
        calls, usd = m.calls, m.usd
    adh = {k: {"on": f"{sum(x['got'][k] for x in rows if x['plan'][k])}/{sum(x['plan'][k] for x in rows)}",
               "off": f"{sum(not x['got'][k] for x in rows if not x['plan'][k])}/{sum(not x['plan'][k] for x in rows)}"}
           for k in taste.WAYS}
    print(json.dumps(adh, ensure_ascii=False), f"calls={calls} usd={usd:.3f}")
    OUT.write_text(json.dumps({"date": "2026-11-07", "persona": "pG(가상)", "adherence": adh, "calls": calls,
                               "est_usd": round(usd, 4), "rows": rows}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
