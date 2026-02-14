"""Shared test fixtures.

Provides an async SQLite-backed session for testing ORM models and
ProvenanceGraph operations without requiring PostgreSQL.

SQLite supports recursive CTEs (3.8.3+) which is the core of F(u)/I(u).
PostgreSQL-specific features (partitioning, partial indexes, enum DDL) are
not exercised here — those are validated by the Alembic migration against
a real PG instance.
"""

import asyncio

import pytest
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from cortex.db.models.base import Base

# ── SQLite compatibility shims ──────────────────────────────────────────
# JSONB columns render as TEXT in SQLite (stores JSON strings, which is
# sufficient for ORM round-trip testing).


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Override pytest-asyncio default to use a session-scoped loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine():
    """Session-scoped async SQLite engine with all ORM tables created."""
    # Import all models to register them on Base.metadata.
    import cortex.db.models  # noqa: F401

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        # Enable WAL mode + foreign keys for SQLite.
        await conn.execute(
            __import__("sqlalchemy").text("PRAGMA journal_mode=WAL")
        )
        await conn.execute(
            __import__("sqlalchemy").text("PRAGMA foreign_keys=ON")
        )
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def session(async_engine):
    """Per-test async session wrapped in a transaction that rolls back.

    Each test gets a clean slate without needing to re-create tables.
    """
    async with async_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)

        # Nested transaction (savepoint) so that session.commit() inside
        # the code under test doesn't actually commit to the outer txn.
        nested = await conn.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(session, transaction):
            nonlocal nested
            if transaction.nested and not transaction._parent.nested:
                nested = conn.sync_connection.begin_nested()

        yield session

        await session.close()
        await trans.rollback()
