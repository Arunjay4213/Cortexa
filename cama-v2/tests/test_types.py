"""Tests for cama/types.py — Pydantic data models."""

from datetime import datetime, timedelta

import pytest

from cama.types import (
    Contradiction,
    HallucinatedSpan,
    Memory,
    MemoryAttribution,
    SpanAttribution,
    TokenScore,
    TraceResult,
)


class TestMemory:
    def test_minimal_creation(self):
        m = Memory(id="m1", content="Hello world")
        assert m.id == "m1"
        assert m.content == "Hello world"
        assert m.source is None
        assert m.metadata == {}

    def test_full_creation(self):
        now = datetime.now()
        m = Memory(
            id="m2",
            content="Test content",
            source="https://example.com",
            source_updated_at=now + timedelta(days=1),
            created_at=now,
            metadata={"key": "value"},
        )
        assert m.source == "https://example.com"
        assert m.source_updated_at > m.created_at
        assert m.metadata["key"] == "value"

    def test_from_dict(self):
        d = {"id": "m3", "content": "Dict content"}
        m = Memory(**d)
        assert m.id == "m3"

    def test_created_at_default(self):
        m = Memory(id="m4", content="Auto date")
        assert isinstance(m.created_at, datetime)


class TestTokenScore:
    def test_creation(self):
        ts = TokenScore(token="hello", index=0, hallucination_prob=0.8)
        assert ts.token == "hello"
        assert ts.index == 0
        assert ts.hallucination_prob == 0.8


class TestHallucinatedSpan:
    def test_creation(self):
        tokens = [
            TokenScore(token="69", index=5, hallucination_prob=0.9),
            TokenScore(token="million", index=6, hallucination_prob=0.85),
        ]
        span = HallucinatedSpan(
            text="69 million",
            start_char=40,
            end_char=50,
            score=0.875,
            token_scores=tokens,
        )
        assert span.text == "69 million"
        assert len(span.token_scores) == 2
        assert span.score == 0.875


class TestMemoryAttribution:
    def test_supporting(self):
        a = MemoryAttribution(
            memory_id="m1", mas=0.6, delta=0.15, direction="supporting",
        )
        assert a.direction == "supporting"
        assert a.mas == 0.6

    def test_causing(self):
        a = MemoryAttribution(
            memory_id="m2", mas=0.3, delta=-0.1, direction="causing",
        )
        assert a.direction == "causing"


class TestSpanAttribution:
    def test_creation(self):
        span = HallucinatedSpan(
            text="test", start_char=0, end_char=4, score=0.8,
            token_scores=[TokenScore(token="test", index=0, hallucination_prob=0.8)],
        )
        sa = SpanAttribution(
            span=span,
            attributions=[
                MemoryAttribution(memory_id="m1", mas=0.7, delta=-0.2, direction="causing"),
            ],
            diagnosis="wrong_memory",
            culprit_memory_id="m1",
        )
        assert sa.diagnosis == "wrong_memory"
        assert sa.culprit_memory_id == "m1"


class TestContradiction:
    def test_creation(self):
        c = Contradiction(
            memory_id_1="m1",
            memory_id_2="m2",
            explanation="m1 says X, m2 says not X",
            span_text="conflicting claim",
        )
        assert c.memory_id_1 == "m1"
        assert c.span_text == "conflicting claim"

    def test_no_span(self):
        c = Contradiction(
            memory_id_1="m1",
            memory_id_2="m2",
            explanation="NLI contradiction",
        )
        assert c.span_text is None


class TestTraceResult:
    def test_full_result(self):
        result = TraceResult(
            query="What is X?",
            response="X is Y.",
            memories_used=["m1", "m2"],
            hallucinated_spans=[],
            span_attributions=[],
            ghost_memories=["m2"],
            contradictions=[],
            stale_memories=[],
            health_score=85.0,
            hallucination_rate=0.0,
            latency_ms=42.5,
            detection_method="LettuceDetector",
            attribution_method="LOODetectorAttributor",
        )
        assert result.health_score == 85.0
        assert result.detection_method == "LettuceDetector"
        assert len(result.ghost_memories) == 1
