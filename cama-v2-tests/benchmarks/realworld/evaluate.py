"""Real-world scenario evaluator for CAMA v2/v3.

Evaluates each scenario against ground truth expectations:
- P@1 attribution accuracy
- Ghost Precision / Recall / F1
- Contradiction detection rate
- Stale detection rate
- Latency
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RealWorldMetrics:
    """Metrics for a single real-world scenario."""

    scenario_name: str = ""
    scenario_domain: str = ""

    # Attribution
    p_at_1_hits: int = 0
    p_at_1_total: int = 0

    # Ghost detection
    ghost_tp: int = 0
    ghost_fp: int = 0
    ghost_fn: int = 0

    # Contradiction detection
    contradiction_tp: int = 0
    contradiction_fp: int = 0
    contradiction_fn: int = 0

    # Stale detection
    stale_tp: int = 0
    stale_fn: int = 0

    # Diagnosis accuracy
    diagnosis_correct: int = 0
    diagnosis_total: int = 0

    # Context stats
    memories_processed: int = 0
    tokens_in_context: int = 0

    # Latency
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def p_at_1(self) -> float:
        return self.p_at_1_hits / max(self.p_at_1_total, 1)

    @property
    def ghost_precision(self) -> float:
        return self.ghost_tp / max(self.ghost_tp + self.ghost_fp, 1)

    @property
    def ghost_recall(self) -> float:
        return self.ghost_tp / max(self.ghost_tp + self.ghost_fn, 1)

    @property
    def ghost_f1(self) -> float:
        p, r = self.ghost_precision, self.ghost_recall
        return 2 * p * r / max(p + r, 1e-8)

    @property
    def contradiction_precision(self) -> float:
        return self.contradiction_tp / max(self.contradiction_tp + self.contradiction_fp, 1)

    @property
    def contradiction_recall(self) -> float:
        return self.contradiction_tp / max(self.contradiction_tp + self.contradiction_fn, 1)

    @property
    def stale_rate(self) -> float:
        return self.stale_tp / max(self.stale_tp + self.stale_fn, 1)

    @property
    def diagnosis_accuracy(self) -> float:
        return self.diagnosis_correct / max(self.diagnosis_total, 1)

    @property
    def actionable_rate(self) -> float:
        """Rate of correctly actionable diagnoses (ghost + stale + contradiction)."""
        total_actionable = self.ghost_tp + self.stale_tp + self.contradiction_tp
        total_expected = (
            self.ghost_tp + self.ghost_fn
            + self.stale_tp + self.stale_fn
            + self.contradiction_tp + self.contradiction_fn
        )
        return total_actionable / max(total_expected, 1)

    @property
    def false_alarm_rate(self) -> float:
        """Rate of false positives across all detection types."""
        total_fp = self.ghost_fp + self.contradiction_fp
        total_detections = (
            self.ghost_tp + self.ghost_fp
            + self.contradiction_tp + self.contradiction_fp
        )
        return total_fp / max(total_detections, 1)

    @property
    def mean_latency_ms(self) -> float:
        return sum(self.latencies_ms) / max(len(self.latencies_ms), 1)

    def to_dict(self) -> dict:
        return {
            "scenario_name": self.scenario_name,
            "scenario_domain": self.scenario_domain,
            "p_at_1": self.p_at_1,
            "ghost_precision": self.ghost_precision,
            "ghost_recall": self.ghost_recall,
            "ghost_f1": self.ghost_f1,
            "contradiction_precision": self.contradiction_precision,
            "contradiction_recall": self.contradiction_recall,
            "stale_rate": self.stale_rate,
            "diagnosis_accuracy": self.diagnosis_accuracy,
            "actionable_rate": self.actionable_rate,
            "false_alarm_rate": self.false_alarm_rate,
            "memories_processed": self.memories_processed,
            "tokens_in_context": self.tokens_in_context,
            "mean_latency_ms": self.mean_latency_ms,
        }


def evaluate_scenario(engine: Any, scenario: dict) -> RealWorldMetrics:
    """Evaluate a single real-world scenario.

    Accepts any pipeline object with a .trace(query, response, memories) method.
    Works with both CAMAv2 and CAMAv3Pipeline.

    A scenario dict has:
    - name, domain, memories (list of dicts)
    - queries: list of {query, response, ground_truth}

    ground_truth contains:
    - expected_culprit: str or None
    - expected_ghosts: list[str]
    - expected_contradictions: list[tuple[str, str]]
    - expected_stale: list[str]
    """
    metrics = RealWorldMetrics(
        scenario_name=scenario["name"],
        scenario_domain=scenario["domain"],
    )

    memories = scenario["memories"]
    metrics.memories_processed = len(memories)
    metrics.tokens_in_context = sum(len(m["content"]) // 4 for m in memories)

    for query_case in scenario["queries"]:
        gt = query_case["ground_truth"]
        expected_culprit = gt.get("expected_culprit")
        expected_ghosts = set(gt.get("expected_ghosts", []))
        expected_contradictions = {
            tuple(sorted(pair)) for pair in gt.get("expected_contradictions", [])
        }
        expected_stale = set(gt.get("expected_stale", []))

        start = time.perf_counter()
        result = engine.trace(
            query=query_case["query"],
            response=query_case["response"],
            memories=memories,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        metrics.latencies_ms.append(elapsed_ms)

        # P@1: check if culprit_memory_id matches expected on any span attribution
        if expected_culprit and result.span_attributions:
            metrics.p_at_1_total += 1
            for sa in result.span_attributions:
                if sa.culprit_memory_id == expected_culprit:
                    metrics.p_at_1_hits += 1
                    break

        # Ghost metrics
        actual_ghosts = set(result.ghost_memories)
        for gid in expected_ghosts:
            if gid in actual_ghosts:
                metrics.ghost_tp += 1
            else:
                metrics.ghost_fn += 1
        for gid in actual_ghosts:
            if gid not in expected_ghosts:
                metrics.ghost_fp += 1

        # Contradiction metrics
        actual_contradictions = {
            tuple(sorted([c.memory_id_1, c.memory_id_2]))
            for c in result.contradictions
        }
        for pair in expected_contradictions:
            if pair in actual_contradictions:
                metrics.contradiction_tp += 1
            else:
                metrics.contradiction_fn += 1
        for pair in actual_contradictions:
            if pair not in expected_contradictions:
                metrics.contradiction_fp += 1

        # Stale metrics
        actual_stale = set(result.stale_memories)
        for sid in expected_stale:
            if sid in actual_stale:
                metrics.stale_tp += 1
            else:
                metrics.stale_fn += 1

    return metrics
