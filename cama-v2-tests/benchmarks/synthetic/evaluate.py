"""Evaluate CAMA v2/v3 on synthetic benchmark cases.

Computes:
- Attribution P@1 and P@3
- Ghost Precision and Recall
- Direction Accuracy
- Stale Detection Rate
- Latency stats
"""

from __future__ import annotations

import time
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from cama.pipeline import CAMAv2
from cama.detect import EmbeddingDetector, get_detector
from cama.attribute import NLICrossEncoderAttributor

from .generator import generate_benchmark


@dataclass
class BenchmarkResults:
    total_cases: int = 0
    cases_with_spans: int = 0

    # Attribution
    p_at_1_hits: int = 0
    p_at_3_hits: int = 0

    # Ghost
    ghost_tp: int = 0  # True positives
    ghost_fp: int = 0  # False positives
    ghost_fn: int = 0  # False negatives

    # Direction
    direction_correct: int = 0
    direction_total: int = 0

    # Stale
    stale_detected: int = 0
    stale_expected: int = 0

    # Latency
    latencies_ms: list[float] = field(default_factory=list)

    # Per-domain breakdown
    domain_results: dict[str, dict] = field(default_factory=dict)

    @property
    def p_at_1(self) -> float:
        return self.p_at_1_hits / max(self.cases_with_spans, 1)

    @property
    def p_at_3(self) -> float:
        return self.p_at_3_hits / max(self.cases_with_spans, 1)

    @property
    def ghost_precision(self) -> float:
        return self.ghost_tp / max(self.ghost_tp + self.ghost_fp, 1)

    @property
    def ghost_recall(self) -> float:
        return self.ghost_tp / max(self.ghost_tp + self.ghost_fn, 1)

    @property
    def direction_accuracy(self) -> float:
        return self.direction_correct / max(self.direction_total, 1)

    @property
    def stale_rate(self) -> float:
        return self.stale_detected / max(self.stale_expected, 1)

    @property
    def mean_latency_ms(self) -> float:
        return sum(self.latencies_ms) / max(len(self.latencies_ms), 1)

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]


