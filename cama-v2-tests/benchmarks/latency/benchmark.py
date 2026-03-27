"""Latency benchmark — measure pipeline speed at different scales.

Configs:
1. 1 memory, short response
2. 5 memories, medium response
3. 10 memories, medium response
4. 15 memories, long response
5. 20 memories, long response (pre-filter threshold)
6. 5 memories, no hallucination (skip attribution)
"""

from __future__ import annotations

import time
import json
import sys
from pathlib import Path
from dataclasses import dataclass

from cama.pipeline import CAMAv2
from cama.detect import EmbeddingDetector


@dataclass
class LatencyConfig:
    name: str
    n_memories: int
    response_sentences: int
    hallucination: bool  # Whether response contains fabricated content
    runs: int = 5


CONFIGS = [
    LatencyConfig("1mem_short", 1, 1, True),
    LatencyConfig("5mem_medium", 5, 3, True),
    LatencyConfig("10mem_medium", 10, 3, True),
    LatencyConfig("15mem_long", 15, 5, True),
    LatencyConfig("20mem_long", 20, 5, True),
    LatencyConfig("5mem_no_halluc", 5, 3, False),
]


def build_scenario(config: LatencyConfig) -> dict:
    """Build a test scenario for a given config."""
    memories = []
    for i in range(config.n_memories):
        memories.append({
            "id": f"m{i}",
            "content": f"Fact number {i}: the item-{i} costs ${10 * (i + 1)} with standard features.",
        })

    if config.hallucination:
        # Fabricated response with made-up numbers
        sentences = [
            f"Item-0 costs ${999 + i} which is a great deal."
            for i in range(config.response_sentences)
        ]
    else:
        # Response grounded in memories
        sentences = [
            f"Fact number {i}: the item-{i} costs ${10 * (i + 1)} with standard features."
            for i in range(min(config.response_sentences, config.n_memories))
        ]

    return {
        "query": "What are the prices?",
        "response": " ".join(sentences),
        "memories": memories,
    }


def run_latency_benchmark(
    configs: list[LatencyConfig] | None = None,
    output_path: str | None = None,
    verbose: bool = True,
) -> dict:
    """Run latency benchmark across all configs.

    Returns dict mapping config_name → {mean_ms, min_ms, max_ms, p95_ms, runs}.
    """
    if configs is None:
        configs = CONFIGS

    if verbose:
        print("Initializing CAMA v2 engine...")
    detector = EmbeddingDetector()
    engine = CAMAv2(detector=detector)

    # Warmup run
    if verbose:
        print("Warmup run...")
    engine.trace(
        query="warmup", response="Warmup answer.",
        memories=[{"id": "w1", "content": "Warmup memory."}],
    )

    results = {}

    for config in configs:
        scenario = build_scenario(config)
        latencies = []

        for run in range(config.runs):
            start = time.perf_counter()
            engine.trace(**scenario)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        sorted_lat = sorted(latencies)
        p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)

        entry = {
            "mean_ms": sum(latencies) / len(latencies),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "p95_ms": sorted_lat[p95_idx],
            "runs": config.runs,
            "n_memories": config.n_memories,
            "response_sentences": config.response_sentences,
            "hallucination": config.hallucination,
        }
        results[config.name] = entry

        if verbose:
            print(f"  {config.name:20s} | mean={entry['mean_ms']:7.0f}ms | "
                  f"min={entry['min_ms']:7.0f}ms | max={entry['max_ms']:7.0f}ms | "
                  f"p95={entry['p95_ms']:7.0f}ms")

    if output_path:
        Path(output_path).write_text(json.dumps(results, indent=2))
        if verbose:
            print(f"\nResults saved to: {output_path}")

    return results


if __name__ == "__main__":
    run_latency_benchmark(output_path="latency_results.json")
