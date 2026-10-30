"""
app/repository/ops.py

운영 화면(/ops, WS22 — PRD §7 473 · §8.0 · §8.3 · §8.7, 결정 10 · 13)의 숫자와, 동의한 사용자의 피드백 원문 읽기.

- reader(repo): 모든 사용자의 '평문 칸'(id · 종류 · 상태 · 숫자 · 시각)만 읽는다. Postgres 는 역할 app_ops 로 읽어
  암호문 칸(enc · steps_enc)에는 권한이 없다(supabase/migrations/20261014000200_v8_ops.sql). 그래서 summary 는 원문 0건이다.
- summary(...): 지표 계산(순수 함수). 대화 지표는 WS19 · WS20 이 runs 에 남기는 아래 줄을 센다(원문 없음, 숫자만).
    step='chat_turn'  entry_id=대화 id, meta={"turn": n, "suggested": true|false}   별지기가 한 턴 답할 때마다
    step='chat_done'  entry_id=대화 id, meta={"turns": n}                          '대화 마치고 정리하기'
    step='confirm'    entry_id=기록 id, meta={"items": n, "edited": k}              요약 확인에서 '확인하고 우주에 저장'
- user_feedback(s, ...): 운영자 열람에 동의한 사용자 한 명의 피드백과 그 대상 문장(그 사용자 세션 = app_user · RLS 로 읽음).
  가명 처리 · 열람 기록은 app/api/ops.py 가 한다.
- pref_signals / pref_suggestions: 사용자 자기 피드백으로 "이 설정으로 바꿀까요?"(영역 넘는 선 · 제안 빈도, PRD §8.0 선호).
"""

import json
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from app.core import config
from app.repository import diary
from app.service.rules import other_candidates
from app.service.rules.normalize import OTHER

# app_ops 가 읽을 수 있는 칸(마이그레이션의 grant 와 같음). 메모리 가짜도 이 칸만 돌려준다.
COLS = {
    "profiles": ("user_id", "created_at"),
    "entries": ("id", "user_id", "status", "step", "error_code", "sun_id", "source", "confirmed", "created_at"),
    "thoughts": ("user_id", "kind", "certainty", "value"),
    "messages": ("user_id", "entry_id", "suggested", "repeated", "created_at"),
    "feedback": ("user_id", "target", "target_id", "value", "studio_config", "created_at"),
    "runs": ("user_id", "entry_id", "step", "ms", "calls", "est_usd", "error_code", "meta", "studio_config", "created_at"),
    "consents": ("user_id", "version", "operator_read", "created_at"),
}
WARN_AT = 0.8            # 추정 비용 합계가 예산의 80% 를 넘으면 경고, 100% 면 넘음
DROP_AFTER = timedelta(hours=24)   # 마지막 턴 뒤 이만큼 지나도 '정리하기'가 없으면 그만둔 대화
RECENT = 30
WRONG = ("아니에요", "별로", "불편한 점 한 줄")   # 오답 재료(PRD §8.7 '모아서 개선')
REACTIONS = ("맞아요", "아니에요", "좋아요", "별로", "불편한 점 한 줄", "지켰어요", "그만둘래요")


##################################################
# 읽기(평문 칸만)
##################################################

class PgReader:
    def __init__(self, conn):
        self.conn = conn

    def rows(self, table):
        q = sql.SQL("select {} from {}").format(sql.SQL(", ").join(map(sql.Identifier, COLS[table])), sql.Identifier(table))
        return self.conn.execute(q).fetchall()

    def log_read(self, admin_id, user_id, what, items):
        self.conn.execute("insert into ops_reads (admin_id, user_id, what, items) values (%s, %s, %s, %s)",
                          [admin_id, user_id, what, items])


class MemReader:
    def __init__(self, store):
        self.store = store

    def rows(self, table):
        with self.store.lock:
            return [{k: r.get(k) for k in COLS[table]} for r in self.store.tables.get(table, [])]

    def log_read(self, admin_id, user_id, what, items):
        with self.store.lock:
            self.store.tables.setdefault("ops_reads", []).append(
                {"admin_id": admin_id, "user_id": user_id, "what": what, "items": items, "created_at": diary.now()})


