"""Run all CAMA v2 benchmarks and generate report."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    results_dir = Path("benchmarks")
    results_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("  CAMA v2 — Full Benchmark Suite")
    print("=" * 60)

    # 1. Build synthetic benchmark
    print("\n[1/4] Building synthetic benchmark...")
    try:
        from benchmarks.build_synthetic import build_benchmark, save_benchmark
        examples = build_benchmark(n=200)
        save_benchmark(examples)
        print(f"  Built {len(examples)} examples")
    except Exception as e:
        logger.error("Failed to build synthetic: %s", e)
        examples = None

    # 2. Run detection eval (RAGTruth)
    print("\n[2/4] RAGTruth detection evaluation...")
    detection_metrics = None
    try:
        from benchmarks.ragtruth_eval import evaluate_detection, load_ragtruth
        rt_examples = load_ragtruth()
        detection_metrics = evaluate_detection(rt_examples, max_examples=100)
        with open(results_dir / "detection_results.json", "w") as f:
            json.dump(detection_metrics, f, indent=2)
        print(f"  Example F1: {detection_metrics['example_f1'] * 100:.1f}%")
    except ImportError:
        print("  Skipped (install cama-v2[bench] for RAGTruth)")
    except Exception as e:
        logger.error("  Failed: %s", e)

    # 3. Run attribution eval (synthetic)
    print("\n[3/4] Synthetic attribution evaluation...")
    attribution_metrics = None
    try:
        from benchmarks.synthetic_eval import evaluate, load_benchmark
        from cama.pipeline import CAMAv2

        cama = CAMAv2(device="auto")
        if examples is None:
            examples = load_benchmark()
        attribution_metrics = evaluate(cama, examples, max_examples=50)
        with open(results_dir / "attribution_results.json", "w") as f:
            json.dump(attribution_metrics, f, indent=2)
        p1 = attribution_metrics.get("attribution_p_at_1")
        print(f"  P@1: {p1 * 100:.1f}%" if p1 else "  P@1: N/A")
        print(f"  Ghost F1: {attribution_metrics['ghost_f1'] * 100:.1f}%")
    except Exception as e:
        logger.error("  Failed: %s", e)

    # 4. Run latency eval
    print("\n[4/4] Latency benchmark...")
    latency_results = None
    try:
        from benchmarks.latency_eval import run_latency_benchmark
        from cama.pipeline import CAMAv2

        cama = CAMAv2(device="auto")
        config_name = type(cama.detector).__name__
        results = run_latency_benchmark(cama, k_values=[5, 10, 20], n_runs=10)
        latency_results = {config_name: results}
        with open(results_dir / "latency_results.json", "w") as f:
            json.dump(latency_results, f, indent=2)
    except Exception as e:
        logger.error("  Failed: %s", e)

    # 5. Generate report
    print("\n[5/5] Generating report...")
    from benchmarks.report import generate_report
    report = generate_report(detection_metrics, attribution_metrics, latency_results)
    print("\n" + report)

    print("\nDone! Report saved to benchmarks/REPORT.md")


if __name__ == "__main__":
    main()
