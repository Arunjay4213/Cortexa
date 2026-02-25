"""
python -m cortex.seed_admin

Idempotent seed script: creates (or reuses) an admin user and issues a
fresh API key. Prints the plaintext key to stdout — save it immediately.

Usage:
    cd cortex-engine
    python -m cortex.seed_admin
    python -m cortex.seed_admin --email admin@example.com --name "CI key"
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from cortex.auth import generate_api_key, hash_key, key_prefix
from cortex.config import settings
from cortex.db.tables import api_keys, users

_ADMIN_EMAIL = "admin@cortexos.local"
_ADMIN_KEY_NAME = "default-admin-key"


async def seed(email: str, key_name: str) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Find or create user
        user_row = (
            await db.execute(select(users).where(users.c.email == email))
        ).first()

        if user_row is None:
            user_id = str(uuid.uuid4())
            await db.execute(
                users.insert().values(
                    id=user_id,
                    email=email,
                    name=email.split("@")[0],
                    created_at=datetime.now(UTC),
                )
            )
            print(f"Created user: {email} (id={user_id})")
        else:
            user_id = user_row.id
            print(f"Reusing existing user: {email} (id={user_id})")

        # Always create a new key (idempotent on user, not on key)
        plaintext = generate_api_key()
        key_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        await db.execute(
            api_keys.insert().values(
                id=key_id,
                key_hash=hash_key(plaintext),
                key_prefix=key_prefix(plaintext),
                user_id=user_id,
                agent_id=None,     # admin key = all-agent access
                name=key_name,
                rate_limit_rpm=600,  # generous limit for admin key
                created_at=now,
            )
        )
        await db.commit()

    await engine.dispose()

    print()
    print("=" * 60)
    print("  API KEY CREATED — SAVE THIS NOW, IT WON'T BE SHOWN AGAIN")
    print("=" * 60)
    print(f"  Key:        {plaintext}")
    print(f"  Prefix:     {key_prefix(plaintext)}")
    print(f"  Key ID:     {key_id}")
    print(f"  Rate limit: 600 req/min")
    print("=" * 60)
    print()
    print("Usage:")
    print(f'  curl -H "Authorization: Bearer {plaintext}" http://localhost:8000/api/v1/memories')
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a CortexOS admin API key")
    parser.add_argument("--email", default=_ADMIN_EMAIL, help="Admin user email")
    parser.add_argument("--name", default=_ADMIN_KEY_NAME, help="Key display name")
    args = parser.parse_args()
    asyncio.run(seed(args.email, args.name))


if __name__ == "__main__":
    main()