@contextmanager
def reader(repo):
    """운영 읽기 트랜잭션 하나(끝나면 커밋 — 열람 기록이 응답보다 먼저 남는다)."""
    if hasattr(repo, "store"):   # 메모리 가짜(MemRepo)
        yield MemReader(repo.store)
        return
    # ponytail: 요청마다 표 전체를 읽는다(사용자 100명 · 수만 줄까지). 늘면 기간 조건 · 집계 쿼리로 바꾼다.
    with psycopg.connect(repo.url, row_factory=dict_row, prepare_threshold=None) as conn:
        conn.execute("set local role app_ops")
        yield PgReader(conn)


##################################################
# 지표(순수 함수)
##################################################

def _day(dt):
    return dt.astimezone(diary.TZ).date()


def _ratio(a, b):
    return round(a / b, 3) if b else None


def _meta(r):
    m = r.get("meta") or {}
    return json.loads(m) if isinstance(m, str) else m


def activity(entries, runs):
    """사용자 → 이 서비스를 쓴 날(현지 날짜). 글을 만든 날(가져온 옛 글도 가져온 날) + 대화한 날."""
    out = defaultdict(set)
    for e in entries:
        out[e["user_id"]].add(_day(e["created_at"]))
    for r in runs:
        if r["step"] == "chat_turn":
            out[r["user_id"]].add(_day(r["created_at"]))
    return out


def next_day(pairs, days, today):
    """pairs: (사용자, 날) 묶음. 다음 날이 다 지난 날만 센다(어제 쓴 사람은 오늘이 끝나야 알 수 있음)."""
    seen = [(u, d) for u, d in set(pairs) if d + timedelta(days=1) < today]
    back = sum(d + timedelta(days=1) in days.get(u, ()) for u, d in seen)
    return {"pairs": len(seen), "returned": back, "ratio": _ratio(back, len(seen))}


def cost(runs, budget, now):
    month = now.astimezone(diary.TZ).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = sum(float(r["est_usd"] or 0) for r in runs)
    by_step = Counter()
    for r in runs:
        by_step[r["step"]] += float(r["est_usd"] or 0)
    return {"total_usd": round(total, 4), "month_usd": round(sum(float(r["est_usd"] or 0) for r in runs if r["created_at"] >= month), 4),
            "budget_usd": budget, "used_ratio": _ratio(total, budget), "warn": total >= budget * WARN_AT, "over": total >= budget,
            "by_step": {k: round(v, 4) for k, v in by_step.most_common() if v}}


def run_stats(runs):
    """단계별 횟수 · 평균 시간 · 실패, 글 한 편(기록 하나)당 평균 시간 · 비용, 최근 실행."""
    steps = defaultdict(list)
    for r in runs:
        steps[r["step"]].append(r)
    by_entry = defaultdict(lambda: [0, 0.0])
    for r in runs:
        if r["entry_id"] and r["step"] not in ("chat_turn", "chat_done", "confirm"):
            by_entry[r["entry_id"]][0] += r["ms"] or 0
            by_entry[r["entry_id"]][1] += float(r["est_usd"] or 0)
    n = len(by_entry)
    recent = sorted(runs, key=lambda r: r["created_at"], reverse=True)[:RECENT]
    return {"count": len(runs),
            "by_step": [{"step": k, "count": len(v), "avg_ms": round(sum(r["ms"] or 0 for r in v) / len(v)),
                         "fails": sum(bool(r["error_code"]) for r in v), "est_usd": round(sum(float(r["est_usd"] or 0) for r in v), 4)}
                        for k, v in sorted(steps.items())],
            "per_entry": {"entries": n, "avg_s": round(sum(x[0] for x in by_entry.values()) / n / 1000, 1) if n else None,
                          "avg_usd": round(sum(x[1] for x in by_entry.values()) / n, 4) if n else None},
            "recent": [{"at": diary.iso(r["created_at"]), "step": r["step"], "ms": r["ms"], "calls": r["calls"],
                        "est_usd": round(float(r["est_usd"] or 0), 4), "code": r["error_code"], "config": r["studio_config"],
                        "entry_id": r["entry_id"]} for r in recent]}


