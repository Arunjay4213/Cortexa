"""
Admin endpoints for managing API keys and users.

All endpoints require CORTEX_ADMIN_SECRET via Bearer token.

POST /api-keys        — create user (if needed) + new key; returns plaintext ONCE
GET  /api-keys        — list keys (prefix + name + last_used, never full key)
DELETE /api-keys/{id} — soft-revoke (sets revoked_at)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cortex.auth import generate_api_key, hash_key, key_prefix, require_admin_secret
from cortex.database import get_session
from cortex.db.tables import api_keys, users

router = APIRouter(tags=["api-keys"])


# ── Request / Response models ──────────────────────────────────────────────

class CreateApiKeyRequest(BaseModel):
    email: str
    name: str                        # human label for the key, e.g. "prod-bot"
    agent_id: Optional[str] = None   # None = all-agents access
    rate_limit_rpm: int = 60


class ApiKeyCreatedResponse(BaseModel):
    key: str                  # plaintext — shown ONCE, never stored
    id: str
    key_prefix: str
    name: str
    email: str
    agent_id: Optional[str]
    rate_limit_rpm: int
    created_at: datetime


class ApiKeyListItem(BaseModel):
    id: str
    key_prefix: str
    name: str
    email: str
    agent_id: Optional[str]
    rate_limit_rpm: int
    created_at: datetime
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    _: None = Depends(require_admin_secret),
    db: AsyncSession = Depends(get_session),
):
    """
    Create (or reuse) a user by email, then issue a new API key.
    The plaintext key is returned ONCE and never stored.
    """
    # Find or create user
    user_row = (
        await db.execute(select(users).where(users.c.email == body.email))
    ).first()

    if user_row is None:
        user_id = str(uuid.uuid4())
        # Derive name from email if not given a separate user name
        user_name = body.email.split("@")[0]
        await db.execute(
            users.insert().values(
                id=user_id,
                email=body.email,
                name=user_name,
                created_at=datetime.now(UTC),
            )
        )
    else:
        user_id = user_row.id

    # Generate plaintext key — hash before storing
    plaintext = generate_api_key()
    key_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    await db.execute(
        api_keys.insert().values(
            id=key_id,
            key_hash=hash_key(plaintext),
            key_prefix=key_prefix(plaintext),
            user_id=user_id,
            agent_id=body.agent_id,
            name=body.name,
            rate_limit_rpm=body.rate_limit_rpm,
            created_at=now,
        )
    )
    await db.commit()

    return ApiKeyCreatedResponse(
        key=plaintext,
        id=key_id,
        key_prefix=key_prefix(plaintext),
        name=body.name,
        email=body.email,
        agent_id=body.agent_id,
        rate_limit_rpm=body.rate_limit_rpm,
        created_at=now,
    )


@router.get("/api-keys", response_model=list[ApiKeyListItem])
async def list_api_keys(
    _: None = Depends(require_admin_secret),
    db: AsyncSession = Depends(get_session),
):
    """List all API keys (prefix + metadata only — never the full key or hash)."""
    rows = (
        await db.execute(
            select(
                api_keys.c.id,
                api_keys.c.key_prefix,
                api_keys.c.name,
                api_keys.c.agent_id,
                api_keys.c.rate_limit_rpm,
                api_keys.c.created_at,
                api_keys.c.last_used_at,
                api_keys.c.revoked_at,
                users.c.email,
            ).join(users, api_keys.c.user_id == users.c.id)
        )
    ).all()

    return [
        ApiKeyListItem(
            id=r.id,
            key_prefix=r.key_prefix,
            name=r.name,
            email=r.email,
            agent_id=r.agent_id,
            rate_limit_rpm=r.rate_limit_rpm,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
            revoked_at=r.revoked_at,
        )
        for r in rows
    ]


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    _: None = Depends(require_admin_secret),
    db: AsyncSession = Depends(get_session),
):
    """Soft-revoke an API key by setting revoked_at. Subsequent auth attempts return 401."""
    row = (
        await db.execute(select(api_keys).where(api_keys.c.id == key_id))
    ).first()

    if row is None:
        raise HTTPException(status_code=404, detail=f"API key {key_id!r} not found.")

    if row.revoked_at is not None:
        raise HTTPException(status_code=409, detail="API key is already revoked.")

    await db.execute(
        update(api_keys)
        .where(api_keys.c.id == key_id)
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()
