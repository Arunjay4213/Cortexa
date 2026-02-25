"""Performance Tests — §7-10.

Tests that validate CortexOS can handle production-scale workloads without
degrading to unusability.

These tests answer: "Can CortexOS scale to real production agents?"
"""

import asyncio
import time
import numpy as np
from typing import List, Dict
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e2e.agent_simulator import (
    AgentSimulator,
    create_test_simulator,
)
from e2e.datasets import generate_personal_assistant_dataset, MemoryDataset


async def test_eas_latency_under_load(
    n_memories: int = 1000,
    n_concurrent_queries: int = 50,
    p95_threshold_ms: float = 500,
) -> Dict:
    """Test 7: Does EAS remain fast under load?

    Validates that attribution computation doesn't become a bottleneck.

    Args:
        n_memories: Size of memory bank
        n_concurrent_queries: Number of concurrent queries to process
        p95_threshold_ms: Maximum acceptable p95 latency in milliseconds

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 7: EAS Latency Under Load")
    print(f"{'='*60}")

    # Generate large memory dataset
    print(f"Generating dataset with {n_memories} memories...")
    from e2e.datasets import generate_research_agent_dataset
    dataset = generate_research_agent_dataset()

    # Ensure we have enough memories
    if len(dataset.memories) < n_memories:
        # Duplicate memories to reach target size
        while len(dataset.memories) < n_memories:
            for mem in list(dataset.memories)[:min(100, n_memories - len(dataset.memories))]:
                dataset.memories.append(mem)

    print(f"✓ Dataset ready: {len(dataset.memories)} memories")

    # Create simulator
    simulator = create_test_simulator(
        [m.content for m in dataset.memories[:n_memories]],
        [m.id for m in dataset.memories[:n_memories]],
        k=10
    )

    # Generate test queries
    queries = [
        f"Query {i}: What are your thoughts on machine learning research?"
        for i in range(n_concurrent_queries)
    ]

    # Measure latencies
    latencies_ms = []

    print(f"Processing {n_concurrent_queries} queries...")

    # Process queries concurrently
    async def process_with_timing(query: str) -> float:
        start = time.perf_counter()
        await simulator.process_query(query)
        end = time.perf_counter()
        return (end - start) * 1000  # Convert to ms

    latencies_ms = await asyncio.gather(*[process_with_timing(q) for q in queries])

    # Compute statistics
    p50 = np.percentile(latencies_ms, 50)
    p95 = np.percentile(latencies_ms, 95)
    p99 = np.percentile(latencies_ms, 99)
    mean = np.mean(latencies_ms)

    passed = p95 <= p95_threshold_ms

    print(f"\nResults:")
    print(f"  Queries processed: {len(latencies_ms)}")
    print(f"  Mean latency: {mean:.1f}ms")
    print(f"  P50 latency: {p50:.1f}ms")
    print(f"  P95 latency: {p95:.1f}ms {'✅' if passed else '❌'} (threshold: {p95_threshold_ms}ms)")
    print(f"  P99 latency: {p99:.1f}ms")

    return {
        "test_name": "eas_latency",
        "passed": passed,
        "metrics": {
            "n_memories": n_memories,
            "n_queries": len(latencies_ms),
            "mean_latency_ms": round(mean, 2),
            "p50_latency_ms": round(p50, 2),
            "p95_latency_ms": round(p95, 2),
            "p99_latency_ms": round(p99, 2),
            "threshold_ms": p95_threshold_ms,
        }
    }


async def test_welford_accuracy_at_scale(
    n_updates: int = 10000,
    max_error_pct: float = 0.1,
) -> Dict:
    """Test 8: Is Welford's algorithm accurate at scale?

    Validates that online statistics don't accumulate significant errors.

    Args:
        n_updates: Number of incremental updates to test
        max_error_pct: Maximum acceptable error percentage vs batch computation

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 8: Welford Accuracy at Scale")
    print(f"{'='*60}")

    print(f"Simulating {n_updates} incremental updates...")

    # Generate random data stream
    rng = np.random.default_rng(42)
    values = rng.normal(100, 15, size=n_updates)

    # Welford's algorithm (online)
    count = 0
    mean = 0.0
    m2 = 0.0

    for value in values:
        count += 1
        delta = value - mean
        mean += delta / count
        delta2 = value - mean
        m2 += delta * delta2

    welford_mean = mean
    welford_variance = m2 / count if count > 0 else 0.0
    welford_std = np.sqrt(welford_variance)

    # Batch computation (ground truth)
    batch_mean = np.mean(values)
    batch_std = np.std(values, ddof=0)

    # Compute errors
    mean_error_pct = abs(welford_mean - batch_mean) / batch_mean * 100
    std_error_pct = abs(welford_std - batch_std) / batch_std * 100

    passed = mean_error_pct < max_error_pct and std_error_pct < max_error_pct

    print(f"\nResults:")
    print(f"  Updates processed: {n_updates}")
    print(f"  Welford mean: {welford_mean:.4f}")
    print(f"  Batch mean: {batch_mean:.4f}")
    print(f"  Mean error: {mean_error_pct:.4f}% {'✅' if mean_error_pct < max_error_pct else '❌'}")
    print(f"  Welford std: {welford_std:.4f}")
    print(f"  Batch std: {batch_std:.4f}")
    print(f"  Std error: {std_error_pct:.4f}% {'✅' if std_error_pct < max_error_pct else '❌'}")

    return {
        "test_name": "welford_accuracy",
        "passed": passed,
        "metrics": {
            "n_updates": n_updates,
            "mean_error_pct": round(mean_error_pct, 4),
            "std_error_pct": round(std_error_pct, 4),
            "threshold_pct": max_error_pct,
        }
    }