def gates(runs):
    """관문 결과: 실명 관문이 막은 외부 요청(real_name_leak), 말 걸기 검사에 걸려 다시 만든 한마디(voice meta.checks > 0)."""
    voice = [r for r in runs if r["step"] == "voice" and not r["error_code"]]
    redo = sum((_meta(r).get("checks") or 0) > 0 for r in voice)
    return {"real_name_leak": sum(r["error_code"] == "real_name_leak" for r in runs), "voice_runs": len(voice),
            "voice_regenerated": redo, "voice_regenerated_ratio": _ratio(redo, len(voice))}


def failures(entries, runs):
    failed = sorted((e for e in entries if e["status"] == "failed"), key=lambda e: e["created_at"], reverse=True)
    return {"entries": len(failed), "by_code": dict(Counter(e["error_code"] or "unknown" for e in failed).most_common()),
            "run_errors": [{"step": s, "code": c, "count": n}
                           for (s, c), n in Counter((r["step"], r["error_code"]) for r in runs if r["error_code"]).most_common()],
            "recent": [{"entry_id": e["id"], "step": e["step"], "code": e["error_code"], "at": diary.iso(e["created_at"])}
                       for e in failed[:RECENT]]}


def satisfaction(feedback, days, today):
    vals = Counter(f["value"] for f in feedback)
    yes, no = vals["맞아요"], vals["아니에요"]
    by_config = defaultdict(Counter)
    for f in feedback:
        if f["value"] in ("맞아요", "아니에요", "좋아요", "별로"):
            by_config[f["studio_config"] or "없음"][f["value"]] += 1
    return {"yes": yes, "no": no, "yes_ratio": _ratio(yes, yes + no),
            "reactions": {v: vals[v] for v in REACTIONS},
            "by_config": {k: dict(v) for k, v in sorted(by_config.items())},
            "next_day": next_day([(u, d) for u, ds in days.items() for d in ds], days, today)}


def multi_sun(entries, today, window=14):
    """지향 지표 '여러 해에 대해 쓰는지': 사용자마다 글의 해(삶의 영역) 가짓수. 최근 window 일 · 전체."""
    recent, ever = defaultdict(set), defaultdict(set)
    start = today - timedelta(days=window - 1)
    for e in entries:
        if e["status"] == "done" and e["sun_id"]:
            ever[e["user_id"]].add(e["sun_id"])
            if _day(e["created_at"]) >= start:
                recent[e["user_id"]].add(e["sun_id"])
    n = len(recent)
    return {"window_days": window, "users": n, "avg_suns": round(sum(map(len, recent.values())) / n, 2) if n else None,
            "share_2plus": _ratio(sum(len(v) >= 2 for v in recent.values()), n),
            "avg_suns_all": round(sum(map(len, ever.values())) / len(ever), 2) if ever else None}


def talk(runs, now):
    """대화 · 요약 확인 지표(§8.3 대화 줄). 위 runs 약속(chat_turn · chat_done · confirm)으로만 센다."""
    convs = defaultdict(lambda: {"turns": 0, "last": None, "rows": []})
    done = {r["entry_id"] for r in runs if r["step"] == "chat_done"}
    for r in runs:
        if r["step"] == "chat_turn":
            c = convs[r["entry_id"]]
            c["rows"].append(r)
            c["turns"] = max(c["turns"], _meta(r).get("turn") or len(c["rows"]))
            c["last"] = max(c["last"] or r["created_at"], r["created_at"])
    dropped = {k for k, c in convs.items() if k not in done and now - c["last"] > DROP_AFTER}

    def stop_after(flag):   # 그 턴이 그만둔 대화의 마지막 턴인 비율
        turns = [(k, r) for k, c in convs.items() for r in c["rows"] if bool(_meta(r).get("suggested")) is flag]
        last = sum(k in dropped and (_meta(r).get("turn") or 0) == convs[k]["turns"] for k, r in turns)
        return _ratio(last, len(turns))

    conf = [_meta(r) for r in runs if r["step"] == "confirm"]
    items, edited = sum(m.get("items") or 0 for m in conf), sum(m.get("edited") or 0 for m in conf)
    n = len(convs)
    return {"conversations": n, "avg_turns": round(sum(c["turns"] for c in convs.values()) / n, 1) if n else None,
            "finished": len(done & set(convs)), "dropped": len(dropped),
            "drop_at": {str(t): k for t, k in sorted(Counter(convs[k]["turns"] for k in dropped).items())},
            "stop_after_suggestion": stop_after(True), "stop_without_suggestion": stop_after(False),
            "confirms": len(conf), "edited_ratio": _ratio(edited, items),
            "confirms_with_edit": _ratio(sum((m.get("edited") or 0) > 0 for m in conf), len(conf))}


