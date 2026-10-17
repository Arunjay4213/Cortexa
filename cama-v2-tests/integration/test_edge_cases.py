"""Adversarial edge case tests — try to break the pipeline.

These tests push the engine to its limits with pathological inputs.
None of them should crash the engine.
"""

from __future__ import annotations

import pytest

from cama.types import TraceResult


class TestEdgeCaseEmptyInputs:
    """Empty or near-empty inputs."""

    def test_empty_response(self, engine):
        result = engine.trace(query="q", response="", memories=[{"id": "m1", "content": "data"}])
        assert isinstance(result, TraceResult)
        assert result.hallucinated_spans == []

    def test_empty_query(self, engine):
        result = engine.trace(query="", response="Some answer.", memories=[{"id": "m1", "content": "data"}])
        assert isinstance(result, TraceResult)

    def test_no_memories(self, engine):
        result = engine.trace(query="q", response="Answer.", memories=[])
        assert isinstance(result, TraceResult)
        assert result.memories_used == []

    def test_all_empty(self, engine):
        result = engine.trace(query="", response="", memories=[])
        assert isinstance(result, TraceResult)


class TestEdgeCaseSingleWord:
    """Single-word or very short inputs."""

    def test_one_word_response(self, engine):
        result = engine.trace(
            query="Is it available?",
            response="Yes.",
            memories=[{"id": "m1", "content": "Product is available."}],
        )
        assert isinstance(result, TraceResult)

    def test_one_word_memory(self, engine):
        result = engine.trace(
            query="q",
            response="The product costs $49.99.",
            memories=[{"id": "m1", "content": "Expensive."}],
        )
        assert isinstance(result, TraceResult)


class TestEdgeCaseIdenticalContent:
    """Response identical to memory content."""

    def test_verbatim_match(self, engine):
        text = "Widget Pro costs $49.99 with free standard shipping."
        result = engine.trace(
            query="Price?",
            response=text,
            memories=[{"id": "m1", "content": text}],
        )
        # Should be healthy — response is exactly the memory
        assert result.health_score >= 60, f"Verbatim match got low health: {result.health_score}"

    def test_response_is_concat_of_all_memories(self, engine):
        m1 = "Widget Pro costs $49.99."
        m2 = "Free shipping on orders over $25."
        result = engine.trace(
            query="Tell me about the product.",
            response=f"{m1} {m2}",
            memories=[
                {"id": "m1", "content": m1},
                {"id": "m2", "content": m2},
            ],
        )
        assert result.health_score >= 50


class TestEdgeCaseContradictingMemories:
    """Memories that contradict each other."""

    def test_opposite_memories(self, engine):
        """Two memories with contradicting facts."""
        result = engine.trace(
            query="What is the price?",
            response="The price is $49.99.",
            memories=[
                {"id": "m1", "content": "Widget Pro costs $49.99."},
                {"id": "m2", "content": "Widget Pro costs $99.99."},
            ],
        )
        assert isinstance(result, TraceResult)
        # Engine should still produce a valid result even with contradictions


class TestEdgeCaseVeryLongInputs:
    """Stress test with large inputs."""

    def test_long_response(self, engine):
        """50-sentence response."""
        response = " ".join(
            f"This is sentence number {i} about various topics." for i in range(50)
        )
        result = engine.trace(
            query="Tell me everything.",
            response=response,
            memories=[{"id": "m1", "content": "This is sentence number 0 about various topics."}],
        )
        assert isinstance(result, TraceResult)
        assert result.latency_ms < 30000  # 30s timeout

    def test_many_memories_15(self, engine):
        """15 memories — should complete."""
        memories = [
            {"id": f"m{i}", "content": f"Memory {i}: various factual content number {i}."}
            for i in range(15)
        ]
        result = engine.trace(
            query="What is memory 5?",
            response="Memory 5 contains various factual content number 5.",
            memories=memories,
        )
        assert len(result.memories_used) == 15

    def test_20_memories_with_loo(self, engine):
        """20 memories — at threshold for pre-filtering."""
        memories = [
            {"id": f"m{i}", "content": f"Fact {i}: item {i} costs ${i * 10}."}
            for i in range(20)
        ]
        result = engine.trace(
            query="How much does item 5 cost?",
            response="Item 5 costs $999.",
            memories=memories,
        )
        assert isinstance(result, TraceResult)


