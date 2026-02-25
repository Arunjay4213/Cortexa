"""Debug script to trace memory ID mapping through the entire pipeline.

This will find where scores get assigned to the wrong memory IDs.
"""

import asyncio
import requests
from pprint import pprint

BASE_URL = "http://localhost:8001"


async def main():
    print("=" * 70)
    print("STEP 1: Seed 5 distinctive memories")
    print("=" * 70)

    # Known, distinctive content
    test_memories = [
        ("mem_A", "The company was founded in 2019 in San Francisco"),
        ("mem_B", "Our refund policy allows returns within 30 days"),
        ("mem_C", "The CEO's name is Alice Johnson"),
        ("mem_D", "We use Python 3.11 and FastAPI for the backend"),
        ("mem_E", "The annual revenue exceeded 50 million dollars"),
    ]

    agent_id = "debug_id_mapping"

    # Clear any existing memories for this agent
    print(f"\nClearing existing memories for agent: {agent_id}")

    # Seed memories and record IDs
    test_id_to_backend_id = {}
    test_id_to_content = {}
    insertion_order = []

    print("\nSeeding memories:")
    for test_id, content in test_memories:
        resp = requests.post(
            f"{BASE_URL}/api/v1/memories",
            json={"content": content, "agent_id": agent_id}
        )
        resp.raise_for_status()
        backend_id = resp.json()["id"]

        test_id_to_backend_id[test_id] = backend_id
        test_id_to_content[test_id] = content
        insertion_order.append((test_id, backend_id))

        print(f"  {test_id}: '{content[:40]}...' → {backend_id}")

    print("\n" + "=" * 70)
    print("STEP 2: Submit query that should use mem_B (refund policy)")
    print("=" * 70)

    query = "What is the refund policy?"
    response_text = "Our refund policy allows returns within 30 days of purchase."

    # Use ALL memories as retrieved (to see full attribution)
    retrieved_ids = [test_id_to_backend_id[tid] for tid, _ in test_memories]

    print(f"\nQuery: {query}")
    print(f"Response: {response_text}")
    print(f"\nRetrieved memory IDs (in order sent to API):")
    for i, (test_id, content) in enumerate(test_memories):
        backend_id = test_id_to_backend_id[test_id]
        print(f"  [{i}] {test_id} → {backend_id} → '{content[:40]}'")

    # Create transaction
    txn_resp = requests.post(
        f"{BASE_URL}/api/v1/transactions",
        json={
            "query_text": query,
            "response_text": response_text,
            "retrieved_memory_ids": retrieved_ids,
            "agent_id": agent_id,
            "model": "test"
        }
    )
    txn_resp.raise_for_status()
    txn_data = txn_resp.json()

    print("\n" + "=" * 70)
    print("STEP 3: Check attribution scores from backend")
    print("=" * 70)

    scores = txn_data["scores"]

    print(f"\nReceived {len(scores)} attribution scores from backend:")
    print(f"{'Index':<7} | {'Backend ID':<36} | {'Score':<7} | {'Content (first 50 chars)':<52}")
    print("-" * 110)

    # Build map of backend_id -> score
    backend_id_to_score = {}
    for i, score_obj in enumerate(scores):
        memory_id = score_obj["memory_id"]
        score_val = score_obj["score"]
        backend_id_to_score[memory_id] = score_val

        # Find which test memory this is
        test_id = None
        for tid, bid in test_id_to_backend_id.items():
            if bid == memory_id:
                test_id = tid
                break

        content_snippet = test_id_to_content.get(test_id, "UNKNOWN")[:50]
        print(f"{i:<7} | {memory_id:<36} | {score_val:<7.4f} | {content_snippet:<52}")

    print("\n" + "=" * 70)
    print("STEP 4: Verify score assignment")
    print("=" * 70)

    # Which memory got the highest score?
    max_score = -1
    max_score_backend_id = None
    max_score_test_id = None

    for test_id, backend_id in test_id_to_backend_id.items():
        score = backend_id_to_score.get(backend_id, 0.0)
        if score > max_score:
            max_score = score
            max_score_backend_id = backend_id
            max_score_test_id = test_id

    print(f"\nHighest score: {max_score:.4f}")
    print(f"  Assigned to: {max_score_test_id} (backend_id: {max_score_backend_id})")
    print(f"  Content: '{test_id_to_content[max_score_test_id]}'")

    if max_score_test_id == "mem_B":
        print(f"\n✅ CORRECT: Highest score assigned to mem_B (refund policy)")
    else:
        print(f"\n❌ BUG DETECTED: Highest score assigned to {max_score_test_id}, expected mem_B!")
        print(f"\n  Expected: mem_B should have highest score (refund policy)")
        print(f"  Got: {max_score_test_id} has highest score")

    # Show all scores in order
    print("\n" + "=" * 70)
    print("STEP 5: Score assignments (sorted by score, descending)")
    print("=" * 70)

    scores_sorted = []
    for test_id, backend_id in test_id_to_backend_id.items():
        score = backend_id_to_score.get(backend_id, 0.0)
        scores_sorted.append((score, test_id, backend_id, test_id_to_content[test_id]))

    scores_sorted.sort(reverse=True)

    print(f"{'Rank':<6} | {'Score':<7} | {'Test ID':<8} | {'Content':<60}")
    print("-" * 90)
    for rank, (score, test_id, backend_id, content) in enumerate(scores_sorted, 1):
        marker = "← EXPECTED" if test_id == "mem_B" else ""
        print(f"{rank:<6} | {score:<7.4f} | {test_id:<8} | {content[:58]} {marker}")

    print("\n" + "=" * 70)
    print("STEP 6: Check ordering bugs")
    print("=" * 70)

    # Check if scores are in the same order as retrieved_memory_ids
    print("\nOrder check:")
    print(f"{'Position':<10} | {'Sent to API':<40} | {'Received in response':<40}")
    print("-" * 95)

    for i in range(len(retrieved_ids)):
        sent_id = retrieved_ids[i]
        received_id = scores[i]["memory_id"] if i < len(scores) else "MISSING"

        # Find test IDs
        sent_test_id = None
        received_test_id = None
        for tid, bid in test_id_to_backend_id.items():
            if bid == sent_id:
                sent_test_id = tid
            if bid == received_id:
                received_test_id = tid

        match = "✅" if sent_id == received_id else "❌ MISMATCH"
        print(f"{i:<10} | {sent_test_id} ({sent_id[:8]}...) | {received_test_id} ({received_id[:8] if received_id != 'MISSING' else 'MISSING'}...) {match}")

    print("\n" + "=" * 70)
    print("STEP 7: Check database query ordering")
    print("=" * 70)

    # The key question: when we query memories by ID, what order do they come back?
    print("\nWe sent IDs in this order:")
    for i, backend_id in enumerate(retrieved_ids):
        test_id = [tid for tid, bid in test_id_to_backend_id.items() if bid == backend_id][0]
        print(f"  [{i}] {test_id} → {backend_id}")

    print("\nScores came back in this order:")
    for i, score_obj in enumerate(scores):
        backend_id = score_obj["memory_id"]
        test_id = [tid for tid, bid in test_id_to_backend_id.items() if bid == backend_id][0]
        print(f"  [{i}] {test_id} → {backend_id}")

    if retrieved_ids == [s["memory_id"] for s in scores]:
        print("\n✅ Order preserved: scores are in same order as retrieved_memory_ids")
    else:
        print("\n❌ ORDER BUG: scores are NOT in same order as retrieved_memory_ids")
        print("\nThis is the bug! The EAS computation assumes scores[i] corresponds")
        print("to retrieved_memory_ids[i], but the database query reordered them.")


if __name__ == "__main__":
    asyncio.run(main())
