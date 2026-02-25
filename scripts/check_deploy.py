#!/usr/bin/env python3
"""
scripts/check_deploy.py — end-to-end deployment verification

Usage:
    CORTEX_ADMIN_SECRET=<secret> python scripts/check_deploy.py https://your-deploy.railway.app

What it does:
    1. GET  /healthz                        — basic liveness
    2. POST /api-keys                       — create a temporary test API key
    3. POST /api/v1/memories                — store a test memory
    4. GET  /api/v1/memories/search?q=...   — recall it via semantic search
    5. POST /api/v1/transactions            — run EAS attribution against the memory
    6. DELETE /api/v1/memories/{id}         — soft-delete the memory
    7. DELETE /api-keys/{id}                — revoke the test key

Prints a latency for each step, then "✓ All systems go" or exactly what failed.

Requirements: Python stdlib only (urllib + json). No dependencies to install.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


# ── Helpers ───────────────────────────────────────────────────────────────────

def _req(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    token: str | None = None,
    expected_status: int | tuple[int, ...] = 200,
) -> tuple[int, Any]:
    """Make an HTTP request, return (status_code, parsed_json_body)."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = e.code

    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = raw.decode(errors="replace")

    if isinstance(expected_status, int):
        expected_status = (expected_status,)
    if status not in expected_status:
        raise AssertionError(
            f"{method} {url}\n"
            f"  Expected status: {expected_status}\n"
            f"  Got status:      {status}\n"
            f"  Body:            {json.dumps(parsed, indent=2) if isinstance(parsed, (dict, list)) else parsed}"
        )
    return status, parsed


def _step(label: str) -> "StepTimer":
    return StepTimer(label)


