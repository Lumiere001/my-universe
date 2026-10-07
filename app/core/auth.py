"""
app/core/auth.py

로그인 확인. 화면이 보낸 `Authorization: Bearer <access token>` 을 Supabase(/auth/v1/user)에 물어 사용자를 얻는다.
구글 로그인이든 로컬 시험용 계정이든 같은 길이다. 같은 토큰은 짧게(60초) 기억해 요청마다 묻지 않는다.
"""

import hashlib
import threading
import time

import httpx
from fastapi import Header

from app.core import config
from app.exceptions import ApiError

TTL_S = 60
_cache, _lock = {}, threading.Lock()


def verify(token):
    """토큰 → {"id", "email"}. 틀리거나 만료면 ApiError(401)."""
    k = hashlib.sha256(token.encode()).hexdigest()
    with _lock:
        hit = _cache.get(k)
        if hit and hit[1] > time.time():
            return hit[0]
    if not config.SUPABASE_URL:
        raise ApiError(503, "auth_unconfigured", "로그인 설정이 아직 없어요.")
    try:
        r = httpx.get(f"{config.SUPABASE_URL}/auth/v1/user", timeout=10,
                      headers={"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"})
    except httpx.HTTPError:
        raise ApiError(503, "auth_unavailable", "로그인을 확인하지 못했어요. 잠시 뒤 다시 해 주세요.")
    if r.status_code != 200 or not r.json().get("id"):
        raise ApiError(401, "unauthorized", "다시 로그인해 주세요.")
    user = {"id": r.json()["id"], "email": r.json().get("email") or ""}
    with _lock:
        if len(_cache) > 1000:
            _cache.clear()
        _cache[k] = (user, time.time() + TTL_S)
    return user


def get_user(authorization: str = Header(default="")):
    """FastAPI 의존성: 로그인한 사용자."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "unauthorized", "로그인이 필요해요.")
    return verify(token.strip())
