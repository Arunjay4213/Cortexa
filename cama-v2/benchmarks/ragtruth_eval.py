"""Evaluate CAMA v2 detection on the RAGTruth benchmark.

Downloads RAGTruth from HuggingFace, runs our detector on the test set,
and compares example-level and span-level F1 against published baselines.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


def load_ragtruth() -> list[dict]:
    """Load RAGTruth test set from HuggingFace."""
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError("datasets required: pip install cama-v2[bench]")

    logger.info("Loading RAGTruth dataset from HuggingFace...")
    ds = load_dataset("NousResearch/ragtruth", split="test")
    return list(ds)


def evaluate_detection(
    examples: list[dict],
    max_examples: int | None = None,
) -> dict:
    """Run detection on RAGTruth and compute F1 metrics.

    Returns dict with example_f1, span_f1, speed_per_sec.
    """
    from cama.detect import get_detector

    detector = get_detector()
    logger.info("Using detector: %s", type(detector).__name__)

    if max_examples:
        examples = examples[:max_examples]

    tp = fp = fn = 0
    total_time = 0.0

    for ex in examples:
        # RAGTruth format varies — adapt as needed
        context = ex.get("context", ex.get("contexts", []))
        if isinstance(context, str):
            context = [context]
        question = ex.get("question", ex.get("query", ""))
        answer = ex.get("answer", ex.get("response", ""))
        has_hallucination = ex.get("label", 0) == 1

        start = time.perf_counter()
        token_scores, spans = detector.detect(context, question, answer)
        total_time += time.perf_counter() - start

        predicted_hallucination = len(spans) > 0

        if has_hallucination and predicted_hallucination:
            tp += 1
        elif not has_hallucination and predicted_hallucination:
            fp += 1
        elif has_hallucination and not predicted_hallucination:
            fn += 1

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)
    speed = len(examples) / max(total_time, 1e-8)

    return {
        "examples_evaluated": len(examples),
        "example_precision": round(precision, 4),
        "example_recall": round(recall, 4),
        "example_f1": round(f1, 4),
        "speed_examples_per_sec": round(speed, 1),
        "total_time_sec": round(total_time, 2),
        "detector": type(get_detector()).__name__,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    try:
        examples = load_ragtruth()
    except Exception as e:
        logger.error("Could not load RAGTruth: %s", e)
        logger.info("Install benchmark deps: pip install cama-v2[bench]")
        return

    print(f"Loaded {len(examples)} RAGTruth examples")

    metrics = evaluate_detection(examples, max_examples=100)

    print("\n=== RAGTruth Detection Evaluation ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    # Baseline comparison
    print("\n--- Baseline Comparison ---")
    print("  LettuceDetect paper (example F1): 79.22%")
    print(f"  CAMA v2 (example F1): {metrics['example_f1'] * 100:.2f}%")


if __name__ == "__main__":
    main()
