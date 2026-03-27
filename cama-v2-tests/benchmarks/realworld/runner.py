"""Real-world scenario runner.

Iterates all scenarios, evaluates each, and produces aggregate results.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from cama.pipeline import CAMAv2
from cama.detect import EmbeddingDetector, get_detector
from cama.attribute import NLICrossEncoderAttributor

from .evaluate import RealWorldMetrics, evaluate_scenario
from .scenarios import ALL_SCENARIOS


def run_all_scenarios(
    detector_name: str = "embedding",
    attributor_name: str = "loo",
    output_path: str | None = None,
    verbose: bool = True,
    scenarios: list[dict] | None = None,
    nli_model_name: str = "cross-encoder/nli-deberta-v3-xsmall",
    pipeline_version: str = "v2",
) -> list[RealWorldMetrics]:
    """Run all real-world scenarios and return metrics.

    Args:
        detector_name: "embedding" or "lettucedetect"
        attributor_name: "loo" or "nli"
        output_path: Optional JSON output path.
        verbose: Print progress.
        scenarios: Optional list of scenarios to run (defaults to ALL_SCENARIOS).
        nli_model_name: NLI model name for cross-encoder attributor.
        pipeline_version: "v2" (default) or "v3" (CAMAv3Pipeline).

    Returns:
        List of RealWorldMetrics, one per scenario.
    """
    if pipeline_version == "v3":
        from cama.pipeline_v3 import CAMAv3Pipeline
        if verbose:
            print("Initializing CAMA v3 (SummaC NLI matrix)...")
        engine = CAMAv3Pipeline(top_k=10, model_name=nli_model_name)
    else:
        if verbose:
            print(f"Initializing CAMA v2 (detector={detector_name}, attributor={attributor_name})...")

        if detector_name == "lettucedetect":
            detector = get_detector(prefer_gpu=True)
        else:
            detector = EmbeddingDetector()

        attributor = None
        nli_model = None
        if attributor_name == "nli":
            attributor = NLICrossEncoderAttributor(model_name=nli_model_name)
            from cama.nli import NLIModel
            nli_model = NLIModel(model_name=nli_model_name)

        engine = CAMAv2(detector=detector, attributor=attributor, nli_model=nli_model)

    scenario_list = scenarios or ALL_SCENARIOS
    all_metrics: list[RealWorldMetrics] = []

    for i, scenario in enumerate(scenario_list):
        if verbose:
            print(f"\n[{i+1}/{len(scenario_list)}] Running: {scenario['name']} "
                  f"({len(scenario['memories'])} memories, {len(scenario['queries'])} queries)")

        metrics = evaluate_scenario(engine, scenario)
        all_metrics.append(metrics)

        if verbose:
            print(f"  P@1: {metrics.p_at_1:.1%} | "
                  f"Ghost F1: {metrics.ghost_f1:.1%} | "
                  f"Contra Prec: {metrics.contradiction_precision:.1%} | "
                  f"Latency: {metrics.mean_latency_ms:.0f}ms")

    if verbose:
        print(f"\n{'='*60}")
        print("REAL-WORLD SCENARIO SUMMARY")
        print(f"{'='*60}")
        for m in all_metrics:
            print(f"  {m.scenario_name:30s} P@1={m.p_at_1:.1%}  Ghost_F1={m.ghost_f1:.1%}  "
                  f"Lat={m.mean_latency_ms:.0f}ms")

    if output_path:
        output = {
            "scenarios": [m.to_dict() for m in all_metrics],
            "aggregate": _compute_aggregate(all_metrics),
        }
        Path(output_path).write_text(json.dumps(output, indent=2))
        if verbose:
            print(f"\nResults saved to: {output_path}")

    return all_metrics


def _compute_aggregate(metrics_list: list[RealWorldMetrics]) -> dict:
    """Compute aggregate metrics across all scenarios."""
    if not metrics_list:
        return {}

    total_p1_hits = sum(m.p_at_1_hits for m in metrics_list)
    total_p1_total = sum(m.p_at_1_total for m in metrics_list)
    total_ghost_tp = sum(m.ghost_tp for m in metrics_list)
    total_ghost_fp = sum(m.ghost_fp for m in metrics_list)
    total_ghost_fn = sum(m.ghost_fn for m in metrics_list)
    total_contra_tp = sum(m.contradiction_tp for m in metrics_list)
    total_contra_fp = sum(m.contradiction_fp for m in metrics_list)
    total_contra_fn = sum(m.contradiction_fn for m in metrics_list)
    all_latencies = [lat for m in metrics_list for lat in m.latencies_ms]

    ghost_p = total_ghost_tp / max(total_ghost_tp + total_ghost_fp, 1)
    ghost_r = total_ghost_tp / max(total_ghost_tp + total_ghost_fn, 1)

    return {
        "p_at_1": total_p1_hits / max(total_p1_total, 1),
        "ghost_precision": ghost_p,
        "ghost_recall": ghost_r,
        "ghost_f1": 2 * ghost_p * ghost_r / max(ghost_p + ghost_r, 1e-8),
        "contradiction_precision": total_contra_tp / max(total_contra_tp + total_contra_fp, 1),
        "contradiction_recall": total_contra_tp / max(total_contra_tp + total_contra_fn, 1),
        "mean_latency_ms": sum(all_latencies) / max(len(all_latencies), 1),
        "total_scenarios": len(metrics_list),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector", default="embedding", choices=["embedding", "lettucedetect"])
    parser.add_argument("--attributor", default="loo", choices=["loo", "nli"])
    parser.add_argument("--nli-model", default="cross-encoder/nli-deberta-v3-xsmall")
    parser.add_argument("--output", default="realworld_results.json")
    parser.add_argument("--pipeline", default="v2", choices=["v2", "v3"])
    args = parser.parse_args()
    run_all_scenarios(
        detector_name=args.detector,
        attributor_name=args.attributor,
        output_path=args.output,
        nli_model_name=args.nli_model,
        pipeline_version=args.pipeline,
    )