def voice(messages, runs, feedback, days, today):
    """말 걸기 지표: 제안 넣은 비율 · 반복 다시 만든 비율 · '별로' 비율 · 제안 있음/없음의 다음 날 다시 쓴 비율."""
    known = [m for m in messages if m["suggested"] is not None]
    rep = [m for m in messages if m["repeated"] is not None]
    by_day = defaultdict(bool)   # (사용자, 날) → 그날 받은 말에 제안이 하나라도 있었나(한마디 + 대화 턴)
    for m in known:
        by_day[(m["user_id"], _day(m["created_at"]))] |= bool(m["suggested"])
    for r in runs:
        if r["step"] == "chat_turn" and "suggested" in _meta(r):
            by_day[(r["user_id"], _day(r["created_at"]))] |= bool(_meta(r)["suggested"])
    dislike = sum(f["target"] == "message" and f["value"] == "별로" for f in feedback)
    return {"messages": len(messages), "suggested_ratio": _ratio(sum(bool(m["suggested"]) for m in known), len(known)),
            "repeat_ratio": _ratio(sum(bool(m["repeated"]) for m in rep), len(rep)),
            "dislike_ratio": _ratio(dislike, len(messages)),
            "next_day_with_suggestion": next_day([k for k, v in by_day.items() if v], days, today),
            "next_day_without_suggestion": next_day([k for k, v in by_day.items() if not v], days, today)}


def other_counts(thoughts):
    """목록 밖 값('기타')이 몇 번 나왔나(칸별 숫자만). 원래 말(새 값 후보)은 동의한 사용자 것만 /ops/feedback 에서."""
    return {"thoughts": len(thoughts), **{f: sum(t[f] == OTHER for t in thoughts) for f in ("kind", "certainty", "value")}}


def consenting(consents, version):
    """가장 최근 동의가 지금 판이고 운영자 열람(operator_read)에 동의한 사용자 id."""
    last = {}
    for c in sorted(consents, key=lambda c: c["created_at"]):
        last[str(c["user_id"])] = c
    return sorted(u for u, c in last.items() if c["version"] == version and c["operator_read"])


def eval_results(base=None, keep=5):
    """골든셋 결과(eval/results/*.json)의 요약 숫자. 배포 번들에는 eval/ 이 없어 None(로컬 · 저장소에서만 보임)."""
    base = base or config.BASE_DIR / "eval" / "results"
    files = sorted((p for p in base.glob("*.json") if p.name != "baseline.json"), key=lambda p: p.name, reverse=True)[:keep] \
        if base.is_dir() else []
    out = []
    for p in files:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))["summary"]
        except (ValueError, KeyError, OSError):
            continue
        cats = s.get("categories", {})
        out.append({"file": p.name, "gate_ok": s.get("gate_ok"), "regressions": len(s.get("regressions") or []),
                    "passed": sum(c.get("passed", 0) for c in cats.values()), "total": sum(c.get("total", 0) for c in cats.values()),
                    "est_usd": (s.get("cost") or {}).get("est_usd"),
                    "categories": {k: {"passed": c.get("passed"), "total": c.get("total")} for k, c in cats.items()}})
    return out or None


PERSONAL_MIN = 5   # ponytail: 사람 하나의 비율을 믿을 최소 반응 수(근거 없음). 파일럿 반응이 쌓이면 다시 정한다
FIXES = ("고침", "옮김", "합침", "떼어 냄")


def _rate(rows, good, bad):
    g, b = sum(r["value"] in good for r in rows), sum(r["value"] in bad for r in rows)
    return round(g / (g + b), 3) if g + b >= PERSONAL_MIN else None


