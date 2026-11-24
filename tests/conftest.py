"""시험은 열린 서비스 기준(배포 기본값은 닫힘, 2026-11-25). 닫힘 흐름은 tests/test_closing.py 가 monkeypatch 로 켠다."""
import os

os.environ.setdefault("SERVICE_CLOSED", "0")
