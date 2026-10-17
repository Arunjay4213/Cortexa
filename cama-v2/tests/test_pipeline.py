"""Tests for cama/pipeline.py — full CAMA v2 pipeline integration."""

from unittest.mock import patch

import pytest

from cama.detect import Detector
from cama.pipeline import CAMAv2
from cama.types import HallucinatedSpan, Memory, TokenScore, TraceResult


class MockDetector(Detector):
    """Deterministic mock detector for pipeline integration tests."""

    def __init__(self):
        self._contexts_seen: list[list[str]] = []

    def detect(self, memories, question, answer):
        self._contexts_seen.append(list(memories))

        # Simulate: if "wrong" is in any memory content, flag tokens 2-3
        has_wrong = any("wrong" in m for m in memories)
        n_tokens = len(answer.split())

        token_scores = []
        for i in range(n_tokens):
            word = answer.split()[i] if i < len(answer.split()) else f"tok{i}"
            prob = 0.8 if (has_wrong and 2 <= i <= 3) else 0.1
            token_scores.append(TokenScore(
                token=word, index=i, hallucination_prob=prob,
            ))

        spans = []
        if has_wrong and n_tokens > 3:
            span_tokens = token_scores[2:4]
            spans.append(HallucinatedSpan(
                text=" ".join(t.token for t in span_tokens),
                start_char=0, end_char=20,
                score=0.8,
                token_scores=span_tokens,
            ))

        return token_scores, spans


class TestCAMAv2Pipeline:
    def test_pipeline_with_mock_detector(self):
        detector = MockDetector()
        cama = CAMAv2(detector=detector)

        result = cama.trace(
            query="What is the price?",
            response="The Widget Pro costs fifty nine dollars today",
            memories=[
                {"id": "m1", "content": "Widget Pro costs $49.99"},
                {"id": "m2", "content": "wrong price is $59.99"},
                {"id": "m3", "content": "User likes dark mode"},
            ],
        )

        assert isinstance(result, TraceResult)
        assert result.query == "What is the price?"
        assert len(result.memories_used) == 3
        assert result.latency_ms > 0
        assert result.detection_method == "MockDetector"
        assert 0 <= result.health_score <= 100

    def test_pipeline_no_hallucinations(self):
        """When detector finds no hallucinations, pipeline should still work."""
        class CleanDetector(Detector):
            def detect(self, memories, question, answer):
                tokens = [
                    TokenScore(token=w, index=i, hallucination_prob=0.1)
                    for i, w in enumerate(answer.split())
                ]
                return tokens, []

        cama = CAMAv2(detector=CleanDetector())
        result = cama.trace(
            query="q",
            response="this is clean",
            memories=[{"id": "m1", "content": "this is clean"}],
        )

        assert result.hallucinated_spans == []
        assert result.span_attributions == []
        assert result.hallucination_rate < 0.5
        assert result.health_score >= 90

    def test_pipeline_empty_memories(self):
        detector = MockDetector()
        cama = CAMAv2(detector=detector)

        result = cama.trace(
            query="q", response="some response here today",
            memories=[],
        )
        assert result.memories_used == []
        assert isinstance(result.health_score, (int, float))

    def test_pipeline_memory_objects(self):
        """Pipeline should accept both dicts and Memory objects."""
        detector = MockDetector()
        cama = CAMAv2(detector=detector)

        mem = Memory(id="m1", content="some fact")
        result = cama.trace(
            query="q", response="some response here today",
            memories=[mem],
        )
        assert result.memories_used == ["m1"]

    def test_stale_detection_in_pipeline(self):
        from datetime import datetime, timedelta

        detector = MockDetector()
        cama = CAMAv2(detector=detector)

        now = datetime.now()
        result = cama.trace(
            query="q", response="some response here today",
            memories=[{
                "id": "m1",
                "content": "wrong outdated info",
                "created_at": (now - timedelta(days=30)).isoformat(),
                "source_updated_at": (now - timedelta(days=1)).isoformat(),
            }],
        )
        assert "m1" in result.stale_memories

    def test_trace_result_completeness(self):
        """All TraceResult fields should be populated."""
        detector = MockDetector()
        cama = CAMAv2(detector=detector)

        result = cama.trace(
            query="test query",
            response="The item costs wrong amount here today",
            memories=[
                {"id": "m1", "content": "correct info"},
                {"id": "m2", "content": "wrong info here"},
            ],
        )

        # Check all fields are present and reasonable
        assert isinstance(result.query, str)
        assert isinstance(result.response, str)
        assert isinstance(result.memories_used, list)
        assert isinstance(result.hallucinated_spans, list)
        assert isinstance(result.span_attributions, list)
        assert isinstance(result.ghost_memories, list)
        assert isinstance(result.contradictions, list)
        assert isinstance(result.stale_memories, list)
        assert isinstance(result.health_score, (int, float))
        assert isinstance(result.hallucination_rate, float)
        assert isinstance(result.latency_ms, float)
        assert isinstance(result.detection_method, str)
        assert isinstance(result.attribution_method, str)