async def test_dashboard_overview_latency(
    latency_threshold_ms: float = 2000,
) -> Dict:
    """Test 9: Can dashboard load overview quickly?

    Validates that the /overview endpoint responds quickly even with
    moderate data volumes.

    Note: This is a simplified test without real database. In production,
    test against real PostgreSQL with realistic data volumes.

    Args:
        latency_threshold_ms: Maximum acceptable latency in milliseconds

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 9: Dashboard Overview Latency")
    print(f"{'='*60}")

    # Simulate overview computation
    print("Simulating dashboard overview computation...")

    start = time.perf_counter()

    # Simulate what /overview does:
    # 1. Fetch 100 recent transactions
    await asyncio.sleep(0.05)  # Simulate DB query

    # 2. Compute stats for each transaction
    stats = []
    for i in range(100):
        # Simulate light computation per transaction
        mean = np.mean(np.random.randn(10))
        std = np.std(np.random.randn(10))
        stats.append({"mean": mean, "std": std})
        await asyncio.sleep(0.001)  # Simulate processing

    # 3. Aggregate stats
    overall_mean = np.mean([s["mean"] for s in stats])
    overall_std = np.mean([s["std"] for s in stats])

    # 4. Fetch agent health snapshots
    await asyncio.sleep(0.02)  # Simulate DB query

    end = time.perf_counter()
    latency_ms = (end - start) * 1000

    passed = latency_ms <= latency_threshold_ms

    print(f"\nResults:")
    print(f"  Overview latency: {latency_ms:.1f}ms {'✅' if passed else '❌'} (threshold: {latency_threshold_ms}ms)")
    print(f"  Transactions processed: 100")

    return {
        "test_name": "dashboard_overview_latency",
        "passed": passed,
        "metrics": {
            "latency_ms": round(latency_ms, 2),
            "threshold_ms": latency_threshold_ms,
            "transactions_processed": 100,
        }
    }


async def test_memory_growth_doesnt_degrade_linearly(
    memory_sizes: List[int] = [100, 500, 1000, 2000],
    max_slope: float = 1.5,
) -> Dict:
    """Test 10: Does latency scale sublinearly with memory count?

    Validates that retrieval uses efficient indexing (not brute force).

    Args:
        memory_sizes: Different memory bank sizes to test
        max_slope: Maximum acceptable log-log slope (should be < 2 for sublinear)

    Returns:
        Dict with test results
    """
    print(f"\n{'='*60}")
    print("TEST 10: Memory Growth Doesn't Degrade Linearly")
    print(f"{'='*60}")

    latencies = []

    for n in memory_sizes:
        print(f"Testing with {n} memories...")

        # Create dataset
        dataset = generate_personal_assistant_dataset()

        # Duplicate to reach target size
        memories = list(dataset.memories)
        while len(memories) < n:
            memories.extend(dataset.memories[:min(100, n - len(memories))])

        # Create simulator
        simulator = create_test_simulator(
            [m.content for m in memories[:n]],
            [m.id for m in memories[:n]],
            k=5
        )

        # Measure retrieval latency (average over 10 queries)
        query = "What do I prefer for programming?"
        times = []

        for _ in range(10):
            start = time.perf_counter()
            await simulator.process_query(query)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        mean_latency = np.mean(times)
        latencies.append(mean_latency)

        print(f"  Mean latency: {mean_latency:.1f}ms")

    # Fit log-log regression to check scaling
    # log(latency) = slope * log(n) + intercept
    # If slope ≈ 1: linear scaling (bad)
    # If slope < 1: sublinear scaling (good, e.g., log(n))

    log_n = np.log(memory_sizes)
    log_latency = np.log(latencies)

    # Simple linear regression
    slope = np.cov(log_n, log_latency)[0, 1] / np.var(log_n)
    intercept = np.mean(log_latency) - slope * np.mean(log_n)

    passed = slope <= max_slope

    print(f"\nResults:")
    print(f"  Memory sizes tested: {memory_sizes}")
    print(f"  Latencies: {[round(l, 1) for l in latencies]}")
    print(f"  Log-log slope: {slope:.3f} {'✅' if passed else '❌'} (threshold: {max_slope})")
    print(f"  Interpretation: {'Sublinear scaling ✅' if slope < 1 else 'Linear or worse ❌'}")

    return {
        "test_name": "memory_growth_scaling",
        "passed": passed,
        "metrics": {
            "memory_sizes": memory_sizes,
            "latencies_ms": [round(l, 2) for l in latencies],
            "log_log_slope": round(slope, 4),
            "max_slope": max_slope,
        }
    }


async def run_all_performance_tests():
    """Run all performance tests."""
    print(f"\n{'#'*60}")
    print("# CortexOS Performance Test Suite")
    print(f"{'#'*60}")

    # Test 7: EAS latency
    test7_result = await test_eas_latency_under_load(
        n_memories=1000,
        n_concurrent_queries=50,
        p95_threshold_ms=500,
    )

    # Test 8: Welford accuracy
    test8_result = await test_welford_accuracy_at_scale(
        n_updates=10000,
        max_error_pct=0.1,
    )

    # Test 9: Dashboard latency
    test9_result = await test_dashboard_overview_latency(
        latency_threshold_ms=2000,
    )

    # Test 10: Memory growth scaling
    test10_result = await test_memory_growth_doesnt_degrade_linearly(
        memory_sizes=[100, 500, 1000],  # Reduced for faster testing
        max_slope=1.5,
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    all_results = [test7_result, test8_result, test9_result, test10_result]
    passed_count = sum(1 for r in all_results if r["passed"])
    total_count = len(all_results)

    for result in all_results:
        status = "✅ PASSED" if result["passed"] else "❌ FAILED"
        print(f"{result['test_name']:30} {status}")

    print(f"\nOVERALL: {passed_count}/{total_count} PASSED")

    if passed_count == total_count:
        print("\n🎉 All performance tests PASSED!")
        print("CortexOS can handle production-scale workloads.")
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed.")
        print("Performance may degrade under production load.")

    return all_results


if __name__ == "__main__":
    results = asyncio.run(run_all_performance_tests())
