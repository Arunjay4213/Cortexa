"""Tests for cortexa.engine.scorer — the unified CAMA orchestrator."""

from unittest.mock import MagicMock, patch

from cortexa.engine.models import (
    AuditResult,
    Claim,
    Contradiction,
    EntailmentScore,
    GhostToken,
    Memory,
    StaleMemory,
    TraceResult,
)
from cortexa.engine.scorer import CortexaScorer


class TestComputeHealth:
    def test_perfect_health(self):
        score = CortexaScorer._compute_health_from_counts(
            total=100, ghost_count=0, contradiction_count=0, stale_count=0
        )
        assert score == 100.0

    def test_ghosts_reduce_health(self):
        score = CortexaScorer._compute_health_from_counts(
            total=100, ghost_count=20, contradiction_count=0, stale_count=0
        )
        # ghost_pct = 20%, penalty = 20 * 0.5 = 10
        assert score == 90.0

    def test_contradictions_capped_at_30(self):
        score = CortexaScorer._compute_health_from_counts(
            total=100, ghost_count=0, contradiction_count=10, stale_count=0
        )
        # penalty = min(10 * 5, 30) = 30
        assert score == 70.0

    def test_stale_reduces_health(self):
        score = CortexaScorer._compute_health_from_counts(
            total=100, ghost_count=0, contradiction_count=0, stale_count=50
        )
        # stale_pct = 50%, penalty = 50 * 0.3 = 15
        assert score == 85.0

    def test_combined_penalties(self):
        score = CortexaScorer._compute_health_from_counts(
            total=100, ghost_count=10, contradiction_count=3, stale_count=10
        )
        # ghost: 10% * 0.5 = 5
        # contradiction: min(15, 30) = 15
        # stale: 10% * 0.3 = 3
        assert score == 77.0

    def test_floor_at_zero(self):
        score = CortexaScorer._compute_health_from_counts(
            total=10, ghost_count=10, contradiction_count=6, stale_count=10
        )
        # ghost: 100% * 0.5 = 50, contradiction: 30, stale: 100% * 0.3 = 30 → total penalty 110
        assert score == 0.0

    def test_empty_memories(self):
        score = CortexaScorer._compute_health_from_counts(
            total=0, ghost_count=0, contradiction_count=0, stale_count=0
        )
        assert score == 100.0


class TestScorerTrace:
    """Test the full trace pipeline with mocked entailment backend."""

    def setup_method(self):
        self.scorer = CortexaScorer(
            decompose_mode="fast",
            nli_backend="api",
        )
        # Mock the entailment backend
        self.mock_backend = MagicMock()
        self.scorer.entailment._backend = self.mock_backend

    def test_trace_simple(self):
        """End-to-end trace with mocked NLI."""
        # Mock returns entailment for all pairs
        self.mock_backend.score_pairs.return_value = [(0.1, 0.8, 0.1)]

        memories = [
            Memory(id="m1", content="Premium plan costs $49.99 per month"),
        ]

        result = self.scorer.trace(
            query="How much?",
            response="The price is $49.99",
            memories=memories,
        )

        assert isinstance(result, TraceResult)
        assert result.query == "How much?"
        assert result.response == "The price is $49.99"
        assert len(result.claims) >= 1
        assert result.health_score >= 0.0
        assert result.health_score <= 100.0

    def test_trace_returns_attributions(self):
        self.mock_backend.score_pairs.return_value = [
            (0.1, 0.8, 0.1),
            (0.1, 0.1, 0.8),
        ]

        memories = [
            Memory(id="m1", content="Plan costs $49.99"),
            Memory(id="m2", content="Blue color theme preferred"),
        ]

        result = self.scorer.trace(
            query="price?",
            response="The price is $49.99",
            memories=memories,
        )

        assert len(result.attributions) >= 1

    def test_trace_empty_response(self):
        result = self.scorer.trace(
            query="test", response="", memories=[]
        )
        assert isinstance(result, TraceResult)
        assert result.claims == []
        assert result.health_score == 100.0


class TestScorerAudit:
    def setup_method(self):
        self.scorer = CortexaScorer(decompose_mode="fast", nli_backend="api")

    def test_audit_empty(self):
        result = self.scorer.audit([])
        assert isinstance(result, AuditResult)
        assert result.total_memories == 0
        assert result.health_score == 100.0
        assert len(result.recommendations) >= 1

    def test_audit_with_recent_traces(self):
        memories = [
            Memory(id="m1", content="Test memory 1"),
            Memory(id="m2", content="Test memory 2"),
        ]

        traces = [
            TraceResult(
                query="q", response="r", claims=[], health_score=80.0,
                attributions=[],
                ghost_tokens=[
                    GhostToken(memory_id="m1", max_mas=0.01, waste_tokens=10, reason="low MAS"),
                ],
                contradictions=[
                    Contradiction(
                        memory_id_1="m1", memory_id_2="m2",
                        explanation="test", severity=0.9,
                    ),
                ],
            ),
        ]

        result = self.scorer.audit(memories, recent_traces=traces)
        assert result.total_memories == 2
        assert result.ghost_count == 1
        assert result.contradiction_count == 1
        assert result.health_score < 100.0
        assert len(result.recommendations) >= 1

    def test_audit_healthy_store(self, memories):
        """Audit with the synthetic 76-memory dataset (no traces = no ghosts)."""
        result = self.scorer.audit(memories)
        assert result.total_memories == 76
        # Without traces, ghost and contradiction counts should be 0
        assert result.ghost_count == 0
        assert result.contradiction_count == 0
        # But stale count should pick up mem_2847
        assert result.stale_count >= 1

    def test_audit_recommendations(self):
        memories = [Memory(id="m1", content="test")]
        result = self.scorer.audit(memories)
        # Should always have at least one recommendation
        assert len(result.recommendations) >= 1
