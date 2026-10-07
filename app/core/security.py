"""
app/core/security.py

원문 암호화. AES-256-GCM, 사용자별 키 = HKDF-SHA256(DIARY_ENC_KEY, salt=user_id).
행마다 seal(user_id, aad, dict) → bytes(nonce 12 + 암호문). aad 에 '표:행 id'를 넣어 다른 행으로 옮겨 붙이면 풀리지 않는다.
"""

import base64
import json
import os
from functools import lru_cache

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core import config


class EncryptionKeyMissing(RuntimeError):
    """DIARY_ENC_KEY 가 없거나 32바이트가 아니다."""


def _master():
    raw = config.DIARY_ENC_KEY
    try:
        key = base64.b64decode(raw, validate=True) if raw else b""
    except ValueError:
        key = b""
    if len(key) != 32:
        raise EncryptionKeyMissing("DIARY_ENC_KEY(base64 32바이트)가 필요합니다")
    return key


@lru_cache(maxsize=256)
def _key(master, user_id):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=str(user_id).encode(), info=b"my-universe/diary/v1").derive(master)


def seal(user_id, aad, data):
    nonce = os.urandom(12)
    plain = json.dumps(data, ensure_ascii=False).encode()
    return nonce + AESGCM(_key(_master(), str(user_id))).encrypt(nonce, plain, aad.encode())


def unseal(user_id, aad, blob):
    """다른 사용자 키 · 다른 행 aad · 바뀐 암호문이면 cryptography.exceptions.InvalidTag."""
    if blob is None:
        return {}
    blob = bytes(blob)
    plain = AESGCM(_key(_master(), str(user_id))).decrypt(blob[:12], blob[12:], aad.encode())
    return json.loads(plain)


def new_master_key():
    """scripts/dev_up.sh 가 .env.local 에 넣을 새 키(출력하지 않고 파일에만 쓴다)."""
    return base64.b64encode(os.urandom(32)).decode()
