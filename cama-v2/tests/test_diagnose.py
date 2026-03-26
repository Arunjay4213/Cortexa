"""Tests for cama/diagnose.py — ghost/contradiction/stale/health."""

from datetime import datetime, timedelta

import pytest

from cama.diagnose import Diagnoser
from cama.types import (
    Contradiction,
    HallucinatedSpan,
    Memory,
    MemoryAttribution,
    SpanAttribution,
    TokenScore,
    TraceResult,
)


@pytest.fixture
def diagnoser():
    return Diagnoser()


def _make_span(text: str = "test span") -> HallucinatedSpan:
    return HallucinatedSpan(
        text=text, start_char=0, end_char=len(text), score=0.8,
        token_scores=[TokenScore(token=text, index=0, hallucination_prob=0.8)],
    )


def _make_attribution(
    memory_id: str, delta: float, direction: str, mas: float = 0.5,
) -> MemoryAttribution:
    # Derive raw scores from direction so contradiction tests work
    raw_contra = 0.8 if direction == "causing" else 0.1
    raw_ent = 0.8 if direction == "supporting" else 0.1
    return MemoryAttribution(
        memory_id=memory_id, mas=mas, delta=delta, direction=direction,
        raw_contradiction=raw_contra, raw_entailment=raw_ent,
    )


class TestDetectGhosts:
    def test_basic_ghost(self, diagnoser):
        memories = [
            Memory(id="m1", content="relevant"),
            Memory(id="m2", content="irrelevant"),
        ]
        span_attrs = [SpanAttribution(
            span=_make_span(),
            attributions=[
                _make_attribution("m1", 0.15, "supporting", 0.9),
                _make_attribution("m2", 0.001, "ghost", 0.01),
            ],
            diagnosis="supported",
            culprit_memory_id=None,
        )]

        ghosts = diagnoser.detect_ghosts(memories, span_attrs)
        assert "m2" in ghosts
        assert "m1" not in ghosts

    def test_no_ghosts(self, diagnoser):
        memories = [Memory(id="m1", content="relevant")]
        span_attrs = [SpanAttribution(
            span=_make_span(),
            attributions=[_make_attribution("m1", 0.2, "supporting", 0.9)],
            diagnosis="supported",
            culprit_memory_id=None,
        )]

        ghosts = diagnoser.detect_ghosts(memories, span_attrs)
        assert ghosts == []

    def test_no_spans_no_ghosts(self, diagnoser):
        memories = [Memory(id="m1", content="x")]
        ghosts = diagnoser.detect_ghosts(memories, [])
        assert ghosts == []

    def test_all_ghosts(self, diagnoser):
        memories = [
            Memory(id="m1", content="a"),
            Memory(id="m2", content="b"),
        ]
        span_attrs = [SpanAttribution(
            span=_make_span(),
            attributions=[
                _make_attribution("m1", 0.001, "ghost", 0.01),
                _make_attribution("m2", -0.001, "ghost", 0.01),
            ],
            diagnosis="fabricated",
            culprit_memory_id=None,
        )]

        ghosts = diagnoser.detect_ghosts(memories, span_attrs)
        assert set(ghosts) == {"m1", "m2"}


class TestDetectContradictions:
    def test_attribution_based(self, diagnoser):
        memories = [
            Memory(id="m1", content="A"),
            Memory(id="m2", content="B"),
        ]
        span_attrs = [SpanAttribution(
            span=_make_span("conflicting claim"),
            attributions=[
                _make_attribution("m1", 0.3, "supporting", 0.5),
                _make_attribution("m2", -0.25, "causing", 0.4),
            ],
            diagnosis="wrong_memory",
            culprit_memory_id="m2",
        )]

        contradictions = diagnoser.detect_contradictions(memories, span_attrs)
        assert len(contradictions) == 1
        assert {contradictions[0].memory_id_1, contradictions[0].memory_id_2} == {"m1", "m2"}

    def test_no_contradictions(self, diagnoser):
        memories = [Memory(id="m1", content="A")]
        span_attrs = [SpanAttribution(
            span=_make_span(),
            attributions=[_make_attribution("m1", 0.2, "supporting", 1.0)],
            diagnosis="supported",
            culprit_memory_id=None,
        )]

        contradictions = diagnoser.detect_contradictions(memories, span_attrs)
        assert contradictions == []

    def test_dedup_pairs(self, diagnoser):
        """Same pair shouldn't appear twice even from multiple spans."""
        memories = [
            Memory(id="m1", content="A"),
            Memory(id="m2", content="B"),
        ]
        span_attrs = [
            SpanAttribution(
                span=_make_span("span1"),
                attributions=[
                    _make_attribution("m1", 0.3, "supporting", 0.5),
                    _make_attribution("m2", -0.25, "causing", 0.4),
                ],
                diagnosis="wrong_memory",
                culprit_memory_id="m2",
            ),
            SpanAttribution(
                span=_make_span("span2"),
                attributions=[
                    _make_attribution("m1", 0.2, "supporting", 0.5),
                    _make_attribution("m2", -0.15, "causing", 0.4),
                ],
                diagnosis="wrong_memory",
                culprit_memory_id="m2",
            ),
        ]

        contradictions = diagnoser.detect_contradictions(memories, span_attrs)
        assert len(contradictions) == 1


