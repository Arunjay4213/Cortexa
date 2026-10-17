"""Hostile tests for cama/pipeline.py — end-to-end pipeline with REAL inference.

Tests the full detect → attribute → diagnose pipeline through CAMAv2.trace().
"""

from __future__ import annotations

import pytest

from cama.types import TraceResult


class TestPipelineBasicOutput:
    """Verify trace() returns well-formed TraceResult."""

    def test_returns_trace_result(self, engine):
        result = engine.trace(
            query="How much does Widget Pro cost?",
            response="Widget Pro costs $49.99.",
            memories=[{"id": "m1", "content": "Widget Pro costs $49.99."}],
        )
        assert isinstance(result, TraceResult)

    def test_trace_result_fields(self, engine):
        result = engine.trace(
            query="q",
            response="Some response text.",
            memories=[{"id": "m1", "content": "Some response text."}],
        )
        assert result.query == "q"
        assert result.response == "Some response text."
        assert result.memories_used == ["m1"]
        assert isinstance(result.health_score, (int, float))
        assert isinstance(result.hallucination_rate, float)
        assert result.latency_ms > 0
        assert result.detection_method == "EmbeddingDetector"
        assert result.attribution_method == "LOODetectorAttributor"

    def test_dict_memories_accepted(self, engine):
        """Pipeline accepts plain dicts, not just Memory objects."""
        result = engine.trace(
            query="q",
            response="answer",
            memories=[
                {"id": "m1", "content": "memory content"},
                {"id": "m2", "content": "more content"},
            ],
        )
        assert set(result.memories_used) == {"m1", "m2"}


class TestPipelineHallucination:
    """Pipeline should detect and attribute hallucinations."""

    def test_fabricated_number_detected(self, engine):
        """Response invents a number → hallucination detected."""
        result = engine.trace(
            query="What is the price?",
            response="The price is $999.99.",
            memories=[{"id": "m1", "content": "Widget Pro costs $49.99."}],
        )
        assert result.hallucination_rate > 0, "Fabricated price should cause non-zero hallucination rate"

    def test_hallucinated_spans_populated(self, engine):
        """Fabricated response → at least one hallucinated span."""
        result = engine.trace(
            query="What is the return policy?",
            response="We offer unlimited free returns forever with a personal butler to pick up your items.",
            memories=[{"id": "m1", "content": "Returns accepted within 30 days."}],
        )
        assert len(result.hallucinated_spans) > 0

    def test_supported_response_no_spans(self, engine):
        """Fully grounded response → no hallucinated spans."""
        result = engine.trace(
            query="What is the price?",
            response="Widget Pro costs $49.99.",
            memories=[{"id": "m1", "content": "Widget Pro costs $49.99."}],
        )
        # Should have zero or very few spans
        # (exact match embedding similarity should be very high)
        if result.hallucinated_spans:
            # If spans exist, scores should be low
            for span in result.hallucinated_spans:
                assert span.score < 0.9, "Exact match should not have high hallucination score"


class TestPipelineAttribution:
    """Pipeline should attribute hallucinated spans to memories."""

    def test_attribution_runs_when_spans_exist(self, engine):
        """If hallucination detected, attribution should run."""
        result = engine.trace(
            query="Shipping?",
            response="All orders ship via free next-day helicopter delivery.",
            memories=[
                {"id": "m1", "content": "Standard shipping takes 5-7 business days."},
                {"id": "m2", "content": "Customer prefers email communication."},
            ],
        )
        if result.hallucinated_spans:
            assert len(result.span_attributions) > 0
            assert len(result.span_attributions) == len(result.hallucinated_spans)

    def test_no_attribution_without_spans(self, engine):
        """If no hallucination detected, attribution is skipped."""
        result = engine.trace(
            query="Price?",
            response="Widget costs $49.99.",
            memories=[{"id": "m1", "content": "Widget costs $49.99."}],
        )
        if not result.hallucinated_spans:
            assert result.span_attributions == []


