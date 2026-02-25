"""All tunables for the CortexOS stress test suite."""

from __future__ import annotations

import os

BASE_URL = "http://localhost:8000"


def auth_headers() -> dict[str, str]:
    """Return Authorization headers for inline httpx clients.

    Reads CORTEX_STRESS_API_KEY from the environment (set by conftest via
    harness.set_session_api_key once the session key is provisioned).
    Returns an empty dict if no key is available (e.g. server has no auth).
    """
    key = os.environ.get("CORTEX_STRESS_API_KEY", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


class StressConfig:
    # ── Concurrency ──────────────────────────────────────────────────────
    WORKER_COUNTS = [1, 4, 8, 16, 32]
    LIGHT_WORKERS = [1, 4, 8]          # for quick sweeps

    # ── Dataset scale ────────────────────────────────────────────────────
    MEMORY_COUNTS = [10, 100, 500, 1_000, 5_000]
    SMALL_SCALE = 50
    MEDIUM_SCALE = 500
    LARGE_SCALE = 2_000

    # ── Timeouts (seconds) ───────────────────────────────────────────────
    SINGLE_OP_TIMEOUT_S = 30
    BATCH_TIMEOUT_S = 300
    ENDURANCE_DURATION_S = 3_600       # 1 hour (use 600 for quick runs)
    ENDURANCE_QUICK_S = 120            # 2-min quick endurance

    # ── Rate limiting (ops/sec) ──────────────────────────────────────────
    TARGET_RPS = [10, 50, 100]

    # ── Memory sizes ─────────────────────────────────────────────────────
    MEMORY_TEXT_LENGTHS = [50, 200, 1_000, 5_000]  # chars
    EMBEDDING_DIMS = [384]              # system uses 384

    # ── Agent counts ─────────────────────────────────────────────────────
    AGENT_COUNTS = [1, 5, 10, 25]

    # ── Attribution ──────────────────────────────────────────────────────
    CONTEXT_WINDOW_SIZES = [5, 10, 25, 50]

    # ── SLA thresholds ───────────────────────────────────────────────────
    MAX_P95_MS = 5_000                  # 5 seconds
    MAX_P99_MS = 15_000                 # 15 seconds
    MAX_ERROR_RATE = 0.05               # 5%
    MIN_RECALL_AT_10 = 0.70             # retrieval quality floor
    MAX_TTL_ACCURACY_MS = 2_000         # ±2 seconds

    # ── HTTP client settings ─────────────────────────────────────────────
    HTTP_TIMEOUT = 30.0
    HTTP_CONNECT_TIMEOUT = 5.0
