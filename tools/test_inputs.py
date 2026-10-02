"""입력 3종 시험 (가이드: 서로 다른 문서 3개 이상으로 끝까지 실행).

    python tools/test_inputs.py      # MD 파일, TXT 파일, 직접 쓴 글 → 새 우주에서 차례로 관측

인스타그램 ZIP은 `python app.py`가 시험한다. 결과는 data/ops/input_tests.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import importer  # noqa: E402
import service  # noqa: E402
import universe  # noqa: E402

config.validate_config()
samples = config.DATA_DIR / "samples"
recs = [*importer.from_text_file("2026-09-25-독서노트.md", (samples / "2026-09-25-독서노트.md").read_bytes()),
        *importer.from_text_file("2026-10-01-일기.txt", (samples / "2026-10-01-일기.txt").read_bytes()),
        importer.from_direct("10/2 목요일", "오늘은 아침에 휴대폰을 침대 밖에 두고 잤더니 일찍 일어났다. "
                             "의지보다 환경이 먼저라는 말이 맞는 것 같다. 이번 주는 이 습관을 지켜 보자.", "2026-10-02")]
state, out = universe.new_state("시험"), []
for kind, rec in zip(["MD 파일", "TXT 파일", "직접 쓰기"], recs):
    rep = service.process_record(state, rec)
    v = service.view_report(state, rec["id"])
    out.append({"input": kind, "title": rec["title"], "day": rec["day"], "day_basis": rec["day_basis"], "type": v["type"],
                "observation_state": v["observation_state"], "thoughts": v["counts"], "relations": len(rep["relations"]),
                "question": v["question"], "gates": v["gates"], "seconds": v["run"]["seconds"], "est_cost_usd": v["run"]["est_cost_usd"]})
    print(json.dumps(out[-1], ensure_ascii=False))
(config.DATA_DIR / "ops").mkdir(parents=True, exist_ok=True)
(config.DATA_DIR / "ops" / "input_tests.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