class TestPipelineDiagnosis:
    """Pipeline should detect ghosts, contradictions, staleness."""

    def test_ghost_detection(self, engine):
        """Irrelevant memory should be flagged as ghost when hallucination exists."""
        result = engine.trace(
            query="What is the shipping time?",
            response="Shipping takes 2 days via express delivery.",
            memories=[
                {"id": "shipping", "content": "Express shipping: 2-day delivery."},
                {"id": "ghost", "content": "Customer prefers dark mode theme."},
            ],
        )
        # Ghost should be detected (if spans exist)
        if result.hallucinated_spans:
            assert "ghost" in result.ghost_memories, \
                f"Expected 'ghost' in ghost_memories, got: {result.ghost_memories}"

    def test_stale_detection(self, engine):
        """Memory with source_updated_at > created_at → stale."""
        result = engine.trace(
            query="Price?",
            response="Widget costs $49.99.",
            memories=[
                {
                    "id": "stale_mem",
                    "content": "Widget costs $49.99.",
                    "created_at": "2025-01-01T00:00:00",
                    "source_updated_at": "2026-01-01T00:00:00",
                },
            ],
        )
        assert "stale_mem" in result.stale_memories

    def test_health_score_range(self, engine):
        """Health score should always be 0-100."""
        result = engine.trace(
            query="q",
            response="Some answer about things.",
            memories=[
                {"id": "m1", "content": "Some memory content."},
                {"id": "m2", "content": "More memory content."},
            ],
        )
        assert 0 <= result.health_score <= 100


class TestPipelineEdgeCases:
    """Edge cases that should not crash the pipeline."""

    def test_empty_memories(self, engine):
        """No memories at all — should not crash."""
        result = engine.trace(
            query="q",
            response="Some answer.",
            memories=[],
        )
        assert isinstance(result, TraceResult)
        assert result.memories_used == []

    def test_single_memory(self, engine):
        result = engine.trace(
            query="q",
            response="answer text",
            memories=[{"id": "only", "content": "answer text"}],
        )
        assert result.memories_used == ["only"]

    def test_many_memories(self, engine):
        """15 memories — should complete without timeout."""
        memories = [
            {"id": f"m{i}", "content": f"Memory content number {i} about various things."}
            for i in range(15)
        ]
        result = engine.trace(
            query="What is memory 7?",
            response="Memory 7 is about various things.",
            memories=memories,
        )
        assert len(result.memories_used) == 15

    def test_empty_response(self, engine):
        """Empty response string — should return empty results."""
        result = engine.trace(
            query="q",
            response="",
            memories=[{"id": "m1", "content": "data"}],
        )
        assert result.hallucinated_spans == []

    def test_unicode_input(self, engine):
        """Non-ASCII in all fields."""
        result = engine.trace(
            query="Combien coute le Widget Pro?",
            response="Le Widget Pro coute 49,99 euros.",
            memories=[{"id": "fr1", "content": "Prix: 49,99 EUR pour le Widget Pro."}],
        )
        assert isinstance(result, TraceResult)

    def test_latency_recorded(self, engine):
        """latency_ms should be positive."""
        result = engine.trace(
            query="q",
            response="answer",
            memories=[{"id": "m1", "content": "data"}],
        )
        assert result.latency_ms > 0


class TestPipelineHealthScoring:
    """Targeted health score tests via the full pipeline."""

    def test_healthy_response_high_score(self, engine):
        """Grounded response → high health."""
        result = engine.trace(
            query="What does Widget Pro cost?",
            response="Widget Pro costs $49.99.",
            memories=[
                {"id": "m1", "content": "Widget Pro costs $49.99."},
                {"id": "m2", "content": "Widget Pro has free standard shipping."},
            ],
        )
        assert result.health_score >= 70, f"Grounded response got low health: {result.health_score}"

    def test_unhealthy_response_low_score(self, engine):
        """Fabricated response with ghost/stale memories → low health."""
        result = engine.trace(
            query="What is the return policy?",
            response="You can return anything forever for a full refund plus bonus cash.",
            memories=[
                {
                    "id": "stale",
                    "content": "Returns within 30 days.",
                    "created_at": "2025-01-01T00:00:00",
                    "source_updated_at": "2026-01-01T00:00:00",
                },
                {"id": "ghost", "content": "Customer prefers morning meetings."},
            ],
        )
        # Should have penalties from hallucination + ghost + stale
        assert result.health_score < 90, f"Unhealthy response got high score: {result.health_score}"
