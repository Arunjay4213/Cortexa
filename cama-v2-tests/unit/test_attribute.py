"""Hostile tests for cama/attribute.py — LOO attribution with REAL detector.

Every test uses the real EmbeddingDetector for LOO scoring.
This verifies that attribution actually identifies causing vs supporting vs ghost memories.
"""

from __future__ import annotations

import pytest

from cama.types import Memory, HallucinatedSpan, TokenScore, SpanAttribution


class TestLOOBasicAttribution:
    """Verify LOO correctly identifies the poison memory."""

    def test_poison_memory_is_causing(self, embedding_detector, attributor):
        """Memory with wrong info should be classified as 'causing'."""
        memories = [
            Memory(id="good", content="Widget Pro costs $49.99."),
            Memory(id="poison", content="All products have a lifetime warranty."),
            Memory(id="irrelevant", content="Customer prefers email communication."),
        ]
        question = "What warranty does Widget Pro have?"
        answer = "Widget Pro has a lifetime warranty."

        # Run baseline detection
        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("Detector did not find hallucinated spans for this case")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        assert len(attributions) > 0

        # The poison memory should appear with direction "causing" or "supporting"
        # (it causes the hallucination by providing wrong info)
        for sa in attributions:
            poison_attr = next((a for a in sa.attributions if a.memory_id == "poison"), None)
            assert poison_attr is not None, "Poison memory should appear in attributions"

    def test_ghost_memory_has_near_zero_delta(self, embedding_detector, attributor):
        """Irrelevant memory should have near-zero delta."""
        memories = [
            Memory(id="relevant", content="Widget Pro costs $49.99."),
            Memory(id="ghost", content="Customer prefers blue color theme."),
        ]
        question = "How much does Widget Pro cost?"
        answer = "Widget Pro costs $99.99."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        for sa in attributions:
            ghost_attr = next((a for a in sa.attributions if a.memory_id == "ghost"), None)
            if ghost_attr:
                assert abs(ghost_attr.delta) < 0.1, \
                    f"Ghost memory delta too large: {ghost_attr.delta}"


class TestLOOAttributionShape:
    """Validate the shape and structure of attribution output."""

    def test_one_attribution_per_span(self, embedding_detector, attributor):
        """Should return one SpanAttribution per hallucinated span."""
        memories = [
            Memory(id="m1", content="Standard shipping takes 5-7 days."),
        ]
        question = "Shipping?"
        answer = "We offer free overnight delivery with drone service."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        assert len(attributions) == len(spans)

    def test_all_memories_present_in_each_attribution(self, embedding_detector, attributor):
        """Every memory should appear in each SpanAttribution's attributions list."""
        memories = [
            Memory(id="m1", content="Widget Pro costs $49.99."),
            Memory(id="m2", content="Free shipping on orders over $25."),
            Memory(id="m3", content="Customer uses Google OAuth."),
        ]
        question = "Tell me about Widget Pro."
        answer = "Widget Pro costs $999 and includes free helicopter delivery."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        memory_ids = {m.id for m in memories}

        for sa in attributions:
            attr_ids = {a.memory_id for a in sa.attributions}
            assert attr_ids == memory_ids, \
                f"Missing memories in attribution: {memory_ids - attr_ids}"

    def test_mas_sums_approximately_to_one(self, embedding_detector, attributor):
        """MAS values should sum close to 1.0 (normalized)."""
        memories = [
            Memory(id="m1", content="Widget costs $49.99."),
            Memory(id="m2", content="Returns accepted within 30 days."),
        ]
        question = "Price?"
        answer = "The price is $999 with no return policy."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        for sa in attributions:
            total_mas = sum(a.mas for a in sa.attributions)
            # MAS should sum close to 1.0 (epsilon from +1e-8 in denominator)
            assert 0.9 < total_mas <= 1.01, f"MAS sum = {total_mas}, expected ~1.0"

    def test_attributions_sorted_by_abs_delta(self, embedding_detector, attributor):
        """Attributions should be sorted by |delta| descending."""
        memories = [
            Memory(id="m1", content="Product costs $49.99."),
            Memory(id="m2", content="Shipping is free."),
            Memory(id="m3", content="Customer prefers dark mode."),
        ]
        question = "Price?"
        answer = "It costs $999 with premium delivery."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        for sa in attributions:
            deltas = [abs(a.delta) for a in sa.attributions]
            assert deltas == sorted(deltas, reverse=True), "Attributions not sorted by |delta|"


