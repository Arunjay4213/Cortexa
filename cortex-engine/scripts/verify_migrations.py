#!/usr/bin/env python3
"""
CI migration verification script.

Creates a throw-away PostgreSQL database, runs `alembic upgrade head` against
it from a clean slate, then asserts that every expected table and column exists.
Exits 0 on success, 1 on any failure.

Usage:
    python scripts/verify_migrations.py
    python scripts/verify_migrations.py --db-url postgresql://user:pass@host/dbname

The target database is DROPPED AND RECREATED, so never point it at a database
you care about. The default name is `cortex_migration_verify`.

How it fits into CI:
    - Add as a step after the test suite:
        python cortex-engine/scripts/verify_migrations.py
    - Or gate on it before running the server in staging:
        python cortex-engine/scripts/verify_migrations.py --db-url $STAGING_VERIFY_URL
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse


# ── Expected schema ───────────────────────────────────────────────────────────
#
# Derived by reading every alembic migration in revision order (001 → 009).
# MAINTENANCE RULE: when you add a migration that creates a table or adds a
# column, add the corresponding entry here. The CI run will catch regressions
# on the next PR if you forget.

@dataclass
class TableSpec:
    name: str
    required_columns: list[str] = field(default_factory=list)


EXPECTED_TABLES: list[TableSpec] = [
    # ── 001: initial schema ────────────────────────────────────────────────
    TableSpec("memories", [
        "id", "content", "embedding", "tokens", "agent_id", "tier",
        "criticality", "metadata_", "retrieval_count",
        "created_at", "last_accessed", "deleted_at",
        # 003 additions
        "content_hash",
        # 004 additions
        "archived_at", "archive_reason",
    ]),
    TableSpec("transactions", [
        "id", "agent_id", "query_text", "response_text", "created_at",
        "query_embedding", "response_embedding", "retrieved_memory_ids",
    ]),
    TableSpec("attribution_scores", [
        "id", "transaction_id", "memory_id", "score",
    ]),
    TableSpec("memory_profiles", [
        "memory_id", "mean_attribution", "m2", "retrieval_count",
        "total_attribution", "trend", "updated_at",
    ]),
    TableSpec("contradictions", [
        "id", "memory_id_1", "memory_id_2", "type", "detected_at",
        # 003 additions
        "resolved_at", "resolved_by",
    ]),
    TableSpec("health_snapshots", [
        "id", "agent_id", "timestamp",
        # 006 additions
        "chi_score", "chi_grade",
        "accuracy_component", "freshness_component",
        "coverage_component", "consistency_component", "efficiency_component",
    ]),
    # ── 002: calibration + cost configs ───────────────────────────────────
    TableSpec("calibration_pairs", [
        "id", "memory_id", "transaction_id", "eas_score", "created_at",
    ]),
    TableSpec("agent_cost_configs", [
        "agent_id", "input_token_cost", "output_token_cost", "provider", "model_id",
        # 003 additions
        "description", "status",
    ]),
    # ── 004: lifecycle automation ──────────────────────────────────────────
    TableSpec("lifecycle_events", [
        "id", "agent_id", "action", "memory_id", "details", "created_at",
    ]),
    # ── 005: memory versioning ─────────────────────────────────────────────
    TableSpec("memory_snapshots", [
        "id", "name", "agent_id", "memory_count", "created_at",
    ]),
    TableSpec("memory_snapshot_entries", [
        "snapshot_id", "memory_id", "content", "tier",
    ]),
    TableSpec("memory_branches", [
        "id", "name", "parent_snapshot_id", "agent_id", "created_at",
    ]),
    # ── 008: API key authentication ────────────────────────────────────────
    TableSpec("users", [
        "id", "email", "name", "created_at",
    ]),
    TableSpec("api_keys", [
        "id", "key_hash", "key_prefix", "user_id", "agent_id",
        "name", "rate_limit_rpm", "created_at", "last_used_at", "revoked_at",
    ]),
]

# Columns added via ALTER TABLE — a subset of what's in EXPECTED_TABLES above,
# kept here as an explicit cross-reference to the migration that added them.
EXPECTED_ALTER_COLUMNS: list[tuple[str, str]] = [
    # (table, column) — from migration 003
    ("memories",           "content_hash"),
    ("contradictions",     "resolved_at"),
    ("contradictions",     "resolved_by"),
    ("agent_cost_configs", "description"),
    ("agent_cost_configs", "status"),
    # from migration 004
    ("memories",           "archived_at"),
    ("memories",           "archive_reason"),
    # from migration 006
    ("health_snapshots",   "chi_score"),
    ("health_snapshots",   "chi_grade"),
    ("health_snapshots",   "accuracy_component"),
    ("health_snapshots",   "freshness_component"),
    ("health_snapshots",   "coverage_component"),
    ("health_snapshots",   "consistency_component"),
    ("health_snapshots",   "efficiency_component"),
]


# ── DB helpers ────────────────────────────────────────────────────────────────

def _db_name(db_url: str) -> str:
    return urlparse(db_url).path.lstrip("/")


def _as_asyncpg_url(db_url: str, db_override: str | None = None) -> str:
    """Convert a postgresql:// URL to asyncpg format, optionally changing the DB."""
    url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    if db_override is not None:
        parsed = urlparse(url)
        url = urlunparse(parsed._replace(path=f"/{db_override}"))
    return url


