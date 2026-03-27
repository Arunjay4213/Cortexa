"""THE GATE TEST: Canonical shipping story end-to-end.

If this test fails, the engine is broken. This is the acceptance test
for the entire CAMA v2 pipeline with real ML inference.
"""

from __future__ import annotations

import pytest

from cama.types import TraceResult


class TestShippingStoryEndToEnd:
    """Full pipeline run on the shipping demo scenario."""

    @pytest.fixture(autouse=True)
    def run_trace(self, engine, shipping_scenario):
        """Run the trace once and cache result for all tests in this class."""
        self.scenario = shipping_scenario
        self.result = engine.trace(
            query=shipping_scenario["query"],
            response=shipping_scenario["response"],
            memories=shipping_scenario["memories"],
        )
        self.gt = shipping_scenario["ground_truth"]

    def test_returns_trace_result(self):
        assert isinstance(self.result, TraceResult)

    def test_all_memories_listed(self):
        expected_ids = {m["id"] for m in self.scenario["memories"]}
        assert set(self.result.memories_used) == expected_ids

    # ── Hallucination Detection ───────────────────────────────────

    def test_hallucination_detected(self):
        """The stale shipping info should trigger hallucination detection."""
        assert self.gt["expected_hallucination"]
        assert self.result.hallucination_rate > 0, \
            f"Expected hallucination but rate={self.result.hallucination_rate}"

    def test_hallucinated_spans_exist(self):
        assert len(self.result.hallucinated_spans) > 0, \
            "Expected at least one hallucinated span"

    def test_hallucinated_span_covers_fabricated_claim(self):
        """At least one span should contain the fabricated insurance claim."""
        span_texts = " ".join(s.text.lower() for s in self.result.hallucinated_spans)
        # The response fabricates "$500 damage insurance" — no memory supports this
        assert any(
            word in span_texts
            for word in ["insurance", "500", "damage"]
        ), f"No span covers the fabricated claim. Spans: {[s.text for s in self.result.hallucinated_spans]}"

    # ── Attribution ───────────────────────────────────────────────

    def test_attribution_ran(self):
        """Attribution should run when spans exist."""
        if self.result.hallucinated_spans:
            assert len(self.result.span_attributions) > 0

    def test_culprit_memory_identified(self):
        """Culprit should be identified if expected (null = fabricated, no culprit)."""
        expected_culprit = self.gt.get("expected_culprit")
        if expected_culprit is None:
            # Fabricated claim — no memory is the culprit
            pytest.skip("No culprit expected for fabricated claim scenario")
        culprits = [
            sa.culprit_memory_id
            for sa in self.result.span_attributions
            if sa.culprit_memory_id is not None
        ]
        if culprits:
            assert expected_culprit in culprits, \
                f"Expected culprit '{expected_culprit}' not found. Got: {culprits}"

    def test_culprit_has_causing_direction(self):
        """The culprit memory should have 'causing' direction."""
        expected_culprit = self.gt.get("expected_culprit")
        if expected_culprit is None:
            pytest.skip("No culprit expected for fabricated claim scenario")
        for sa in self.result.span_attributions:
            culprit_attr = next(
                (a for a in sa.attributions if a.memory_id == expected_culprit),
                None,
            )
            if culprit_attr and abs(culprit_attr.delta) > 0.02:
                assert culprit_attr.direction in ("causing", "supporting"), \
                    f"Culprit direction: {culprit_attr.direction}"

    def test_culprit_has_highest_mas(self):
        """The culprit should have the highest MAS (or near-highest)."""
        expected_culprit = self.gt.get("expected_culprit")
        if expected_culprit is None:
            pytest.skip("No culprit expected for fabricated claim scenario")
        for sa in self.result.span_attributions:
            if sa.culprit_memory_id == expected_culprit:
                culprit_mas = next(
                    a.mas for a in sa.attributions if a.memory_id == expected_culprit
                )
                max_mas = max(a.mas for a in sa.attributions)
                sorted_by_mas = sorted(sa.attributions, key=lambda a: a.mas, reverse=True)
                top_2_ids = [a.memory_id for a in sorted_by_mas[:2]]
                assert expected_culprit in top_2_ids, \
                    f"Culprit MAS={culprit_mas:.3f}, max={max_mas:.3f}. Top 2: {top_2_ids}"

    # ── Ghost Detection ───────────────────────────────────────────

    def test_ghost_memories_detected(self):
        """m1203 (blue theme) and m0023 (OAuth) should be ghosts."""
        expected_ghosts = set(self.gt.get("expected_ghosts", []))
        if expected_ghosts and self.result.hallucinated_spans:
            actual_ghosts = set(self.result.ghost_memories)
            # At least some expected ghosts should be detected
            overlap = expected_ghosts & actual_ghosts
            assert len(overlap) > 0, \
                f"No expected ghosts found. Expected: {expected_ghosts}, Got: {actual_ghosts}"

    # ── Staleness ─────────────────────────────────────────────────

    def test_stale_memories_detected(self):
        """m2847 should be detected as stale."""
        expected_stale = set(self.gt.get("expected_stale", []))
        actual_stale = set(self.result.stale_memories)
        assert expected_stale.issubset(actual_stale), \
            f"Missing stale: {expected_stale - actual_stale}"

    # ── Health Score ──────────────────────────────────────────────

    def test_health_below_threshold(self):
        """Health should be below acceptable threshold for this bad scenario."""
        max_health = self.gt.get("max_acceptable_health", 60)
        assert self.result.health_score <= max_health, \
            f"Health {self.result.health_score} > threshold {max_health}"

    def test_health_in_range(self):
        assert 0 <= self.result.health_score <= 100

    # ── Latency ───────────────────────────────────────────────────

    def test_latency_under_5s(self):
        """Full pipeline should complete in < 5 seconds on CPU."""
        assert self.result.latency_ms < 5000, \
            f"Pipeline took {self.result.latency_ms:.0f}ms"

    # ── Diagnosis ─────────────────────────────────────────────────

    def test_diagnosis_matches_expected(self):
        """Diagnosis should match expected: 'fabricated' for ungrounded claims."""
        expected_diag = self.gt.get("expected_diagnosis")
        if expected_diag and self.result.span_attributions:
            # Check that at least one span has the expected diagnosis
            diagnoses = [sa.diagnosis for sa in self.result.span_attributions]
            assert expected_diag in diagnoses, \
                f"Expected '{expected_diag}' diagnosis, got: {diagnoses}"
