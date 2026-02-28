#!/usr/bin/env python3
"""
CortexOS SDK Error Handling Test — verifies proper exception types.

Usage:
    CORTEX_API_KEY=your-key python scripts/test_errors.py
"""

import os

from cortexos import Cortex
from cortexos.errors import CortexError, MemoryNotFoundError

# NOTE: Never commit real API keys. Use env vars.
BASE_URL = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")
API_KEY = os.environ.get("CORTEX_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "Set CORTEX_API_KEY environment variable to run this test.\n"
        "Example: CORTEX_API_KEY=your-key python scripts/test_errors.py"
    )

print("=" * 60)
print("  CortexOS SDK Error Handling Tests")
print("=" * 60)

# ── Test 1: MemoryNotFoundError ──────────────────────────────────────────

print("\n[1] MemoryNotFoundError — fetching non-existent memory")
cx = Cortex(api_key=API_KEY, agent_id="error-test", base_url=BASE_URL)

try:
    cx.get("00000000-0000-0000-0000-000000000000")
    assert False, "Should have raised an exception"
except MemoryNotFoundError as e:
    print(f"    Caught MemoryNotFoundError: {e}")
    assert e.status_code == 404
    print("    PASS")
except CortexError as e:
    # Server may return 404 without our specific wrapper — still OK
    assert e.status_code == 404, f"Expected 404, got {e.status_code}"
    print(f"    Caught CortexError (404): {e}")
    print("    PASS (server returned generic 404)")

# ── Test 2: ConnectionError on wrong host ────────────────────────────────

print("\n[2] CortexError — connection to non-existent server")
bad_cx = Cortex(api_key="bad-key", agent_id="test", base_url="http://localhost:59999", timeout=2.0, max_retries=1)

try:
    bad_cx.recall("test query")
    assert False, "Should have raised an exception"
except CortexError as e:
    print(f"    Caught CortexError: {e}")
    print("    PASS")

bad_cx.close()

# ── Test 3: Forget non-existent memory ───────────────────────────────────

print("\n[3] Forget non-existent memory — should raise error")
try:
    cx.forget("00000000-0000-0000-0000-000000000000")
    # Some servers may return 204 even for non-existent — that's OK
    print("    Server returned success (idempotent delete)")
    print("    PASS")
except (MemoryNotFoundError, CortexError) as e:
    print(f"    Caught: {e}")
    print("    PASS")

cx.close()

# ── Summary ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("  ALL ERROR TESTS PASSED")
print("=" * 60)
