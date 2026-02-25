"""
API key authentication dependency + in-memory sliding-window rate limiter.

Usage in route handlers:
    from cortex.auth import require_api_key, ApiKeyRecord

    @router.get("/something")
    async def my_route(
        key: ApiKeyRecord = Depends(require_api_key),
        db: AsyncSession = Depends(get_session),
    ):
        # key.agent_id is set if the key is scoped — use it to filter DB queries
        ...

Admin endpoints use require_admin_secret instead.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.config import settings
from cortex.database import get_session
from cortex.db.tables import api_keys

# ── Key format ─────────────────────────────────────────────────────────────

_KEY_PREFIX = "sk-cortex-"
_KEY_PREFIX_DISPLAY_LEN = 12  # "sk-cortex-ab" (first 12 chars of full key)


def generate_api_key() -> str:
    """Generate a new plaintext API key. NEVER store this — hash it."""
    return _KEY_PREFIX + secrets.token_hex(16)


def hash_key(plaintext: str) -> str:
    """SHA-256 hash of the plaintext key (what we store in the DB)."""
    return hashlib.sha256(plaintext.encode()).hexdigest()


def key_prefix(plaintext: str) -> str:
    """First 12 characters of the key for display (non-secret)."""
    return plaintext[:_KEY_PREFIX_DISPLAY_LEN]


# ── Rate limiter (in-process sliding window, no Redis) ─────────────────────

@dataclass
class _RateLimiterWindow:
    """Per-key sliding window: stores timestamps of recent requests."""
    timestamps: deque = field(default_factory=deque)


class SlidingWindowRateLimiter:
    """
    Thread-safe* sliding window rate limiter keyed by api_key id.

    *asyncio single-threaded — no locking needed.
    """

    def __init__(self) -> None:
        self._windows: dict[str, _RateLimiterWindow] = {}

    def check(self, key_id: str, rate_limit_rpm: int) -> tuple[bool, int]:
        """
        Return (allowed, remaining).
        Evicts timestamps older than 60 seconds before checking.
        """
        now = time.monotonic()
        window_start = now - 60.0

        if key_id not in self._windows:
            self._windows[key_id] = _RateLimiterWindow()

        win = self._windows[key_id]

        # Evict expired entries
        while win.timestamps and win.timestamps[0] < window_start:
            win.timestamps.popleft()

        count = len(win.timestamps)
        remaining = max(0, rate_limit_rpm - count - 1)

        if count >= rate_limit_rpm:
            return False, 0

        win.timestamps.append(now)
        return True, remaining


# Singleton — shared across all requests in the process
_rate_limiter = SlidingWindowRateLimiter()


# ── Auth data ──────────────────────────────────────────────────────────────

@dataclass
class ApiKeyRecord:
    """Resolved, validated API key passed to route handlers via Depends."""
    id: str
    user_id: str
    agent_id: Optional[str]   # None = all agents; set = scoped
    name: str
    rate_limit_rpm: int


# ── HTTP Bearer extractor ─────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_session),
) -> ApiKeyRecord:
    """
    FastAPI dependency — validates Bearer token, enforces rate limit,
    injects ApiKeyRecord into the route handler.

    Raises 401 if missing/invalid/revoked.
    Raises 429 if rate limit exceeded.
    Sets X-RateLimit-* headers on the response.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Include 'Authorization: Bearer sk-cortex-...' header.",
        )

    token = credentials.credentials
    token_hash = hash_key(token)

    row = (
        await db.execute(
            select(api_keys).where(api_keys.c.key_hash == token_hash)
        )
    ).first()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid API key.")

    if row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="API key has been revoked.")

    # ── Rate limit ─────────────────────────────────────────────────────────
    allowed, remaining = _rate_limiter.check(row.id, row.rate_limit_rpm)

    # Always add rate-limit headers to the response
    request.state.rate_limit_limit = row.rate_limit_rpm
    request.state.rate_limit_remaining = remaining

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded.",
            headers={
                "Retry-After": "60",
                "X-RateLimit-Limit": str(row.rate_limit_rpm),
                "X-RateLimit-Remaining": "0",
            },
        )

    # ── Update last_used_at (fire-and-forget) ──────────────────────────────
    await db.execute(
        update(api_keys)
        .where(api_keys.c.id == row.id)
        .values(last_used_at=datetime.now(UTC))
    )
    await db.commit()

    return ApiKeyRecord(
        id=row.id,
        user_id=row.user_id,
        agent_id=row.agent_id,
        name=row.name,
        rate_limit_rpm=row.rate_limit_rpm,
    )


# ── Rate-limit response middleware helper ─────────────────────────────────

async def add_rate_limit_headers(request: Request, call_next):
    """Starlette middleware that adds X-RateLimit-* headers from request.state."""
    response = await call_next(request)
    limit = getattr(request.state, "rate_limit_limit", None)
    remaining = getattr(request.state, "rate_limit_remaining", None)
    if limit is not None:
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


# ── Agent-ID scoping helper ────────────────────────────────────────────────

def resolve_agent_id(
    requested: Optional[str],
    key: ApiKeyRecord,
) -> Optional[str]:
    """
    If the API key is scoped to a specific agent_id, ALWAYS return that agent_id
    regardless of what the caller requested. If the key is unscoped (agent_id=None),
    pass through the requested value.
    """
    if key.agent_id is not None:
        return key.agent_id
    return requested


# ── Admin secret dependency ────────────────────────────────────────────────

async def require_admin_secret(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    """
    Protects admin endpoints with CORTEX_ADMIN_SECRET.
    Uses Bearer auth for consistency with API key endpoints.
    """
    secret = settings.admin_secret
    if secret == "changeme-set-CORTEX_ADMIN_SECRET":
        raise HTTPException(
            status_code=503,
            detail="Admin secret not configured. Set CORTEX_ADMIN_SECRET env var.",
        )
    if credentials is None or credentials.credentials != secret:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin secret.",
        )
