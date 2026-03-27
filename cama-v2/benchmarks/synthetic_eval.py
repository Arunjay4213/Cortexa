"""Evaluate CAMA v2 attribution on the synthetic planted-poison benchmark.

Metrics:
- Attribution Precision@1: top-MAS memory == planted poison?
- Ghost F1: precision/recall on ghost memory detection
- Direction Accuracy: is culprit flagged as "causing"?
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from cama.pipeline import CAMAv2
from cama.types import Memory

logger = logging.getLogger(__name__)


def load_benchmark(path: str = "benchmarks/synthetic_dataset.json") -> list[dict]:
    """Load synthetic benchmark from JSON."""
    with open(path) as f:
        return json.load(f)


def evaluate(
    cama: CAMAv2,
    examples: list[dict],
    max_examples: int | None = None,
) -> dict:
    """Run evaluation and compute metrics.

    Returns dict with:
    - attribution_p_at_1: Precision@1 for poison memory attribution
    - ghost_precision, ghost_recall, ghost_f1
    - direction_accuracy: fraction of culprits flagged as "causing"
    - avg_latency_ms
    """
    if max_examples:
        examples = examples[:max_examples]

    results = {
        "total": 0,
        "with_poison": 0,
        "poison_correct": 0,
        "with_ghosts": 0,
        "ghost_tp": 0,
        "ghost_fp": 0,
        "ghost_fn": 0,
        "direction_total": 0,
        "direction_correct": 0,
        "latencies": [],
    }

    for ex in examples:
        results["total"] += 1
        gt = ex["ground_truth"]

        # Run pipeline
        start = time.perf_counter()
        trace = cama.trace(
            query=ex["query"],
            response=ex["response"],
            memories=ex["memories"],
        )
        elapsed = (time.perf_counter() - start) * 1000
        results["latencies"].append(elapsed)

        # Attribution P@1
        poison_id = gt.get("poison_memory_id")
        if poison_id and trace.span_attributions:
            results["with_poison"] += 1
            # Find the span attribution with highest MAS for any memory
            for sa in trace.span_attributions:
                if sa.attributions:
                    top_memory = sa.attributions[0].memory_id  # sorted by |delta|
                    if top_memory == poison_id:
                        results["poison_correct"] += 1
                        break

            # Direction accuracy
            for sa in trace.span_attributions:
                for attr in sa.attributions:
                    if attr.memory_id == poison_id:
                        results["direction_total"] += 1
                        if attr.direction == "causing":
                            results["direction_correct"] += 1
                        break

        # Ghost F1
        expected_ghosts = set(gt.get("ghost_memory_ids", []))
        predicted_ghosts = set(trace.ghost_memories)

        if expected_ghosts:
            results["with_ghosts"] += 1

        results["ghost_tp"] += len(predicted_ghosts & expected_ghosts)
        results["ghost_fp"] += len(predicted_ghosts - expected_ghosts)
        results["ghost_fn"] += len(expected_ghosts - predicted_ghosts)

    # Compute final metrics
    metrics: dict = {
        "total_examples": results["total"],
    }

    # P@1
    if results["with_poison"] > 0:
        metrics["attribution_p_at_1"] = results["poison_correct"] / results["with_poison"]
    else:
        metrics["attribution_p_at_1"] = None

    # Ghost F1
    ghost_p = results["ghost_tp"] / max(results["ghost_tp"] + results["ghost_fp"], 1)
    ghost_r = results["ghost_tp"] / max(results["ghost_tp"] + results["ghost_fn"], 1)
    ghost_f1 = 2 * ghost_p * ghost_r / max(ghost_p + ghost_r, 1e-8)
    metrics["ghost_precision"] = round(ghost_p, 4)
    metrics["ghost_recall"] = round(ghost_r, 4)
    metrics["ghost_f1"] = round(ghost_f1, 4)

    # Direction accuracy
    if results["direction_total"] > 0:
        metrics["direction_accuracy"] = results["direction_correct"] / results["direction_total"]
    else:
        metrics["direction_accuracy"] = None

    # Latency
    if results["latencies"]:
        latencies = sorted(results["latencies"])
        metrics["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1)
        metrics["p50_latency_ms"] = round(latencies[len(latencies) // 2], 1)
        metrics["p95_latency_ms"] = round(latencies[int(len(latencies) * 0.95)], 1)

    return metrics


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    # Build benchmark if not exists
    bench_path = Path("benchmarks/synthetic_dataset.json")
    if not bench_path.exists():
        from benchmarks.build_synthetic import build_benchmark, save_benchmark
        examples = build_benchmark(n=200)
        save_benchmark(examples)
    else:
        examples = load_benchmark(str(bench_path))

    print(f"Loaded {len(examples)} benchmark examples")

    # Try GPU first, fall back to CPU
    try:
        cama = CAMAv2(device="auto")
        print(f"Using detector: {type(cama.detector).__name__}")
    except Exception as e:
        logger.warning("Failed to initialize: %s", e)
        return

    metrics = evaluate(cama, examples, max_examples=50)

    print("\n=== CAMA v2 Attribution Evaluation ===")
    for k, v in metrics.items():
        if v is not None:
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: N/A")


if __name__ == "__main__":
    main()
