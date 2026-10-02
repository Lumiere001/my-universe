"""
app.py

나의 우주 — 순차 실행 스크립트 (가이드의 `python app.py`)

    python app.py                          # 가상 인스타그램 ZIP (하늘의 글 29편)
    python app.py data/samples/note.md     # MD · TXT · ZIP 아무거나

결과:
    output/records.json              정리된 기록 파일 (우주 상태 전체)
    result/reports/<기록ID>.json     글마다 관측 보고서
    result/observation_report.json   마지막 글의 관측 보고서
"""

import json
import sys
import time
from pathlib import Path

import config
import importer
import service
import universe


def load_records(path: Path):
    data = path.read_bytes()
    if path.suffix.lower() == ".zip":
        return importer.from_instagram_zip(data)
    return importer.from_text_file(path.name, data)


def main(paths):
    config.validate_config()
    config.DISK_CACHE = True   # 로컬 실행은 캐시를 켠다 (같은 글 · 같은 설정은 다시 보내지 않음)
    state_file = config.OUTPUT_DIR / "records.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() and "--fresh" not in sys.argv else universe.new_state()

    records = [r for p in paths for r in load_records(Path(p))]
    records.sort(key=lambda r: (r["day"], r["written_at"]))
    print(f"글 {len(records)}편을 처리합니다.")

    t0, reports, spent = time.time(), [], 0.0
    (config.RESULT_DIR / "reports").mkdir(parents=True, exist_ok=True)
    for i, rec in enumerate(records, 1):
        rep = service.process_record(state, rec, progress=lambda s: None)
        spent += sum(m["est_cost"] for k, m in rep["run"].items() if k.endswith("_agent") and not m.get("cached"))
        view = service.view_report(state, rec["id"])
        reports.append(view)
        (config.RESULT_DIR / "reports" / f"{rec['id']}.json").write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{i:2}/{len(records)}] {rec['day']} {rec['title'][:18]:<18} {rep['type']:<6} → {rep['observation_state']:<10} "
              f"관계 {len(rep['relations'])} · {rep['run']['seconds']}s · ${rep['run']['est_cost']}")
        state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    if reports:
        (config.RESULT_DIR / "observation_report.json").write_text(json.dumps(reports[-1], ensure_ascii=False, indent=2), encoding="utf-8")
    g = [r["gates"] for r in reports]
    print(f"\n완료 {time.time() - t0:.0f}초 · 이번 실행 추정 비용 ${spent:.2f} (캐시로 건너뛴 실행은 0)")
    print(f"관문: G1 원문에 없는 인용 걸러냄 {sum(x['G1_dropped_quotes'] for x in g)} · "
          f"G2 날짜 문제 {sum(not x['G2_date_ok'] for x in g)} · G3 단정 표현 바꿈 {sum(x.get('G3_rewritten', 0) for x in g)} · "
          f"G4 가린 이름 {len(state['names'])}")
    print(f"결과: {state_file}, {config.RESULT_DIR / 'observation_report.json'}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args or [config.VIRTUAL_ZIP])
