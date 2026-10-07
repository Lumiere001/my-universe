"""
app/core/auth.py

로그인 확인. 화면이 보낸 `Authorization: Bearer <access token>` 을 Supabase(/auth/v1/user)에 물어 사용자를 얻는다.
구글 로그인이든 로컬 시험용 계정이든 같은 길이다. 같은 토큰은 짧게(60초) 기억해 요청마다 묻지 않는다
(그래서 로그아웃한 토큰이 최대 60초 더 통한다 — 알고 둔 한계). ALLOWED_EMAILS 가 있으면 목록 밖 계정은 403.
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
    if r.status_code >= 500:
        raise ApiError(503, "auth_unavailable", "로그인을 확인하지 못했어요. 잠시 뒤 다시 해 주세요.")
    try:
        body = r.json() if r.status_code == 200 else {}
    except ValueError:
        raise ApiError(503, "auth_unavailable", "로그인을 확인하지 못했어요. 잠시 뒤 다시 해 주세요.")
    if not isinstance(body, dict) or not body.get("id"):
        raise ApiError(401, "unauthorized", "다시 로그인해 주세요.")
    user = {"id": body["id"], "email": body.get("email") or ""}
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
    user = verify(token.strip())
    if config.ALLOWED_EMAILS and user["email"].lower() not in config.ALLOWED_EMAILS:
        raise ApiError(403, "not_allowed", "초대된 사람만 쓸 수 있어요.")
    return user


def forget(uid):
    """기억해 둔 토큰 중 이 사용자 것을 지운다(계정을 지운 뒤)."""
    with _lock:
        for k in [k for k, (u, _) in _cache.items() if u["id"] == uid]:
            del _cache[k]


def delete_account(uid):
    """Supabase 관리 API 로 auth 계정을 지운다 → 모든 표가 FK cascade 로 지워진다. 서비스 키는 이 함수에서만 쓴다."""
    key = config.SUPABASE_SERVICE_ROLE_KEY
    try:
        r = httpx.delete(f"{config.SUPABASE_URL}/auth/v1/admin/users/{uid}", timeout=10,
                         headers={"apikey": key, "Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        r = None
    if r is None or r.status_code not in (200, 204, 404):
        raise ApiError(502, "account_delete_failed", "계정을 지우지 못했어요. 잠시 뒤 다시 해 주세요.")
    forget(uid)
