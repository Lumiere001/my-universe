"""
runlog.py

실행 기록 (Ops). 글 원문과 인용문은 남기지 않는다. ID, 설정 버전, 시간, 비용, 관문 결과, 개수만 남긴다.
"""

import json
from datetime import datetime, timedelta, timezone

import config

LOG = config.RUNS_DIR / "run_log.jsonl"
KST = timezone(timedelta(hours=9))


def write(run_id, step, **fields):
    entry = {"at": datetime.now(KST).isoformat(timespec="seconds"), "run_id": run_id, "step": step, **fields}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read(limit=500):
    if not LOG.exists():
        return []
    lines = LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    return [json.loads(l) for l in lines if l.strip()]