class TestDetectStale:
    def test_stale_memory(self, diagnoser):
        now = datetime.now()
        memories = [
            Memory(
                id="m1", content="old info",
                created_at=now - timedelta(days=30),
                source_updated_at=now - timedelta(days=1),
            ),
        ]
        stale = diagnoser.detect_stale(memories)
        assert "m1" in stale

    def test_fresh_memory(self, diagnoser):
        now = datetime.now()
        memories = [
            Memory(
                id="m1", content="fresh",
                created_at=now,
                source_updated_at=now - timedelta(days=1),
            ),
        ]
        stale = diagnoser.detect_stale(memories)
        assert stale == []

    def test_no_timestamps(self, diagnoser):
        memories = [Memory(id="m1", content="no dates")]
        stale = diagnoser.detect_stale(memories)
        assert stale == []


class TestComputeHealth:
    def test_perfect_health(self, diagnoser):
        result = TraceResult(
            query="q", response="r",
            memories_used=["m1", "m2"],
            hallucinated_spans=[], span_attributions=[],
            ghost_memories=[], contradictions=[], stale_memories=[],
            health_score=0, hallucination_rate=0.0,
            latency_ms=50, detection_method="test", attribution_method="test",
        )
        health = diagnoser.compute_health(result)
        assert health == 100

    def test_all_ghosts(self, diagnoser):
        result = TraceResult(
            query="q", response="r",
            memories_used=["m1", "m2"],
            hallucinated_spans=[], span_attributions=[],
            ghost_memories=["m1", "m2"],
            contradictions=[], stale_memories=[],
            health_score=0, hallucination_rate=0.0,
            latency_ms=50, detection_method="test", attribution_method="test",
        )
        health = diagnoser.compute_health(result)
        assert health == 60  # 100 - (100% * 0.4)

    def test_contradictions(self, diagnoser):
        result = TraceResult(
            query="q", response="r",
            memories_used=["m1", "m2"],
            hallucinated_spans=[], span_attributions=[],
            ghost_memories=[],
            contradictions=[
                Contradiction(memory_id_1="m1", memory_id_2="m2", explanation="x"),
            ],
            stale_memories=[],
            health_score=0, hallucination_rate=0.0,
            latency_ms=50, detection_method="test", attribution_method="test",
        )
        health = diagnoser.compute_health(result)
        assert health == 92  # 100 - 8

    def test_mixed_issues(self, diagnoser):
        result = TraceResult(
            query="q", response="r",
            memories_used=["m1", "m2", "m3", "m4"],
            hallucinated_spans=[], span_attributions=[],
            ghost_memories=["m3", "m4"],  # 50% ghosts → -20
            contradictions=[
                Contradiction(memory_id_1="m1", memory_id_2="m2", explanation="x"),
            ],  # 1 contradiction → -8
            stale_memories=["m1"],  # 25% stale → -6.25
            health_score=0, hallucination_rate=0.05,  # 5% → -5
            latency_ms=50, detection_method="test", attribution_method="test",
        )
        health = diagnoser.compute_health(result)
        # 100 - 20 - 8 - 6.25 - 5 = 60.75 → 61
        assert health == 61

    def test_health_clamped(self, diagnoser):
        result = TraceResult(
            query="q", response="r",
            memories_used=["m1"],
            hallucinated_spans=[], span_attributions=[],
            ghost_memories=["m1"],
            contradictions=[
                Contradiction(memory_id_1="a", memory_id_2="b", explanation="x")
                for _ in range(10)
            ],
            stale_memories=["m1"],
            health_score=0, hallucination_rate=1.0,
            latency_ms=50, detection_method="test", attribution_method="test",
        )
        health = diagnoser.compute_health(result)
        assert health >= 0
        assert health <= 100


class TestEstimateGhostWaste:
    def test_basic_estimate(self, diagnoser):
        ghosts = [
            Memory(id="m1", content="x" * 400),  # ~100 tokens
            Memory(id="m2", content="y" * 200),  # ~50 tokens
        ]
        waste = diagnoser.estimate_ghost_waste(ghosts)
        assert waste["waste_tokens"] == 150
        assert waste["waste_cost_daily"] > 0
        assert waste["waste_cost_monthly"] > 0

    def test_no_ghosts(self, diagnoser):
        waste = diagnoser.estimate_ghost_waste([])
        assert waste["waste_tokens"] == 0
        assert waste["waste_cost_monthly"] == 0
