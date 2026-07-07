"""
Dashboard Authentication Module
- API key based auth (env var or auto-generated)
- Rate limiting on auth failures
- Cookie support for browser sessions
"""

import os
import secrets
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException, Response
from fastapi.responses import JSONResponse


# --- API Key Management ---

def _load_or_generate_api_key() -> str:
    """Load DASHBOARD_API_KEY from env, or generate a random one."""
    key = os.environ.get("DASHBOARD_API_KEY", "").strip()
    if key:
        print("[Auth] DASHBOARD_API_KEY loaded from environment variable.")
        return key

    key = secrets.token_urlsafe(32)
    print("=" * 60)
    print("[Auth] WARNING: DASHBOARD_API_KEY not set in environment.")
    print(f"[Auth] Generated random key for this session:")
    print(f"[Auth]   {key}")
    print(f"[Auth] Access dashboard at: http://<host>:8501/?key={key}")
    print(f"[Auth] Set DASHBOARD_API_KEY env var to use a persistent key.")
    print("=" * 60)
    return key


API_KEY: str = _load_or_generate_api_key()

# Cookie name for browser sessions
AUTH_COOKIE_NAME = "dashboard_auth"
# Cookie max age: 30 days
AUTH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60


# --- Rate Limiting ---

# Track failed auth attempts: {ip: [(timestamp, ...), ...]}
_failed_attempts: dict = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_FAILURES = 5


def _is_rate_limited(client_ip: str) -> bool:
    """Check if client IP has exceeded max auth failures in the window."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW

    # Clean old entries
    _failed_attempts[client_ip] = [
        ts for ts in _failed_attempts[client_ip] if ts > cutoff
    ]

    return len(_failed_attempts[client_ip]) >= RATE_LIMIT_MAX_FAILURES


def _record_failure(client_ip: str):
    """Record a failed auth attempt."""
    _failed_attempts[client_ip].append(time.time())


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For for proxied requests."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# --- Auth Extraction ---

def _extract_key_from_request(request: Request) -> Optional[str]:
    """
    Extract API key from request in priority order:
    1. Authorization: Bearer <key> header
    2. ?key=<key> query parameter
    3. dashboard_auth cookie
    """
    # 1. Authorization header
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    # 2. Query parameter
    key_param = request.query_params.get("key")
    if key_param:
        return key_param.strip()

    # 3. Cookie
    cookie_key = request.cookies.get(AUTH_COOKIE_NAME)
    if cookie_key:
        return cookie_key.strip()

    return None


def verify_key(provided_key: Optional[str]) -> bool:
    """Constant-time comparison of provided key against the API key."""
    if not provided_key:
        return False
    return secrets.compare_digest(provided_key, API_KEY)


# --- Public Auth Functions ---

def require_auth(request: Request) -> bool:
    """
    Verify authentication for a request. Raises HTTPException on failure.
    Returns True if authenticated.
    """
    client_ip = _get_client_ip(request)

    # Check rate limit first
    if _is_rate_limited(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many failed authentication attempts. Try again later."
        )

    provided_key = _extract_key_from_request(request)

    if verify_key(provided_key):
        return True

    # Record failure and reject
    if provided_key is not None:
        # Only record if they actually tried (not just missing key)
        _record_failure(client_ip)

    raise HTTPException(
        status_code=401,
        detail="Unauthorized. Provide API key via Authorization header, ?key= parameter, or cookie."
    )


def is_authenticated(request: Request) -> bool:
    """
    Check if request is authenticated without raising exceptions.
    Used for endpoints that work differently based on auth status.
    """
    client_ip = _get_client_ip(request)
    if _is_rate_limited(client_ip):
        return False

    provided_key = _extract_key_from_request(request)
    return verify_key(provided_key)


def set_auth_cookie(response: Response, key: str):
    """Set the auth cookie on a response for browser sessions."""
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=key,
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
