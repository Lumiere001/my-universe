"""
작은 별 묶음(group_rules). 기록 Agent 는 글 한 편만 보고 작은 별 이름을 지어 같은 고민이 장면마다 따로 별이 된다.
새 작은 별이 생긴 글이 끝나면 쌓인 작은 별 전체를 한 번에 보고 같은 고민끼리 묶고(Solar ①), 묶음마다 해를 고른다(Solar ②).
작은 별은 지우지 않고 묶음 머리만 적는다(매번 전체를 새로 묶어 눈덩이가 생기지 않게). 묶기는 관측 전에 돌아,
지난 생각 고르기 · 관측 Agent · 관계 규칙은 묶음 이름으로 '같은 주제'를 본다. 여기는 글 만들기 · 답 읽기 · 적용(네트워크 없음).
2026-10-29 가상 인물 A~D 저장 결과: 작은 별 20~32 → 5~12, 같은 주제 묶임 F1 A 0.70 → 0.81 · B 0.53 → 0.74 · C 0.78 → 0.86 ·
D 0.86 → 0.80~0.83, 해 맞음 A 59 → 89 · B 77 → 94 · C 44 → 100 · D 77 → 97%.
"""

import json
import re

from app.core.ontology import load
from app.service.rules.topics import base, profile

O = load()
EXAMPLES = 2   # 작은 별마다 원문 예 몇 개
CUT = 50       # 예 하나의 글자 수

GROUP_SYSTEM = (
    f"너는 일기 앱에서 '작은 별'을 정리한다. {O['group_rules'][0]}\n"
    "같은 고민 · 목표 · 관계의 부분인 별끼리 묶어라. 다른 고민끼리 억지로 묶지 않는다. 묶음 수는 정해져 있지 않다. "
    "어디에도 안 맞는 별은 혼자 둔다.\n"
    'JSON 만 답한다: {"groups": [[별 번호, ...], ...]} — 모든 별 번호가 정확히 한 번씩 나와야 한다.')


def sun_choices(custom=()):
    """묶음이 고를 해 [(이름, 뜻)]. 두 영역 모드면 커리어 · 인간관계 · 그 밖, 아니면 기준 축 9개. 사용자가 만든 해를 더한다."""
    p = profile()
    if p:
        out = [(s["name"], s["definition"]) for s in p["suns"]] + [(p["other"], p.get("other_definition", ""))]
    else:
        out = [(d["name"], d["definition"]) for d in O["domains"] if d["name"] in base()]
    return out + [(c, "사용자가 만든 해") for c in custom if c not in {n for n, _ in out}]


def sun_system(choices):
    return ("너는 일기 앱에서 생각 묶음이 어느 해(삶의 영역)에 속하는지 고른다. 해: "
            + " / ".join(f"{n}({d})" if d else n for n, d in choices)
            + '.\n묶음마다 하나를 고른다. JSON 만: {"suns": [{"group": 묶음 번호, "sun": "해 이름"}]}')


def group_input(stars):
    """stars: [{name, sun, records, quotes}] → Solar ① 입력."""
    rows = []
    for j, st in enumerate(stars, 1):
        ex = "; ".join(f'"{q[:CUT]}"' for q in st["quotes"][:EXAMPLES] if q)
        rows.append(f"{j}. [{st['sun']}] {st['name']} ({st['records']}편) — 예: {ex}")
    return "작은 별 목록:\n" + "\n".join(rows)


def _json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def parse_groups(text, n):
    """Solar ① 답 → 묶음 [[0부터 번호 …]]. 빠진 번호 · 두 번 나온 번호 · 범위 밖은 바로잡고, 못 읽으면 모두 혼자."""
    seen, out = set(), []
    for g in _json(text).get("groups") or []:
        ids = [i - 1 for i in (g if isinstance(g, list) else []) if isinstance(i, int) and 1 <= i <= n and i - 1 not in seen]
        seen |= set(ids)
        if ids:
            out.append(ids)
    return out + [[i] for i in range(n) if i not in seen]


def sun_input(stars, groups):
    rows = []
    for gi, ids in enumerate(groups, 1):
        ex = "; ".join(f'"{stars[i]["quotes"][0][:CUT]}"' for i in ids[:3] if stars[i]["quotes"])
        rows.append(f"묶음 {gi}: " + ", ".join(stars[i]["name"] for i in ids) + (f" — 예: {ex}" if ex else ""))
    return "\n".join(rows)


def parse_suns(text, n, choices):
    """Solar ② 답 → 묶음마다 해 이름(목록 밖 · 빠짐은 None)."""
    ok = {c for c, _ in choices}
    got = {x.get("group"): x.get("sun") for x in _json(text).get("suns") or [] if isinstance(x, dict)}
    return [got.get(i) if got.get(i) in ok else None for i in range(1, n + 1)]


def apply(stars, groups, suns, declined=frozenset()):
    """묶음 → 작은 별마다 {head: 머리 별 id, sun: 해 이름}.
    머리 = 가장 많은 글에 나온 별(같으면 먼저 만든 별). 해 = 사용자가 옮긴 별(pin)이 있으면 그 별의 해, 아니면 Solar ② 가 고른 해,
    그것도 없으면 머리의 해. 사용자가 거절한 짝(declined: 'a>b' 정렬 id)이 한 묶음에 있으면 나중 별을 혼자 둔다."""
    out = {}
    queue = [(ids, sun) for ids, sun in zip(groups, suns)]
    while queue:
        ids, sun = queue.pop(0)
        keep = []
        for i in ids:
            if any(">".join(sorted((stars[i]["id"], stars[j]["id"]))) in declined for j in keep):
                queue.append(([i], None))
            else:
                keep.append(i)
        head = min(keep, key=lambda i: (-stars[i]["records"], i))
        pinned = sorted((i for i in keep if stars[i].get("pin")), key=lambda i: (-stars[i]["records"], i))
        pick = stars[pinned[0]]["sun"] if pinned else sun or stars[head]["sun"]
        for i in keep:
            out[stars[i]["id"]] = {"head": stars[head]["id"], "sun": pick}
    return out
