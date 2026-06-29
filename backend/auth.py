"""
Google OAuth token validation middleware.

Auth modes:
1. Google OAuth token → validated via Google tokeninfo; restricted to
   @breadfast.com AND to tokens minted for THIS app (aud == GOOGLE_CLIENT_ID).
2. Dev mode → if GOOGLE_CLIENT_ID is unset, auth is skipped (local dev only;
   never deploy without GOOGLE_CLIENT_ID set).

There is intentionally no static-token bypass: a shared secret that grants
access when no Authorization header is present makes the whole API effectively
public once that secret is configured.
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

    # Dev mode: skip auth only when Google is not configured (local dev).
    if not settings.GOOGLE_CLIENT_ID:
        request.state.email = "dev@breadfast.com"
        request.state.access_token = None
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"error": "Missing or invalid Authorization header. Sign in with Google."},
        )

    token = auth_header[7:]  # Strip "Bearer "

    # Validate as Google OAuth token
    user_info = _get_cached(token)
    if not user_info:
        user_info = _validate_google_token(token)
        if user_info is None:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or expired token. Please sign in again."},
            )
        # Token must be minted for THIS app, not just any Google token.
        if user_info.get("aud") != settings.GOOGLE_CLIENT_ID:
            return JSONResponse(
                status_code=401,
                content={"error": "Token was not issued for this application. Please sign in again."},
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
                # `aud` is the OAuth client id the token was issued to.
                "aud": data.get("aud", ""),
            }
    except Exception:
        return None
