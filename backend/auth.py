"""
Google OAuth token validation middleware.

Supports three auth modes:
1. Google OAuth token → validated via Google tokeninfo, restricted to @breadfast.com
2. Static JWT fallback → if BF_CATALOG_TOKEN is set, accepts that token directly
3. Dev mode → if neither GOOGLE_CLIENT_ID nor BF_CATALOG_TOKEN is set, skips auth
"""

import time
from threading import Lock

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

# Token validation cache: {access_token: {"email": str, "cached_at": float}}
_token_cache: dict[str, dict] = {}
_cache_lock = Lock()
_CACHE_TTL = 300  # 5 minutes

# Paths that don't require authentication
PUBLIC_PATHS = {"/api/startup-status", "/docs", "/openapi.json"}


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS


async def google_auth_middleware(request: Request, call_next):
    """Validate auth token: Google OAuth, static JWT fallback, or dev mode."""
    from backend.config import settings

    path = request.url.path

    if _is_public(path) or not path.startswith("/api/"):
        return await call_next(request)

    # Dev mode: skip auth when neither Google nor static token is configured
    if not settings.GOOGLE_CLIENT_ID and not settings.BF_CATALOG_TOKEN:
        request.state.email = "dev@breadfast.com"
        request.state.access_token = None
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")

    # If no auth header and we have a static token, use it as fallback
    if not auth_header.startswith("Bearer ") and settings.BF_CATALOG_TOKEN:
        request.state.email = "service@breadfast.com"
        request.state.access_token = settings.BF_CATALOG_TOKEN
        return await call_next(request)

    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "Missing or invalid Authorization header. Sign in with Google."},
        )

    token = auth_header[7:]  # Strip "Bearer "

    # Check if token matches the static catalog token
    if settings.BF_CATALOG_TOKEN and token == settings.BF_CATALOG_TOKEN:
        request.state.email = "service@breadfast.com"
        request.state.access_token = token
        return await call_next(request)

    # Validate as Google OAuth token
    user_info = _get_cached(token)
    if not user_info:
        user_info = _validate_google_token(token)
        if user_info is None:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or expired token. Please sign in again."},
            )
        if not user_info.get("email", "").endswith("@breadfast.com"):
            return JSONResponse(
                status_code=403,
                content={"error": f"Access restricted to @breadfast.com accounts. Got: {user_info.get('email', 'unknown')}"},
            )
        _set_cached(token, user_info)

    # Attach user info to request state
    request.state.email = user_info["email"]
    request.state.access_token = token

    return await call_next(request)


def _get_cached(token: str) -> dict | None:
    with _cache_lock:
        entry = _token_cache.get(token)
        if entry and entry.get("cached_at", 0) + _CACHE_TTL > time.time():
            return entry
        if entry:
            del _token_cache[token]
        return None


def _set_cached(token: str, user_info: dict):
    with _cache_lock:
        user_info["cached_at"] = time.time()
        _token_cache[token] = user_info
        # Evict old entries
        now = time.time()
        expired = [k for k, v in _token_cache.items() if v.get("cached_at", 0) + _CACHE_TTL < now]
        for k in expired:
            del _token_cache[k]


def _validate_google_token(token: str) -> dict | None:
    """Validate a Google access token via Google's tokeninfo endpoint."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"access_token": token},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return {
                "email": data.get("email", ""),
                "email_verified": data.get("email_verified", "false") == "true",
            }
    except Exception:
        return None
