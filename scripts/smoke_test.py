"""
CortexOS production smoke test.

Uses the actual SDK. Creates API keys, memories, runs EAS + CAMA attribution.
Verifies hallucination detection and dead memory detection.
Cleans up everything it creates.
Exits 0 on all pass, 1 on any fail.
"""

import os
import sys
import time

import httpx

BASE_URL = "http://localhost:8000"
ADMIN_SECRET = os.environ.get("CORTEX_ADMIN_SECRET", "dev-admin-secret")
AGENT_ID = "smoke-test-agent"

results: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    msg = f"  {status}  {name}"
    if detail and not passed:
        msg += f" -- {detail}"
    print(msg)
    results.append((name, passed, detail))


def main():
    print("CortexOS smoke test")
    print("=" * 50)

    # ── 0. Check server is running ────────────────────────────────────
    try:
        r = httpx.get(f"{BASE_URL}/healthz", timeout=5)
        check("healthz", r.status_code == 200)
    except Exception as e:
        check("healthz", False, str(e))
        print("\nServer not running. Start with: bash start.sh")
        sys.exit(1)

    # ── 1. Create API key via admin endpoint ──────────────────────────
    api_key = None
    key_id = None
    try:
        r = httpx.post(
            f"{BASE_URL}/api-keys",
            headers={"Authorization": f"Bearer {ADMIN_SECRET}"},
            json={
                "email": "smoke@test.local",
                "name": "smoke-test-key",
                "rate_limit_rpm": 600,
            },
            timeout=10,
        )
        check("create_api_key", r.status_code == 201, f"status={r.status_code} body={r.text[:200]}")
        if r.status_code == 201:
            data = r.json()
            api_key = data["key"]
            key_id = data["id"]
    except Exception as e:
        check("create_api_key", False, str(e))

    if not api_key:
        print("\nCannot proceed without API key")
        sys.exit(1)

    # ── 2. Use the SDK ────────────────────────────────────────────────
    from cortexos import Cortex, CAMAAttribution

    cx = Cortex(agent_id=AGENT_ID, api_key=api_key, base_url=BASE_URL, timeout=30)
    memory_ids = []

    # ── 3. Store 5 memories ───────────────────────────────────────────
    memories_data = [
        "John reported that his dashboard loads slowly since Feb 15.",
        "John is subscribed to the Pro plan with 3 seats.",
        "John's account was created in January 2024.",
        "John prefers email communication over phone.",
        "Global quarterly revenue reached $2.4M in Q3 2025.",
    ]

    for i, content in enumerate(memories_data):
        try:
            mem = cx.remember(content, importance=0.7)
            memory_ids.append(mem.id)
            check(f"store_memory_{i+1}", True)
        except Exception as e:
            check(f"store_memory_{i+1}", False, str(e))

    check("stored_5_memories", len(memory_ids) == 5, f"got {len(memory_ids)}")

    # ── 4. Recall ─────────────────────────────────────────────────────
    try:
        results_recall = cx.recall("What issues has John reported?", top_k=5)
        check("recall", len(results_recall) > 0, f"got {len(results_recall)} results")
        # The dashboard loading memory should be top or near top
        recalled_ids = [r.memory.id for r in results_recall]
        check("recall_relevance", memory_ids[0] in recalled_ids, "dashboard memory not in recall")
    except Exception as e:
        check("recall", False, str(e))
        check("recall_relevance", False, "skipped")

    # ── 5. EAS attribution ────────────────────────────────────────────
    txn_id = None
    try:
        attr = cx.attribute(
            query="What issues has John reported?",
            response="John reported slow dashboard loading since February 15th. He is on the Pro plan.",
            memory_ids=memory_ids,
        )
        txn_id = attr.transaction_id
        check("eas_attribution", True)
        check("eas_has_scores", len(attr.scores) > 0, f"got {len(attr.scores)} scores")
        total = sum(attr.scores.values())
        check("eas_scores_sum_to_1", abs(total - 1.0) < 0.05, f"sum={total:.4f}")
    except Exception as e:
        check("eas_attribution", False, str(e))
        check("eas_has_scores", False, "skipped")
        check("eas_scores_sum_to_1", False, "skipped")

    # ── 6. CAMA attribution ───────────────────────────────────────────
    if txn_id:
        try:
            cama = cx.cama_attribute(txn_id)
            check("cama_attribution", True)
            check("cama_has_claims", cama.num_claims > 0, f"got {cama.num_claims} claims")
            check("cama_has_scores", len(cama.scores) > 0, f"got {len(cama.scores)} scores")
            check("cama_method", cama.method == "cama", f"got {cama.method}")
        except Exception as e:
            check("cama_attribution", False, str(e))
            check("cama_has_claims", False, "skipped")
            check("cama_has_scores", False, "skipped")
            check("cama_method", False, "skipped")
    else:
        for name in ["cama_attribution", "cama_has_claims", "cama_has_scores", "cama_method"]:
            check(name, False, "no transaction_id from EAS")

    # ── 7. Hallucination detection ────────────────────────────────────
    # Create a new transaction with a fabricated claim in the response
    hallucination_txn_id = None
    try:
        attr2 = cx.attribute(
            query="Tell me about John's account",
            response="John is on the Pro plan. John has filed a lawsuit against the company. Global revenue was $2.4M.",
            memory_ids=memory_ids,
        )
        hallucination_txn_id = attr2.transaction_id
        check("hallucination_setup", True)
    except Exception as e:
        check("hallucination_setup", False, str(e))

    if hallucination_txn_id:
        try:
            cama2 = cx.cama_attribute(hallucination_txn_id)
            # "filed a lawsuit" is completely fabricated — should be hallucinated
            check("hallucination_index_positive", cama2.hallucination_index > 0,
                  f"index={cama2.hallucination_index}")
            has_unsupported = len(cama2.unsupported_claims) > 0
            check("unsupported_claims_found", has_unsupported,
                  f"got {len(cama2.unsupported_claims)} unsupported")
        except Exception as e:
            check("hallucination_index_positive", False, str(e))
            check("unsupported_claims_found", False, "skipped")
    else:
        check("hallucination_index_positive", False, "no txn")
        check("unsupported_claims_found", False, "no txn")

    # ── 8. Dead memory detection ──────────────────────────────────────
    # Memory 5 (revenue) should be dead when asking about John's issues
    if txn_id:
        try:
            cama3 = cx.cama_attribute(txn_id)
            # revenue memory should be dead or have 0 score
            revenue_id = memory_ids[4]  # "Global quarterly revenue..."
            revenue_score = cama3.scores.get(revenue_id, 0.0)
            is_dead = revenue_id in cama3.dead_memories or revenue_score == 0.0
            check("dead_memory_detected", is_dead,
                  f"revenue_score={revenue_score}, dead_memories={cama3.dead_memories}")
        except Exception as e:
            check("dead_memory_detected", False, str(e))
    else:
        check("dead_memory_detected", False, "no txn")

    # ── 9. Cleanup ────────────────────────────────────────────────────
    cleanup_ok = True
    for mid in memory_ids:
        try:
            cx.forget(mid)
        except Exception as e:
            cleanup_ok = False
    check("cleanup_memories", cleanup_ok)

    # Revoke the API key
    try:
        r = httpx.delete(
            f"{BASE_URL}/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {ADMIN_SECRET}"},
            timeout=10,
        )
        check("cleanup_api_key", r.status_code == 204, f"status={r.status_code}")
    except Exception as e:
        check("cleanup_api_key", False, str(e))

    cx.close()

    # ── Summary ───────────────────────────────────────────────────────
    print("=" * 50)
    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    print(f"{passed} passed, {failed} failed")

    if failed > 0:
        print("\nFailed tests:")
        for name, p, detail in results:
            if not p:
                print(f"  - {name}: {detail}")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