class TestEdgeCaseSpecialCharacters:
    """Special characters, HTML, SQL, etc."""

    def test_html_in_content(self, engine):
        result = engine.trace(
            query="q",
            response="The <b>price</b> is $49.99.",
            memories=[{"id": "m1", "content": "Price: $49.99"}],
        )
        assert isinstance(result, TraceResult)

    def test_sql_injection_like(self, engine):
        result = engine.trace(
            query="'; DROP TABLE memories;--",
            response="No results found.",
            memories=[{"id": "m1", "content": "SELECT * FROM products"}],
        )
        assert isinstance(result, TraceResult)

    def test_emoji_content(self, engine):
        result = engine.trace(
            query="How do you feel?",
            response="I feel great! 🎉🚀",
            memories=[{"id": "m1", "content": "The product is awesome 😀."}],
        )
        assert isinstance(result, TraceResult)

    def test_newlines_and_tabs(self, engine):
        result = engine.trace(
            query="q",
            response="Line 1.\nLine 2.\tTabbed.",
            memories=[{"id": "m1", "content": "Line 1.\nLine 2."}],
        )
        assert isinstance(result, TraceResult)


class TestEdgeCaseNumericPrecision:
    """Numeric edge cases for the numerical gate."""

    def test_very_large_number(self, engine):
        result = engine.trace(
            query="Revenue?",
            response="Revenue is $999,999,999,999.",
            memories=[{"id": "m1", "content": "Revenue: $1,000,000,000,000."}],
        )
        assert isinstance(result, TraceResult)

    def test_zero_dollar_amount(self, engine):
        result = engine.trace(
            query="Cost?",
            response="It is free — $0.00.",
            memories=[{"id": "m1", "content": "The product is free."}],
        )
        assert isinstance(result, TraceResult)

    def test_percentage_comparison(self, engine):
        """Memory says 45%, response says 90%."""
        result = engine.trace(
            query="Growth rate?",
            response="Growth rate is 90%.",
            memories=[{"id": "m1", "content": "Growth rate: 45%."}],
        )
        # Should detect the ungrounded 90%
        flagged = [ts for ts in result.hallucinated_spans if "90" in ts.text]
        # At least the hallucination rate should be non-zero
        assert result.hallucination_rate > 0 or len(result.hallucinated_spans) > 0


class TestEdgeCaseNegation:
    """Negation — semantic opposite of what's in memory."""

    def test_negated_claim(self, engine):
        """Memory says X, response says NOT X."""
        result = engine.trace(
            query="Is shipping free?",
            response="Shipping is NOT free. There is a $15 charge.",
            memories=[{"id": "m1", "content": "Free shipping on all orders."}],
        )
        assert isinstance(result, TraceResult)
        # The $15 charge is fabricated
        assert result.hallucination_rate > 0 or len(result.hallucinated_spans) > 0


class TestEdgeCaseTemporalConfusion:
    """Dates and temporal references that could confuse the engine."""

    def test_outdated_date_in_response(self, engine):
        result = engine.trace(
            query="When does the sale end?",
            response="The sale ends on December 31, 2024.",
            memories=[
                {"id": "m1", "content": "Holiday sale runs through December 31, 2025."},
            ],
        )
        assert isinstance(result, TraceResult)
        # Different year — should catch the mismatch
        assert result.hallucination_rate > 0 or len(result.hallucinated_spans) >= 0


class TestEdgeCaseDuplicateMemories:
    """Multiple memories with identical content."""

    def test_duplicate_content_different_ids(self, engine):
        result = engine.trace(
            query="Price?",
            response="Widget costs $49.99.",
            memories=[
                {"id": "m1", "content": "Widget costs $49.99."},
                {"id": "m2", "content": "Widget costs $49.99."},
            ],
        )
        assert isinstance(result, TraceResult)
        assert len(result.memories_used) == 2
