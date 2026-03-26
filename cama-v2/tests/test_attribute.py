"""Tests for cama/attribute.py — LOO attribution."""

from unittest.mock import MagicMock

import pytest

from cama.attribute import LOODetectorAttributor
from cama.detect import Detector
from cama.types import (
    HallucinatedSpan,
    Memory,
    MemoryAttribution,
    SpanAttribution,
    TokenScore,
)


class MockDetector(Detector):
    """Mock detector that returns configurable scores."""

    def __init__(self, score_map: dict[str, list[float]] | None = None):
        """
        score_map: maps a 'context_key' to per-token hallucination scores.
        context_key = sorted comma-joined memory contents.
        """
        self._score_map = score_map or {}
        self._call_count = 0

    def detect(self, memories, question, answer):
        self._call_count += 1
        key = ",".join(sorted(memories))

        if key in self._score_map:
            scores = self._score_map[key]
        else:
            # Default: return 0.3 for all tokens
            scores = [0.3] * 5

        tokens = []
        for i, score in enumerate(scores):
            tokens.append(TokenScore(token=f"tok{i}", index=i, hallucination_prob=score))

        spans = []
        # Build spans from consecutive tokens > 0.5
        current = []
        for ts in tokens:
            if ts.hallucination_prob > 0.5:
                current.append(ts)
            else:
                if current:
                    spans.append(HallucinatedSpan(
                        text=" ".join(t.token for t in current),
                        start_char=0, end_char=10,
                        score=sum(t.hallucination_prob for t in current) / len(current),
                        token_scores=current,
                    ))
                    current = []
        if current:
            spans.append(HallucinatedSpan(
                text=" ".join(t.token for t in current),
                start_char=0, end_char=10,
                score=sum(t.hallucination_prob for t in current) / len(current),
                token_scores=current,
            ))

        return tokens, spans