def drop_and_create(db_url: str) -> None:
    """Drop (if exists) and recreate the target database using asyncpg."""
    import asyncio
    import asyncpg  # type: ignore

    name = _db_name(db_url)
    maintenance_url = _as_asyncpg_url(db_url, db_override="postgres")
    print(f"  Dropping and recreating '{name}'…")

    async def _admin() -> None:
        # autocommit=True is required for CREATE/DROP DATABASE
        conn = await asyncpg.connect(maintenance_url)
        try:
            # Terminate existing connections so DROP can proceed
            await conn.execute(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{name}' AND pid <> pg_backend_pid()
            """)
            await conn.execute(f"DROP DATABASE IF EXISTS {name}")
            await conn.execute(f"CREATE DATABASE {name}")
        finally:
            await conn.close()

    asyncio.run(_admin())


def run_alembic_upgrade(db_url: str, project_root: str) -> None:
    """Run `alembic upgrade head`, injecting the target DB URL via env var."""
    env = os.environ.copy()
    env["CORTEX_DATABASE_URL_SYNC"] = db_url
    print("  Running `alembic upgrade head`…")
    subprocess.run(
        ["python3.12", "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        env=env,
        check=True,
    )


def get_schema(db_url: str) -> tuple[set[str], dict[str, set[str]]]:
    """
    Return (table_names, {table: column_names}) by querying information_schema.

    Uses asyncpg (already a project dependency) so we don't need psycopg2.
    """
    import asyncio
    import asyncpg  # type: ignore

    async def _query() -> tuple[set[str], dict[str, set[str]]]:
        conn = await asyncpg.connect(_as_asyncpg_url(db_url))
        try:
            table_rows = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            col_rows = await conn.fetch(
                "SELECT table_name, column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public'"
            )
        finally:
            await conn.close()

        tables = {r["tablename"] for r in table_rows}
        cols: dict[str, set[str]] = {}
        for r in col_rows:
            cols.setdefault(r["table_name"], set()).add(r["column_name"])
        return tables, cols

    return asyncio.run(_query())


# ── Verification ──────────────────────────────────────────────────────────────

def verify_schema(
    tables: set[str],
    cols: dict[str, set[str]],
) -> list[str]:
    """Return failure messages (empty list = pass)."""
    failures: list[str] = []

    for spec in EXPECTED_TABLES:
        if spec.name not in tables:
            failures.append(f"MISSING TABLE:  {spec.name}")
            continue
        existing = cols.get(spec.name, set())
        for col in spec.required_columns:
            if col not in existing:
                failures.append(f"MISSING COLUMN: {spec.name}.{col}")

    for table, col in EXPECTED_ALTER_COLUMNS:
        if table not in tables:
            continue  # already reported as missing table
        if col not in cols.get(table, set()):
            failures.append(f"MISSING COLUMN: {table}.{col}")

    return failures


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify alembic migrations on a fresh database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db-url",
        default="postgresql://postgres@localhost:5432/cortex_migration_verify",
        help="Sync postgresql:// URL of the throw-away verification database",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Path to cortex-engine root (default: parent of the scripts/ directory)",
    )
    parser.add_argument(
        "--skip-recreate",
        action="store_true",
        help="Skip drop/recreate — use the DB as-is (useful for debugging)",
    )
    args = parser.parse_args()

    project_root = args.project_root or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    sep = "=" * 60
    print(sep)
    print("CortexOS migration verification")
    print(f"  DB URL:       {args.db_url}")
    print(f"  Project root: {project_root}")
    print(sep)

    # ── Step 1: fresh database ────────────────────────────────────────────
    if args.skip_recreate:
        print("\n[1/3] Skipping DB recreate (--skip-recreate)")
    else:
        print("\n[1/3] Recreating verification database…")
        try:
            drop_and_create(args.db_url)
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: failed to recreate database.\n{exc.stderr}", file=sys.stderr)
            return 1

    # ── Step 2: alembic upgrade head ──────────────────────────────────────
    print("\n[2/3] Running migrations…")
    try:
        run_alembic_upgrade(args.db_url, project_root)
    except subprocess.CalledProcessError as exc:
        print("ERROR: `alembic upgrade head` failed.", file=sys.stderr)
        return 1

    # ── Step 3: verify schema ─────────────────────────────────────────────
    print("\n[3/3] Verifying schema…")
    try:
        tables, cols = get_schema(args.db_url)
    except Exception as exc:
        print(f"ERROR: could not query schema: {exc}", file=sys.stderr)
        return 1

    print(f"  Tables found ({len(tables)}): {', '.join(sorted(tables))}")

    failures = verify_schema(tables, cols)

    if failures:
        print(f"\n  {'─' * 40}")
        print("  FAILURES:")
        for msg in failures:
            print(f"    ✗ {msg}")
        print(f"\n  {len(failures)} check(s) failed — migrations are incomplete.")
        return 1

    print(f"\n  ✓ All {len(EXPECTED_TABLES)} expected tables present.")
    print("  ✓ All required columns present.")
    print(f"\n{sep}")
    print("Migration verification PASSED.")
    print(sep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
