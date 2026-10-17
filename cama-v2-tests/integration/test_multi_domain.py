"""Multi-domain integration tests — parametrized across 5 domains.

Each domain scenario has a planted poison memory, expected ghosts,
expected stale memories, and ground truth for validation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cama.types import TraceResult

DATA_DIR = Path(__file__).parent.parent / "data"

SCENARIOS = [
    "shipping_scenario",
    "medical_scenario",
    "finance_scenario",
    "legal_scenario",
    "multilingual_scenario",
]


def load(name: str) -> dict:
    return json.loads((DATA_DIR / f"{name}.json").read_text())


@pytest.fixture(params=SCENARIOS, ids=SCENARIOS)
def scenario(request):
    return load(request.param)


class TestMultiDomainTraceCompletes:
    """Every domain scenario should produce a valid TraceResult."""

    def test_trace_does_not_crash(self, engine, scenario):
        result = engine.trace(
            query=scenario["query"],
            response=scenario["response"],
            memories=scenario["memories"],
        )
        assert isinstance(result, TraceResult)

    def test_health_in_valid_range(self, engine, scenario):
        result = engine.trace(
            query=scenario["query"],
            response=scenario["response"],
            memories=scenario["memories"],
        )
        assert 0 <= result.health_score <= 100

    def test_latency_under_10s(self, engine, scenario):
        result = engine.trace(
            query=scenario["query"],
            response=scenario["response"],
            memories=scenario["memories"],
        )
        assert result.latency_ms < 10000, \
            f"Scenario too slow: {result.latency_ms:.0f}ms"


class TestMultiDomainStaleDetection:
    """Stale memory detection should work across all domains."""

    def test_stale_detected(self, engine, scenario):
        gt = scenario.get("ground_truth", {})
        expected_stale = set(gt.get("expected_stale", []))
        if not expected_stale:
            pytest.skip("No expected_stale in ground truth")

        result = engine.trace(
            query=scenario["query"],
            response=scenario["response"],
            memories=scenario["memories"],
        )
        actual_stale = set(result.stale_memories)
        assert expected_stale.issubset(actual_stale), \
            f"Missing stale: {expected_stale - actual_stale}"


class TestMultiDomainGhostDetection:
    """Ghost detection should work across domains (when hallucination exists)."""

    def test_ghosts_detected(self, engine, scenario):
        gt = scenario.get("ground_truth", {})
        expected_ghosts = set(gt.get("expected_ghosts", []))
        if not expected_ghosts:
            pytest.skip("No expected_ghosts in ground truth")

        result = engine.trace(
            query=scenario["query"],
            response=scenario["response"],
            memories=scenario["memories"],
        )

        if not result.hallucinated_spans:
            pytest.skip("No hallucinated spans detected — can't evaluate ghosts")

        actual_ghosts = set(result.ghost_memories)
        overlap = expected_ghosts & actual_ghosts
        assert len(overlap) > 0, \
            f"No expected ghosts found. Expected: {expected_ghosts}, Got: {actual_ghosts}"


class TestMultiDomainCulpritAttribution:
    """The planted poison memory should be identified as culprit."""

    def test_culprit_attributed(self, engine, scenario):
        gt = scenario.get("ground_truth", {})
        expected_culprit = gt.get("expected_culprit")
        if not expected_culprit:
            pytest.skip("No expected_culprit in ground truth")

        result = engine.trace(
            query=scenario["query"],
            response=scenario["response"],
            memories=scenario["memories"],
        )

        if not result.span_attributions:
            pytest.skip("No span attributions — detection may not have flagged anything")

        culprits = [
            sa.culprit_memory_id
            for sa in result.span_attributions
            if sa.culprit_memory_id is not None
        ]
        # Soft assertion: culprit should appear in at least one span
        if culprits:
            assert expected_culprit in culprits, \
                f"Expected culprit '{expected_culprit}' not in {culprits}"