def personal(feedback, entries, today, window=14):
    """개인 지표(2026-10-30, 개인 고리의 '재기'): 사람마다 그 사람 반응으로만. 최근 window 일(now)과 그 전(before)을 따로 →
    links_yes = AI 추정 선 '맞아요' 비율, dislike = 한마디 '별로' 비율, fixes = 끝난 글 10편당 고침 · 옮김 · 합침(AI 정리를 고친 수).
    반응이 PERSONAL_MIN 보다 적으면 None(믿기 어려움). 원문은 쓰지 않는다(값 · 대상 종류 · 시각만)."""
    cut = today - timedelta(days=window)
    by = defaultdict(lambda: {"fb": [], "done": 0})
    for f in feedback:
        by[str(f["user_id"])]["fb"].append(f)
    for e in entries:
        if e.get("status") == "done":
            by[str(e["user_id"])]["done"] += 1
    out = {}
    for u, d in by.items():
        now_ = [f for f in d["fb"] if _day(f["created_at"]) >= cut]
        old = [f for f in d["fb"] if _day(f["created_at"]) < cut]
        rel = lambda xs: [f for f in xs if f["target"] == "relation"]   # noqa: E731
        msg = lambda xs: [f for f in xs if f["target"] == "message"]   # noqa: E731
        out[u] = {"links_yes": {"now": _rate(rel(now_), ("맞아요",), ("아니에요",)), "before": _rate(rel(old), ("맞아요",), ("아니에요",))},
                  "dislike": {"now": _rate(msg(now_), ("별로",), ("좋아요",)), "before": _rate(msg(old), ("별로",), ("좋아요",))},
                  "fixes": round(10 * sum(f["value"] in FIXES for f in d["fb"]) / d["done"], 1) if d["done"] else None}
    return out


