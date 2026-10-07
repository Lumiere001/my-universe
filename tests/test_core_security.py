"""암호화 왕복 · 다른 사용자 키로 못 풂 · 다른 행으로 옮기면 못 풂 · 키 없으면 거부. 원문 없는 로그."""
import json

import pytest
from cryptography.exceptions import InvalidTag

from app.core import config, logger, security


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setattr(config, "DIARY_ENC_KEY", security.new_master_key())


def test_roundtrip_and_ciphertext_has_no_text():
    data = {"text": "오늘 민준이랑 걸었다", "n": [1, 2]}
    blob = security.seal("u1", "entries:e1", data)
    assert security.unseal("u1", "entries:e1", blob) == data
    assert "민준".encode() not in blob and "걸었다".encode() not in blob
    assert security.seal("u1", "entries:e1", data) != blob          # 매번 새 nonce


def test_other_user_or_row_cannot_open():
    blob = security.seal("u1", "entries:e1", {"text": "비밀"})
    with pytest.raises(InvalidTag):
        security.unseal("u2", "entries:e1", blob)
    with pytest.raises(InvalidTag):
        security.unseal("u1", "entries:e2", blob)
    with pytest.raises(InvalidTag):
        security.unseal("u1", "entries:e1", blob[:-1] + bytes([blob[-1] ^ 1]))


def test_master_key_changes_everything(monkeypatch):
    blob = security.seal("u1", "a", {"x": 1})
    monkeypatch.setattr(config, "DIARY_ENC_KEY", security.new_master_key())
    with pytest.raises(InvalidTag):
        security.unseal("u1", "a", blob)


@pytest.mark.parametrize("bad", ["", "short", "bm90LWEta2V5"])
def test_missing_or_bad_key_refused(monkeypatch, bad):
    monkeypatch.setattr(config, "DIARY_ENC_KEY", bad)
    with pytest.raises(security.EncryptionKeyMissing):
        security.seal("u1", "a", {})


def test_logger_drops_unknown_fields_and_long_text(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LOG_TO_FILE", True)
    monkeypatch.setattr(config, "LOG_DIR", tmp_path)
    logger.log("step", step="record", text="오늘 민준이랑 걸었다", quote="원문", name="민준",
               checks=["사람 판정"], code="x" * 100)
    line = json.loads(next(tmp_path.glob("agent_flow_*.log")).read_text())
    assert set(line) == {"ts", "event", "step", "checks", "code"}
    assert len(line["code"]) == logger.MAX_STR


def test_logger_stdout_when_not_file(monkeypatch, capsys):
    monkeypatch.setattr(config, "LOG_TO_FILE", False)
    logger.log("http", path="/health", http=200)
    assert json.loads(capsys.readouterr().out)["http"] == 200
