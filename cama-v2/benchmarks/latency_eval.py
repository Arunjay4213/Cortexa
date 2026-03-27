"""Measure CAMA v2 pipeline latency for various memory counts.

Tests K in [5, 10, 20, 50] with 100 runs each.
Reports mean, p50, p95, p99 latency and peak RAM usage.
"""

from __future__ import annotations

import logging
import os
import time

import numpy as np

from cama.pipeline import CAMAv2

logger = logging.getLogger(__name__)


def generate_test_case(k: int) -> dict:
    """Generate a test case with K memories."""
    memories = []
    for i in range(k):
        memories.append({
            "id": f"m{i}",
            "content": f"Memory {i}: The product feature {i} has specification value {i * 10 + 5}.",
        })

    # Plant one "wrong" memory
    if k > 0:
        memories[0]["content"] = "The product ships in 2-3 business days."

    return {
        "query": "What are the product details?",
        "response": "The product ships in 2-3 business days. Feature 1 has specification value 15. Feature 2 has value 25.",
        "memories": memories,
    }


def measure_memory_usage() -> float:
    """Get current process RSS in MB."""
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024 / 1024  # Convert to MB (macOS returns bytes)
    except Exception:
        return 0.0


def run_latency_benchmark(
    cama: CAMAv2,
    k_values: list[int] | None = None,
    n_runs: int = 100,
) -> list[dict]:
    """Run latency benchmark for various memory counts.

    Returns list of result dicts per K value.
    """
    if k_values is None:
        k_values = [5, 10, 20, 50]

    results = []

    for k in k_values:
        test_case = generate_test_case(k)
        latencies = []

        # Warmup
        cama.trace(**test_case)

        peak_ram_before = measure_memory_usage()

        for _ in range(n_runs):
            start = time.perf_counter()
            cama.trace(**test_case)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        peak_ram_after = measure_memory_usage()

        arr = np.array(latencies)
        results.append({
            "k_memories": k,
            "n_runs": n_runs,
            "mean_ms": round(float(np.mean(arr)), 1),
            "p50_ms": round(float(np.percentile(arr, 50)), 1),
            "p95_ms": round(float(np.percentile(arr, 95)), 1),
            "p99_ms": round(float(np.percentile(arr, 99)), 1),
            "min_ms": round(float(np.min(arr)), 1),
            "max_ms": round(float(np.max(arr)), 1),
            "peak_ram_mb": round(max(peak_ram_before, peak_ram_after), 1),
        })

        print(f"K={k:3d}: mean={results[-1]['mean_ms']:.1f}ms  "
              f"p95={results[-1]['p95_ms']:.1f}ms  "
              f"RAM={results[-1]['peak_ram_mb']:.0f}MB")

    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    print("=== CAMA v2 Latency Benchmark ===\n")

    # Test both GPU and CPU if available
    configs = []

    try:
        cama_gpu = CAMAv2(device="auto")
        detector_name = type(cama_gpu.detector).__name__
        if "Lettuce" in detector_name:
            configs.append(("GPU (LettuceDetect)", cama_gpu))
    except Exception:
        pass

    try:
        cama_cpu = CAMAv2(device="cpu")
        configs.append(("CPU (Embedding)", cama_cpu))
    except Exception as e:
        logger.warning("CPU detector not available: %s", e)

    if not configs:
        print("No detector available. Install cama-v2[gpu] or cama-v2[cpu].")
        return

    all_results = {}
    for name, cama in configs:
        print(f"\n--- {name} ---")
        results = run_latency_benchmark(cama, n_runs=20)  # Fewer runs for quick testing
        all_results[name] = results

    # Print summary table
    print("\n=== Summary ===")
    print(f"{'Config':<25} {'K':>3} {'Mean (ms)':>10} {'P95 (ms)':>10} {'RAM (MB)':>10}")
    print("-" * 65)
    for name, results in all_results.items():
        for r in results:
            print(f"{name:<25} {r['k_memories']:>3} {r['mean_ms']:>10.1f} "
                  f"{r['p95_ms']:>10.1f} {r['peak_ram_mb']:>10.0f}")


if __name__ == "__main__":
    main()