def personal_spread(per, drop=0.15):
    """운영은 사람을 하나하나 보지 않고 분포만 본다: 지표마다 잴 수 있는 사람 수 · 중앙값 · 자기 기준보다 나빠진 사람 수(drop 이상)."""
    def med(xs):
        xs = sorted(xs)
        return round((xs[len(xs) // 2] + xs[(len(xs) - 1) // 2]) / 2, 3) if xs else None
    out = {}
    for key, worse in (("links_yes", lambda n, b: n <= b - drop), ("dislike", lambda n, b: n >= b + drop)):
        vals = [p[key] for p in per.values() if p[key]["now"] is not None]
        out[key] = {"users": len(vals), "median": med([v["now"] for v in vals]),
                    "worse": sum(v["before"] is not None and worse(v["now"], v["before"]) for v in vals)}
    fx = [p["fixes"] for p in per.values() if p["fixes"] is not None]
    out["fixes"] = {"users": len(fx), "median": med(fx)}
    return out


def personal_loop(fb):
    """개인 고리가 도는 모습(사람 id 없이): 개인 층이 켜진 사람 수와, 다이얼마다 자동으로 옮긴 수 · 방향 · 사람 수 · 되돌린 수.
    되돌림이 많으면 문턱(PREF_MIN)이 낮다는 뜻이고, 여러 사람이 같은 방향으로 옮기면 공통 틀(기본값)을 바꿀 후보다."""
    def who(ok):
        return len({str(f["user_id"]) for f in fb if ok(f)})
    dials = {}
    for f in fb:
        if f["target"] == "setting" and f["value"] in (AUTO, UNDO):
            key, _, to = (f["target_id"] or "").partition(":")
            d = dials.setdefault(key, {"setting": key, "moved": 0, "users": set(), "undone": 0, "to": Counter()})
            if f["value"] == AUTO:
                d["moved"] += 1
                d["users"].add(str(f["user_id"]))
                d["to"][to] += 1
            else:
                d["undone"] += 1
    return {"on": {"auto": who(lambda f: f["target"] == "setting" and f["value"] == AUTO),
                   "disliked": who(lambda f: f["target"] == "message" and f["value"] == "별로"),
                   "rejected": who(lambda f: f["target"] == "relation" and f["value"] == "아니에요"),
                   "fixed": who(lambda f: f["value"] in FIXES)},
            "dials": [{**d, "users": len(d["users"]), "to": dict(d["to"])} for d in dials.values()],
            "min": PREF_MIN}


def summary(r, version, budget, now=None):
    """운영 화면 한 장. r = reader(repo). 원문 0건(숫자 · 코드 · id · 시각만)."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(diary.TZ).date()
    entries, runs, fb, msgs = r.rows("entries"), r.rows("runs"), r.rows("feedback"), r.rows("messages")
    days = activity(entries, runs)
    users = {str(x["user_id"]) for x in r.rows("profiles")} | {str(u) for u in days}
    week = today - timedelta(days=6)
    readers = consenting(r.rows("consents"), version)
    return {
        "generated_at": diary.iso(now),
        "users": {"total": len(users), "active_7d": sum(any(d >= week for d in ds) for ds in days.values()),
                  "operator_read": len(readers)},
        "cost": cost(runs, budget, now),
        "runs": run_stats(runs),
        "gates": gates(runs),
        "failures": failures(entries, runs),
        "eval": eval_results(),
        "satisfaction": satisfaction(fb, days, today),
        "direction": {"multi_sun": multi_sun(entries, today),
                      "closer_feeling": None},   # '가까워졌다는 느낌'은 묻지 않는다(2026-10-13 동규)
        "talk": talk(runs, now),
        "voice": voice(msgs, runs, fb, days, today),
        "other_values": other_counts(r.rows("thoughts")),
        "personal": personal_spread(personal(fb, entries, today)),
        "personal_loop": personal_loop(fb),
        "feedback_text": {"consented": sum(str(f["user_id"]) in readers and f["value"] == "불편한 점 한 줄" for f in fb),
                          "not_consented": sum(str(f["user_id"]) not in readers and f["value"] == "불편한 점 한 줄" for f in fb)},
    }


##################################################
# 동의한 사용자 한 명의 피드백 원문(그 사용자 세션으로)
##################################################

def _target_text(s, target, tid, enc):
    """피드백이 가리키는 문장: 관계(그때 생각 → 지금 생각, 설명) · 한마디 · 다짐 · 질문 생각 · 기록 요약. 앱 · 날씨는 없음."""
    tid = tid or ""
    if target == "relation":
        a, _, b = tid.partition(">")
        text = {t["id"]: t.get("text", "") for t in diary.thoughts(s, id=[a, b])}
        rel = next(iter(diary.relations(s, id=tid)), None)
        kind = rel["type"] if rel else (enc.get("relation") or {}).get("type", "")
        why = f" ({rel['explanation']})" if rel and rel.get("explanation") else ""
        return f"[{kind}] {text.get(a, '')} → {text.get(b, '')}{why}"
    if target == "message":
        m = s.rows("messages", entry_id=tid)
        return diary.message(s, m[0]).get("text") if m else None
    if target in ("vow", "question"):
        t = diary.thoughts(s, id=tid)
        return t[0].get("text") if t else None
    if target == "entry":
        e = diary.entry(s, tid)
        return e["data"].get("summary") if e else None
    return None


def user_feedback(s, since, wrong_only=False):
    """그 사용자의 피드백(since 뒤) → [{at, target, value, text, target_text, config}] + 목록 밖 원래 말 후보.
    마음 상태 버튼(오늘은 위로만 · 살살)은 평문 칸의 '상태 버튼'만 쓰고 풀지 않는다. 가명 처리 전 원문이다."""
    items = []
    for f in s.rows("feedback", order="created_at"):
        if f["created_at"] < since or (wrong_only and f["value"] not in WRONG):
            continue
        enc = diary.unseal(s, "feedback", f["id"], f["enc"]) if f["value"] != diary.MOOD_LABEL else {}
        items.append({"at": diary.iso(f["created_at"]), "target": f["target"], "value": f["value"],
                      "text": enc.get("text") if f["value"] == "불편한 점 한 줄" else None,
                      "target_text": _target_text(s, f["target"], f["target_id"], enc), "config": f["studio_config"]})
    cands = [] if wrong_only else other_candidates(
        diary.thoughts(s) + [{"original": e["data"].get("original") or {}} for e in diary.entries(s, status="done")])
    return items, cands


LESSONS = ("옮김", "고침", "합침", "떼어 냄", "아니에요")


def user_lessons(s, since):
    """동의한 사용자 한 명이 AI 정리를 고친 것(since 뒤) → [{kind, from, to, topic, type}] (개인 맞춤 Ops ⑤의 재료, 가명 처리 전)."""
    out = []
    for f in s.rows("feedback", order="created_at"):
        if f["created_at"] < since or f["value"] not in LESSONS or not f.get("enc"):
            continue
        e = diary.unseal(s, "feedback", f["id"], f["enc"]) or {}
        if f["value"] == "아니에요":
            if (e.get("relation") or {}).get("type"):
                out.append({"kind": "아니에요", "type": e["relation"]["type"]})
        elif f["value"] == "고침":
            out.append({"kind": "고침", "field": e.get("field"), "from": e.get("from"), "to": e.get("to")})
        else:
            out.append({"kind": f["value"], "from": e.get("from"), "to": e.get("to") or e.get("into"), "topic": e.get("topic") or e.get("from")})
    return out


def framework_candidates(per_user, min_users=2):
    """공통 틀 후보(개인 맞춤 Ops ⑤, 2026-10-30): 여러 사람이 같은 방향으로 고친 것만 모은다(min_users 명 이상 — 한 사람의 버릇이나
    이름이 운영자에게 드러나지 않게). per_user: [[lesson, ...], ...](사용자마다, 주제 이름은 가명 처리된 것).
    → [{kind, what, users, count, words}] (사람 수 · 횟수 많은 순). 옮김의 words 는 min_users 명 이상이 쓴 주제 낱말만."""
    agg = {}
    for i, lessons in enumerate(per_user):
        for x in lessons:
            what = {"옮김": lambda: f"{x.get('from')} → {x.get('to')}", "고침": lambda: f"{x.get('field')}: {x.get('from')} → {x.get('to')}",
                    "아니에요": lambda: str(x.get("type")), "떼어 냄": lambda: "묶음에서 떼어 냄", "합침": lambda: "작은 별 합침"}[x["kind"]]()
            a = agg.setdefault((x["kind"], what), {"users": set(), "count": 0, "words": defaultdict(set)})
            a["users"].add(i)
            a["count"] += 1
            if x["kind"] == "옮김":
                for w in (x.get("topic") or "").split():
                    a["words"][w].add(i)
    out = [{"kind": k, "what": w, "users": len(a["users"]), "count": a["count"],
            "words": sorted((t for t, us in a["words"].items() if len(us) >= min_users), key=lambda t: -len(a["words"][t]))[:5]}
           for (k, w), a in agg.items() if len(a["users"]) >= min_users]
    return sorted(out, key=lambda c: (-c["users"], -c["count"], c["kind"], c["what"]))


##################################################
# 선호 맞추기 제안(사용자 자기 피드백, PRD §8.0 선호 · §8.7 바로 반영)
##################################################

STEPS = {"cross_links": ("숨김", "눌렀을 때", "항상"), "suggestions": ("적게", "보통", "많이")}
PREF_MIN = 3   # ponytail: 고정 문턱(연구 근거 없음, 이만큼 같은 쪽으로 누르면 묻는다). 피드백이 쌓이면 다시 정한다
AUTO, UNDO = "자동 조정", "되돌림"   # 개인 고리가 남기는 원문 없는 기록(feedback target='setting', target_id='다이얼:값') — 운영은 이것만 센다
REASON = {("cross_links", -1): "다른 영역과 이어진 선에 '아니에요'를 자주 눌렀어요.",
          ("cross_links", 1): "다른 영역과 이어진 선에 '맞아요'를 자주 눌렀어요.",
          ("suggestions", -1): "다음 걸음 제안이 든 한마디에 '별로'를 자주 눌렀어요.",
          ("suggestions", 1): "다음 걸음 제안이 든 한마디에 '좋아요'를 자주 눌렀어요."}


def pref_signals(s, since=None):
    """since(지난번 제안을 보고 고른 때) 뒤의 피드백만 → {"cross_links": (맞아요, 아니에요), "suggestions": (좋아요, 별로)}.
    영역을 넘는 선 = 관계의 cross_domain, '아니에요'로 이미 지운 관계는 두 생각의 해가 다른지로 본다."""
    fb = [f for f in s.rows("feedback") if since is None or f["created_at"] > since]
    rel = [f for f in fb if f["target"] == "relation" and f["value"] in ("맞아요", "아니에요") and f["target_id"]]
    msg = [f for f in fb if f["target"] == "message" and f["value"] in ("좋아요", "별로") and f["target_id"]]
    cross = {r["id"]: r["cross_domain"] for r in s.rows("relations", id=[f["target_id"] for f in rel])} if rel else {}
    tids = [t for f in rel for t in f["target_id"].split(">")]
    sun = {t["id"]: t["sun_id"] for t in s.rows("thoughts", id=tids)} if tids else {}

    def is_cross(tid):
        if tid in cross:
            return cross[tid]
        a, _, b = tid.partition(">")
        return a in sun and b in sun and sun[a] != sun[b]

    sug = {m["entry_id"]: m.get("suggested") for m in s.rows("messages", entry_id=[f["target_id"] for f in msg])} if msg else {}
    pick = [f for f in rel if is_cross(f["target_id"])]
    said = [f for f in msg if sug.get(f["target_id"])]
    return {"cross_links": (sum(f["value"] == "맞아요" for f in pick), sum(f["value"] == "아니에요" for f in pick)),
            "suggestions": (sum(f["value"] == "좋아요" for f in said), sum(f["value"] == "별로" for f in said))}


def auto_pref(s):
    """개인 고리(2026-10-30): 반응이 한쪽으로 쌓이면(pref_suggestions) 묻지 않고 그 사람 설정을 한 칸 옮기고, 알림(pref_auto)을 남긴다.
    사용자는 알림에서 되돌릴 수 있다. 다이얼마다 옮긴 뒤의 반응만 다시 센다(pref_seen_by — 같은 반응으로 거듭 옮기지 않게,
    한 다이얼을 옮겨도 다른 다이얼에 쌓인 반응은 그대로). → 이번에 옮긴 것 목록."""
    st, ob = diary.profile(s)
    seen = ob.get("pref_seen_by") or {}
    moves = []
    for key in STEPS:
        since = seen.get(key) or ob.get("pref_seen")
        moves += pref_suggestions(st, {key: pref_signals(s, diary.parse_dt(since) if since else None)[key]})
    if not moves:
        return []
    at = diary.now().isoformat()
    notes = [{**m, "id": diary.new_id("p"), "at": at, "seen": False} for m in moves]
    diary.save_profile(s, settings={m["setting"]: m["to"] for m in moves},
                       onboarding={"pref_seen_by": {**seen, **{m["setting"]: at for m in moves}},
                                   "pref_auto": (ob.get("pref_auto") or [])[-9:] + notes})
    for m in moves:   # 설정 · 알림은 암호문이라 운영이 못 읽는다 → 무엇을 어디로 옮겼는지만 평문 기록으로
        diary.add_feedback(s, "setting", f"{m['setting']}:{m['to']}", AUTO)
    return notes


def pref_undo(s, note_id):
    """알림 하나 되돌리기: 설정이 아직 그 값이면 원래 값으로, 알림은 본 것으로. 그 다이얼은 되돌린 뒤의 반응만 다시 센다."""
    st, ob = diary.profile(s)
    notes = ob.get("pref_auto") or []
    n = next((x for x in notes if x["id"] == note_id), None)
    if not n:
        return None
    back = {n["setting"]: n["from"]} if st.get(n["setting"]) == n["to"] else {}
    if not n.get("undone"):
        diary.add_feedback(s, "setting", f"{n['setting']}:{n['from']}", UNDO)
    marks = [{**x, "seen": True, "undone": True} if x["id"] == note_id else x for x in notes]
    diary.save_profile(s, settings=back, onboarding={"pref_auto": marks, "pref_seen_by": {
        **(ob.get("pref_seen_by") or {}), n["setting"]: diary.now().isoformat()}})
    return {**n, "undone": True}


def pref_suggestions(settings, signals):
    """한 쪽으로 PREF_MIN 번 이상 · 반대쪽의 두 배 이상이면 한 칸 옮기기를 제안한다(바꾸는 것은 사용자)."""
    out = []
    for key, (up, down) in signals.items():
        steps = STEPS[key]
        i = steps.index(settings[key]) if settings.get(key) in steps else 1
        move = -1 if down >= PREF_MIN and down >= 2 * up else 1 if up >= PREF_MIN and up >= 2 * down else 0
        if move and 0 <= i + move < len(steps):
            out.append({"setting": key, "from": steps[i], "to": steps[i + move], "reason": REASON[(key, move)]})
    return out
