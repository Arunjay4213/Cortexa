import hashlib
import logging
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger("cortexos.auth")

security = HTTPBearer(auto_error=False)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    return f"cx_{secrets.token_urlsafe(32)}"


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    """
    Validate Bearer token against admin_secret or database api_keys.
    Returns the api_key_id if authenticated, or None if auth is disabled.
    """
    settings = request.app.state.settings

    # If no admin secret is configured, refuse all requests
    if not settings.admin_secret:
        logger.critical(
            "CORTEX_ADMIN_SECRET is not set. "
            "All requests are being rejected. "
            "Set CORTEX_ADMIN_SECRET in your environment."
        )
        raise HTTPException(
            status_code=503,
            detail="Server is not configured. "
                   "Administrator must set CORTEX_ADMIN_SECRET.",
        )

    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    token = credentials.credentials

    # Check against admin secret first
    if token == settings.admin_secret:
        return "admin"

    # Check against database api_keys
    db = getattr(request.app.state, "db", None)
    if db is not None:
        from app.db.tables import api_keys
        from sqlalchemy import select

        async with db() as session:
            key_hash = hash_key(token)
            result = await session.execute(
                select(api_keys.c.id).where(
                    api_keys.c.key_hash == key_hash,
                    api_keys.c.revoked_at.is_(None),
                )
            )
            row = result.first()
            if row:
                return row.id

    raise HTTPException(status_code=401, detail="Invalid API key")