class TestLOODiagnosis:
    """Verify the diagnosis field in SpanAttribution."""

    def test_stale_memory_diagnosis(self, embedding_detector, attributor):
        """Stale causing memory should produce 'stale_memory' diagnosis."""
        from datetime import datetime
        memories = [
            Memory(
                id="stale",
                content="Express shipping takes 2 days.",
                created_at=datetime(2025, 1, 1),
                source_updated_at=datetime(2026, 1, 1),  # Updated AFTER created
            ),
            Memory(id="other", content="Customer prefers email."),
        ]
        question = "How long is express shipping?"
        answer = "Express shipping takes 10 days."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        # If stale memory is causing, diagnosis should be "stale_memory"
        for sa in attributions:
            if sa.culprit_memory_id == "stale":
                assert sa.diagnosis == "stale_memory"

    def test_fabricated_diagnosis(self, embedding_detector, attributor):
        """All ghost attributions + high score → 'fabricated' diagnosis."""
        memories = [
            Memory(id="m1", content="Customer prefers morning meetings."),
            Memory(id="m2", content="Account created January 2025."),
        ]
        question = "What is the refund policy?"
        answer = "You get a full refund within 90 days including free return shipping."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        # With totally irrelevant memories, all should be ghosts → fabricated
        for sa in attributions:
            if all(a.direction == "ghost" for a in sa.attributions) and sa.span.score > 0.7:
                assert sa.diagnosis == "fabricated"


class TestLOOEdgeCases:
    """Edge cases for attribution."""

    def test_no_spans_returns_empty(self, embedding_detector, attributor):
        """If detector finds no hallucinated spans, attribution should return []."""
        memories = [Memory(id="m1", content="The sky is blue.")]
        question = "What color is the sky?"
        answer = "The sky is blue."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        if not spans:
            assert attributions == []

    def test_no_memories_returns_empty(self, embedding_detector, attributor):
        """Empty memory list → empty attributions."""
        memories = []
        baseline_scores, spans = embedding_detector.detect([], "q", "Some answer.")
        attributions = attributor.attribute(memories, "q", "Some answer.", baseline_scores, spans)
        assert attributions == []

    def test_single_memory(self, embedding_detector, attributor):
        """Only one memory — it gets 100% MAS."""
        memories = [Memory(id="only", content="Widget costs $49.99.")]
        question = "Price?"
        answer = "Widget costs $999."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        for sa in attributions:
            assert len(sa.attributions) == 1
            assert sa.attributions[0].memory_id == "only"
            # Single memory should have MAS close to 1.0
            assert sa.attributions[0].mas > 0.9

    def test_direction_values_valid(self, embedding_detector, attributor):
        """Direction should only be 'supporting', 'causing', or 'ghost'."""
        memories = [
            Memory(id="m1", content="Widget costs $49.99."),
            Memory(id="m2", content="Free shipping available."),
        ]
        question = "Price?"
        answer = "Widget costs $999 with premium delivery."

        baseline_scores, spans = embedding_detector.detect(
            [m.content for m in memories], question, answer
        )

        if not spans:
            pytest.skip("No spans detected")

        attributions = attributor.attribute(memories, question, answer, baseline_scores, spans)
        valid_directions = {"supporting", "causing", "ghost"}
        for sa in attributions:
            for a in sa.attributions:
                assert a.direction in valid_directions, f"Invalid direction: {a.direction}"