def evaluate_case(engine: Any, case: dict, results: BenchmarkResults) -> dict:
    """Evaluate a single benchmark case. Returns per-case metrics dict."""
    gt = case["ground_truth"]
    expected_culprit = gt["expected_culprit"]
    expected_ghosts = set(gt.get("expected_ghosts", []))
    expected_stale = set(gt.get("expected_stale", []))

    start = time.perf_counter()
    result = engine.trace(
        query=case["query"],
        response=case["response"],
        memories=case["memories"],
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    results.total_cases += 1
    results.latencies_ms.append(elapsed_ms)

    case_metrics = {
        "case_id": case["case_id"],
        "domain": case["domain"],
        "latency_ms": elapsed_ms,
        "p_at_1": False,
        "p_at_3": False,
        "has_spans": len(result.hallucinated_spans) > 0,
    }

    # Attribution P@K
    if result.span_attributions:
        results.cases_with_spans += 1

        # Top-1: culprit_memory_id matches on any span
        for sa in result.span_attributions:
            if sa.culprit_memory_id == expected_culprit:
                results.p_at_1_hits += 1
                case_metrics["p_at_1"] = True
                break

        # Top-3: culprit in top 3 by MAS on any span
        for sa in result.span_attributions:
            top3_ids = [a.memory_id for a in sa.attributions[:3]]
            if expected_culprit in top3_ids:
                results.p_at_3_hits += 1
                case_metrics["p_at_3"] = True
                break

        # Direction accuracy: is culprit classified as "causing"?
        for sa in result.span_attributions:
            culprit_attr = next(
                (a for a in sa.attributions if a.memory_id == expected_culprit), None
            )
            if culprit_attr:
                results.direction_total += 1
                if culprit_attr.direction == "causing":
                    results.direction_correct += 1
                break

    # Ghost metrics
    actual_ghosts = set(result.ghost_memories)
    for gid in expected_ghosts:
        if gid in actual_ghosts:
            results.ghost_tp += 1
        else:
            results.ghost_fn += 1
    for gid in actual_ghosts:
        if gid not in expected_ghosts:
            results.ghost_fp += 1

    # Stale detection
    actual_stale = set(result.stale_memories)
    for sid in expected_stale:
        results.stale_expected += 1
        if sid in actual_stale:
            results.stale_detected += 1

    return case_metrics


def run_benchmark(
    n_cases: int = 500,
    seed: int = 42,
    output_path: str | None = None,
    verbose: bool = True,
    detector_name: str = "embedding",
    attributor_name: str = "loo",
    pipeline_version: str = "v2",
) -> BenchmarkResults:
    """Run the full synthetic benchmark.

    Args:
        n_cases: Number of test cases to generate and evaluate.
        seed: Random seed for reproducibility.
        output_path: Optional path to save detailed results JSON.
        verbose: Print progress.
        detector_name: "embedding" for EmbeddingDetector, "lettucedetect" for LettuceDetector.
        pipeline_version: "v2" (default) or "v3" (CAMAv3Pipeline).

    Returns:
        BenchmarkResults with aggregate metrics.
    """
    if verbose:
        print(f"Generating {n_cases} synthetic benchmark cases (seed={seed})...")
    cases = generate_benchmark(n_cases, seed)

    if pipeline_version == "v3":
        from cama.pipeline_v3 import CAMAv3Pipeline
        if verbose:
            print("Initializing CAMA v3 (SummaC NLI matrix)...")
        engine = CAMAv3Pipeline(top_k=10)
    else:
        if verbose:
            print(f"Initializing CAMA v2 engine (detector={detector_name}, attributor={attributor_name})...")
        if detector_name == "lettucedetect":
            detector = get_detector(prefer_gpu=True)
        else:
            detector = EmbeddingDetector()

        attributor = None
        if attributor_name == "nli":
            attributor = NLICrossEncoderAttributor()
        engine = CAMAv2(detector=detector, attributor=attributor)

        if verbose:
            print(f"  Detector: {type(engine.detector).__name__}")

    results = BenchmarkResults()
    per_case_metrics = []

    for i, case in enumerate(cases):
        if verbose and (i + 1) % 50 == 0:
            print(f"  [{i+1}/{n_cases}] P@1={results.p_at_1:.1%}, "
                  f"P@3={results.p_at_3:.1%}, "
                  f"mean_lat={results.mean_latency_ms:.0f}ms")

        metrics = evaluate_case(engine, case, results)
        per_case_metrics.append(metrics)

    if verbose:
        print(f"\n{'='*60}")
        print(f"SYNTHETIC BENCHMARK RESULTS ({n_cases} cases)")
        print(f"{'='*60}")
        print(f"  Cases with hallucinated spans: {results.cases_with_spans}/{results.total_cases}")
        print(f"  Attribution P@1: {results.p_at_1:.1%}")
        print(f"  Attribution P@3: {results.p_at_3:.1%}")
        print(f"  Ghost Precision: {results.ghost_precision:.1%}")
        print(f"  Ghost Recall:    {results.ghost_recall:.1%}")
        print(f"  Direction Accuracy: {results.direction_accuracy:.1%}")
        print(f"  Stale Detection Rate: {results.stale_rate:.1%}")
        print(f"  Mean Latency: {results.mean_latency_ms:.0f}ms")
        print(f"  P95 Latency:  {results.p95_latency_ms:.0f}ms")

    if output_path:
        output = {
            "summary": {
                "total_cases": results.total_cases,
                "cases_with_spans": results.cases_with_spans,
                "p_at_1": results.p_at_1,
                "p_at_3": results.p_at_3,
                "ghost_precision": results.ghost_precision,
                "ghost_recall": results.ghost_recall,
                "direction_accuracy": results.direction_accuracy,
                "stale_rate": results.stale_rate,
                "mean_latency_ms": results.mean_latency_ms,
                "p95_latency_ms": results.p95_latency_ms,
            },
            "per_case": per_case_metrics,
        }
        Path(output_path).write_text(json.dumps(output, indent=2))
        if verbose:
            print(f"\nDetailed results saved to: {output_path}")

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--detector", default="embedding", choices=["embedding", "lettucedetect"])
    parser.add_argument("--attributor", default="loo", choices=["loo", "nli"])
    parser.add_argument("--output", default="benchmark_results.json")
    parser.add_argument("--pipeline", default="v2", choices=["v2", "v3"])
    args = parser.parse_args()
    run_benchmark(
        n_cases=args.n,
        output_path=args.output,
        detector_name=args.detector,
        attributor_name=args.attributor,
        pipeline_version=args.pipeline,
    )
