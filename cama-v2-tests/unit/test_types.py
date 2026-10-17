"""Hostile tests for cama/types.py — Pydantic model validation.

Tests that models reject bad input and handle edge cases.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from cama.types import (
    Contradiction,
    HallucinatedSpan,
    Memory,
    MemoryAttribution,
    SpanAttribution,
    TokenScore,
    TraceResult,
)


class TestMemoryValidation:
    def test_empty_id_accepted(self):
        """Empty string id — engine should accept or reject? Document behavior."""
        # Pydantic won't reject empty str by default — this is a gap.
        m = Memory(id="", content="some content")
        assert m.id == ""

    def test_empty_content_accepted(self):
        """Empty content — does the engine handle this gracefully downstream?"""
        m = Memory(id="m1", content="")
        assert m.content == ""

    def test_future_source_updated_at(self):
        """source_updated_at in the future — should be accepted (valid: source changed)."""
        m = Memory(
            id="m1",
            content="data",
            source_updated_at=datetime.now() + timedelta(days=30),
        )
        assert m.source_updated_at > datetime.now()

    def test_source_updated_before_created(self):
        """source_updated_at BEFORE created_at — weird but engine should handle."""
        m = Memory(
            id="m1",
            content="data",
            created_at=datetime.now(),
            source_updated_at=datetime.now() - timedelta(days=100),
        )
        assert m.source_updated_at < m.created_at

    def test_very_long_content(self):
        """Memory with 100KB content — should not crash."""
        content = "x" * 100_000
        m = Memory(id="m1", content=content)
        assert len(m.content) == 100_000

    def test_special_chars_in_id(self):
        """IDs with special characters."""
        m = Memory(id="mem/2847/v2", content="data")
        assert m.id == "mem/2847/v2"

    def test_unicode_content(self):
        """Unicode, emojis, CJK chars in content."""
        m = Memory(id="m1", content="价格是 ¥499 😀 très bien")
        assert "¥499" in m.content


class TestTokenScoreValidation:
    def test_prob_exactly_zero(self):
        ts = TokenScore(token="hello", index=0, hallucination_prob=0.0)
        assert ts.hallucination_prob == 0.0

    def test_prob_exactly_one(self):
        ts = TokenScore(token="hello", index=0, hallucination_prob=1.0)
        assert ts.hallucination_prob == 1.0

    def test_prob_above_one_accepted(self):
        """Does the engine validate prob ∈ [0,1]? Document behavior."""
        # Pydantic float doesn't enforce bounds by default.
        ts = TokenScore(token="x", index=0, hallucination_prob=1.5)
        assert ts.hallucination_prob == 1.5  # No validation — potential bug

    def test_prob_negative_accepted(self):
        """Negative prob — should this be rejected?"""
        ts = TokenScore(token="x", index=0, hallucination_prob=-0.1)
        assert ts.hallucination_prob == -0.1  # No validation — potential bug

    def test_empty_token(self):
        ts = TokenScore(token="", index=0, hallucination_prob=0.5)
        assert ts.token == ""

    def test_negative_index(self):
        """Negative index — should probably be rejected."""
        ts = TokenScore(token="x", index=-1, hallucination_prob=0.5)
        assert ts.index == -1  # No validation


class TestRoundTrip:
    def test_memory_roundtrip(self):
        """create → serialize → deserialize → compare."""
        m = Memory(
            id="m1",
            content="Test content",
            source="test.md",
            source_updated_at=datetime(2025, 6, 1),
            metadata={"key": "value"},
        )
        j = m.model_dump_json()
        m2 = Memory.model_validate_json(j)
        assert m2.id == m.id
        assert m2.content == m.content
        assert m2.source == m.source
        assert m2.metadata == m.metadata

    def test_trace_result_roundtrip(self):
        """Full TraceResult serialize/deserialize."""
        tr = TraceResult(
            query="q",
            response="r",
            memories_used=["m1"],
            hallucinated_spans=[],
            span_attributions=[],
            ghost_memories=["m2"],
            contradictions=[],
            stale_memories=[],
            health_score=85.0,
            hallucination_rate=0.1,
            latency_ms=123.4,
            detection_method="EmbeddingDetector",
            attribution_method="LOODetectorAttributor",
        )
        j = tr.model_dump_json()
        tr2 = TraceResult.model_validate_json(j)
        assert tr2.health_score == tr.health_score
        assert tr2.ghost_memories == tr.ghost_memories

    def test_token_score_in_json(self):
        """TokenScore embedded in HallucinatedSpan roundtrips correctly."""
        ts = TokenScore(token="hello", index=0, hallucination_prob=0.75)
        span = HallucinatedSpan(
            text="hello world",
            start_char=0,
            end_char=11,
            score=0.75,
            token_scores=[ts],
        )
        j = span.model_dump_json()
        span2 = HallucinatedSpan.model_validate_json(j)
        assert span2.token_scores[0].hallucination_prob == 0.75


class TestContradiction:
    def test_same_memory_id_both_sides(self):
        """Contradiction with same memory on both sides — should this be allowed?"""
        c = Contradiction(
            memory_id_1="m1",
            memory_id_2="m1",
            explanation="self-contradiction",
        )
        assert c.memory_id_1 == c.memory_id_2  # Allowed — document as potential issue

    def test_no_span_text(self):
        c = Contradiction(
            memory_id_1="m1",
            memory_id_2="m2",
            explanation="NLI contradiction",
        )
        assert c.span_text is None


class TestSpanAttribution:
    def test_mas_not_summing_to_one(self):
        """MAS values that don't sum to 1.0 — is this validated?"""
        ts = TokenScore(token="x", index=0, hallucination_prob=0.8)
        span = HallucinatedSpan(text="x", start_char=0, end_char=1, score=0.8, token_scores=[ts])
        attrs = [
            MemoryAttribution(memory_id="m1", mas=0.3, delta=0.1, direction="supporting"),
            MemoryAttribution(memory_id="m2", mas=0.3, delta=-0.1, direction="causing"),
        ]
        sa = SpanAttribution(
            span=span,
            attributions=attrs,
            diagnosis="wrong_memory",
            culprit_memory_id="m2",
        )
        total_mas = sum(a.mas for a in sa.attributions)
        # Document: MAS doesn't need to sum to 1.0 at the model level
        assert total_mas != pytest.approx(1.0)