class StepTimer:
    def __init__(self, label: str):
        self.label = label
        self._start = time.perf_counter()

    def ok(self, detail: str = "") -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        suffix = f"  {detail}" if detail else ""
        print(f"  ✓ {self.label:<40} {elapsed_ms:>6.0f}ms{suffix}")

    def fail(self, reason: str) -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        print(f"  ✗ {self.label:<40} {elapsed_ms:>6.0f}ms")
        print(f"    REASON: {reason}")
        raise SystemExit(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: CORTEX_ADMIN_SECRET=<secret> python scripts/check_deploy.py <base-url>")
        print("Example: CORTEX_ADMIN_SECRET=abc123 python scripts/check_deploy.py https://cortexos.fly.dev")
        sys.exit(1)

    base = sys.argv[1].rstrip("/")
    admin_secret = os.environ.get("CORTEX_ADMIN_SECRET", "")

    if not admin_secret:
        print("ERROR: Set CORTEX_ADMIN_SECRET environment variable.")
        sys.exit(1)

    print(f"\nChecking deployment at: {base}\n")

    test_key_id: str | None = None
    test_key: str | None = None
    memory_id: str | None = None

    # ── Step 1: Health check ──────────────────────────────────────────────────
    s = _step("GET /healthz")
    try:
        _, body = _req("GET", f"{base}/healthz", expected_status=200)
        if not isinstance(body, dict) or body.get("status") != "ok":
            s.fail(f"Expected {{\"status\": \"ok\"}}, got: {body}")
        s.ok()
    except AssertionError as e:
        s.fail(str(e))

    # ── Step 2: Create test API key ───────────────────────────────────────────
    s = _step("POST /api-keys  (create test key)")
    try:
        _, body = _req(
            "POST",
            f"{base}/api-keys",
            body={"email": "deploy-check@cortexos.local", "name": "deploy-check-key", "rate_limit_rpm": 60},
            token=admin_secret,
            expected_status=201,
        )
        if not isinstance(body, dict) or "key" not in body or "id" not in body:
            s.fail(f"Unexpected response shape: {body}")
        test_key = body["key"]
        test_key_id = body["id"]
        s.ok(f"prefix={body.get('key_prefix', '?')}")
    except AssertionError as e:
        s.fail(str(e))

    # ── Step 3: Store a memory ────────────────────────────────────────────────
    s = _step("POST /api/v1/memories  (store memory)")
    try:
        _, body = _req(
            "POST",
            f"{base}/api/v1/memories",
            body={
                "content": "CortexOS deploy-check: the capital of France is Paris.",
                "agent_id": "deploy-check-agent",
                "tier": "warm",
                "criticality": 0.5,
                "metadata": {},
            },
            token=test_key,
            expected_status=201,
        )
        # POST /memories returns a flat MemoryUnit dict
        if not isinstance(body, dict) or "id" not in body:
            s.fail(f"Unexpected response shape: {body}")
        memory_id = body["id"]
        s.ok(f"id={memory_id[:8]}...")
    except AssertionError as e:
        s.fail(str(e))

    # ── Step 4: Semantic search / recall ──────────────────────────────────────
    s = _step("GET /api/v1/memories/search  (recall)")
    try:
        _, body = _req(
            "GET",
            f"{base}/api/v1/memories/search?q=capital+of+France&agent_id=deploy-check-agent&top_k=5",
            token=test_key,
            expected_status=200,
        )
        if not isinstance(body, list):
            s.fail(f"Expected list, got: {type(body).__name__}: {body}")
        if not body:
            s.fail("Search returned empty results — memory may not have been stored or embedded correctly")

        # Check our memory is in the results
        ids_returned = [r["memory"]["id"] for r in body if isinstance(r, dict) and "memory" in r]
        if memory_id not in ids_returned:
            s.fail(
                f"Stored memory {memory_id[:8]}... not found in search results.\n"
                f"    Returned IDs: {[i[:8] for i in ids_returned]}"
            )
        top_sim = body[0].get("similarity", 0)
        s.ok(f"top similarity={top_sim:.4f}")
    except AssertionError as e:
        s.fail(str(e))

    # ── Step 5: Attribution (EAS transaction) ─────────────────────────────────
    s = _step("POST /api/v1/transactions  (EAS attribution)")
    try:
        _, body = _req(
            "POST",
            f"{base}/api/v1/transactions",
            body={
                "query_text": "What is the capital of France?",
                "response_text": "The capital of France is Paris.",
                "retrieved_memory_ids": [memory_id],
                "agent_id": "deploy-check-agent",
                "model": "deploy-check",
                "input_tokens": 8,
                "output_tokens": 7,
            },
            token=test_key,
            expected_status=201,
        )
        # Response: {"transaction": {...}, "scores": [...], "cost": {...}}
        if not isinstance(body, dict) or "transaction" not in body:
            s.fail(f"Unexpected response shape: {body}")
        txn_id = body["transaction"]["id"]
        scores = body.get("scores", [])
        top_score = scores[0]["score"] if scores else None
        s.ok(f"txn={txn_id[:8]}... EAS={top_score:.4f}" if top_score is not None else f"txn={txn_id[:8]}... no scores")
    except AssertionError as e:
        s.fail(str(e))

    # ── Step 6: Delete memory ─────────────────────────────────────────────────
    s = _step(f"DELETE /api/v1/memories/{{id}}  (cleanup)")
    try:
        _req("DELETE", f"{base}/api/v1/memories/{memory_id}", token=test_key, expected_status=204)
        s.ok()
    except AssertionError as e:
        s.fail(str(e))

    # ── Step 7: Revoke test API key ───────────────────────────────────────────
    s = _step(f"DELETE /api-keys/{{id}}  (revoke test key)")
    try:
        _req("DELETE", f"{base}/api-keys/{test_key_id}", token=admin_secret, expected_status=204)
        s.ok()
    except AssertionError as e:
        s.fail(str(e))

    # ── Done ──────────────────────────────────────────────────────────────────
    print(f"\n✓ All systems go  —  {base}\n")


if __name__ == "__main__":
    main()