class TestLOODetectorAttributor:
    def test_basic_attribution(self):
        """Test that removing a causing memory decreases hallucination score."""
        # Full context (both memories): tokens 2,3 are hallucinated
        full_key = ",".join(sorted(["correct fact", "wrong fact"]))
        # Without "wrong fact": tokens 2,3 have lower hallucination
        without_wrong_key = "correct fact"
        # Without "correct fact": tokens 2,3 have higher hallucination
        without_correct_key = "wrong fact"

        detector = MockDetector({
            full_key: [0.1, 0.2, 0.8, 0.9, 0.1],        # baseline
            without_wrong_key: [0.1, 0.2, 0.3, 0.3, 0.1],  # removing wrong → less hallucination
            without_correct_key: [0.1, 0.2, 0.9, 0.95, 0.1],  # removing correct → more hallucination
        })

        memories = [
            Memory(id="m1", content="correct fact"),
            Memory(id="m2", content="wrong fact"),
        ]

        baseline_scores = [
            TokenScore(token=f"tok{i}", index=i, hallucination_prob=p)
            for i, p in enumerate([0.1, 0.2, 0.8, 0.9, 0.1])
        ]

        spans = [HallucinatedSpan(
            text="tok2 tok3",
            start_char=0, end_char=10,
            score=0.85,
            token_scores=[baseline_scores[2], baseline_scores[3]],
        )]

        attributor = LOODetectorAttributor(detector)
        results = attributor.attribute(memories, "question", "answer", baseline_scores, spans)

        assert len(results) == 1
        sa = results[0]

        # Find attributions
        m1_attr = next(a for a in sa.attributions if a.memory_id == "m1")
        m2_attr = next(a for a in sa.attributions if a.memory_id == "m2")

        # m2 (wrong fact) should have negative delta → causing
        # because removing it decreased hallucination scores
        assert m2_attr.delta < 0, f"Expected negative delta for causing memory, got {m2_attr.delta}"
        assert m2_attr.direction == "causing"

        # m1 (correct fact) should have positive delta → supporting
        # because removing it increased hallucination scores
        assert m1_attr.delta > 0, f"Expected positive delta for supporting memory, got {m1_attr.delta}"
        assert m1_attr.direction == "supporting"

    def test_ghost_detection(self):
        """Test that irrelevant memories get ghost direction."""
        # Both contexts give same scores → memory is irrelevant
        full_key = ",".join(sorted(["relevant fact", "random note"]))
        without_random_key = "relevant fact"
        without_relevant_key = "random note"

        detector = MockDetector({
            full_key: [0.1, 0.2, 0.8, 0.1, 0.1],
            without_random_key: [0.1, 0.2, 0.8, 0.1, 0.1],    # same! ghost
            without_relevant_key: [0.1, 0.2, 0.95, 0.1, 0.1],  # worse → relevant supports
        })

        memories = [
            Memory(id="m1", content="relevant fact"),
            Memory(id="m2", content="random note"),
        ]

        baseline_scores = [
            TokenScore(token=f"tok{i}", index=i, hallucination_prob=p)
            for i, p in enumerate([0.1, 0.2, 0.8, 0.1, 0.1])
        ]

        spans = [HallucinatedSpan(
            text="tok2",
            start_char=0, end_char=4,
            score=0.8,
            token_scores=[baseline_scores[2]],
        )]

        attributor = LOODetectorAttributor(detector)
        results = attributor.attribute(memories, "q", "a", baseline_scores, spans)

        m2_attr = next(a for a in results[0].attributions if a.memory_id == "m2")
        assert m2_attr.direction == "ghost"

    def test_empty_spans(self):
        detector = MockDetector()
        attributor = LOODetectorAttributor(detector)
        results = attributor.attribute(
            [Memory(id="m1", content="x")], "q", "a", [], [],
        )
        assert results == []

    def test_empty_memories(self):
        detector = MockDetector()
        attributor = LOODetectorAttributor(detector)
        baseline = [TokenScore(token="t", index=0, hallucination_prob=0.8)]
        spans = [HallucinatedSpan(
            text="t", start_char=0, end_char=1, score=0.8, token_scores=baseline,
        )]
        results = attributor.attribute([], "q", "a", baseline, spans)
        assert results == []

    def test_mas_normalization(self):
        """MAS values should sum to 1 across memories for each span."""
        full_key = ",".join(sorted(["a", "b", "c"]))
        detector = MockDetector({
            full_key: [0.8, 0.8],
            ",".join(sorted(["b", "c"])): [0.9, 0.9],
            ",".join(sorted(["a", "c"])): [0.6, 0.6],
            ",".join(sorted(["a", "b"])): [0.8, 0.8],
        })

        memories = [
            Memory(id="m1", content="a"),
            Memory(id="m2", content="b"),
            Memory(id="m3", content="c"),
        ]

        baseline = [
            TokenScore(token="t0", index=0, hallucination_prob=0.8),
            TokenScore(token="t1", index=1, hallucination_prob=0.8),
        ]
        spans = [HallucinatedSpan(
            text="t0 t1", start_char=0, end_char=5, score=0.8,
            token_scores=baseline,
        )]

        attributor = LOODetectorAttributor(detector)
        results = attributor.attribute(memories, "q", "a", baseline, spans)

        total_mas = sum(a.mas for a in results[0].attributions)
        assert abs(total_mas - 1.0) < 0.01, f"MAS sum = {total_mas}, expected ~1.0"

    def test_call_count(self):
        """Should make K+1 detector calls (1 baseline already done + K ablations)."""
        detector = MockDetector()
        memories = [
            Memory(id=f"m{i}", content=f"content {i}")
            for i in range(5)
        ]
        baseline = [TokenScore(token="t", index=0, hallucination_prob=0.8)]
        spans = [HallucinatedSpan(
            text="t", start_char=0, end_char=1, score=0.8, token_scores=baseline,
        )]

        attributor = LOODetectorAttributor(detector)
        attributor.attribute(memories, "q", "a", baseline, spans)

        # Should call detector K times (once per memory ablation)
        assert detector._call_count == 5
