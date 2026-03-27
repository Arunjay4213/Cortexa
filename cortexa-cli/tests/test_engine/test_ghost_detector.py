"""Tests for cortexa.engine.ghost_detector."""

from datetime import datetime, timedelta

from cortexa.engine.ghost_detector import GhostDetector, _estimate_tokens
from cortexa.engine.models import Attribution, GhostToken, Memory, TraceResult


class TestEstimateTokens:
    def test_basic(self):
        assert _estimate_tokens("Hello world!") == 3  # 12 chars / 4

    def test_minimum_one(self):
        assert _estimate_tokens("Hi") >= 1

    def test_empty(self):
        assert _estimate_tokens("") >= 1


class TestGhostDetector:
    def setup_method(self):
        self.detector = GhostDetector(
            ghost_threshold=0.05, rolling_threshold=0.10, inactive_days=30
        )
        self.now = datetime(2026, 3, 24, 12, 0, 0)

    def test_low_mas_ghost(self):
        memories = [Memory(id="m1", content="Irrelevant memory")]
        attributions = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.01,
                entailment_score=0.05, contribution_type="ghost",
            ),
        ]
        ghosts = self.detector.detect(memories, attributions)
        assert len(ghosts) == 1
        assert ghosts[0].memory_id == "m1"
        assert "current trace" in ghosts[0].reason

    def test_high_mas_not_ghost(self):
        memories = [Memory(id="m1", content="Relevant memory")]
        attributions = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.5,
                entailment_score=0.8, contribution_type="supporting",
            ),
        ]
        ghosts = self.detector.detect(memories, attributions)
        assert len(ghosts) == 0

    def test_rolling_average_ghost(self):
        memories = [
            Memory(id="m1", content="Sometimes useful", last_accessed=self.now),
        ]
        # Current trace: m1 has decent MAS
        current_attrs = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.06,
                entailment_score=0.1, contribution_type="neutral",
            ),
        ]
        # But rolling window shows low average
        recent_traces = [
            TraceResult(
                query="q", response="r", claims=[], health_score=80.0,
                attributions=[
                    Attribution(
                        claim_id="c1", memory_id="m1", mas_score=0.02,
                        entailment_score=0.05, contribution_type="ghost",
                    ),
                ],
            ),
            TraceResult(
                query="q", response="r", claims=[], health_score=80.0,
                attributions=[
                    Attribution(
                        claim_id="c1", memory_id="m1", mas_score=0.03,
                        entailment_score=0.05, contribution_type="ghost",
                    ),
                ],
            ),
        ]

        ghosts = self.detector.detect(memories, current_attrs, recent_traces)
        assert len(ghosts) == 1
        assert "Rolling avg" in ghosts[0].reason

    def test_inactive_memory_ghost(self):
        memories = [
            Memory(
                id="m1", content="Old memory",
                last_accessed=self.now - timedelta(days=60),
            ),
        ]
        # MAS is above threshold so won't be caught by check 1
        attributions = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.15,
                entailment_score=0.2, contribution_type="neutral",
            ),
        ]
        ghosts = self.detector.detect(memories, attributions)
        assert len(ghosts) == 1
        assert "Not accessed in" in ghosts[0].reason

    def test_no_attributions(self):
        memories = [Memory(id="m1", content="test")]
        # No attributions means MAS defaults to 0.0
        ghosts = self.detector.detect(memories, [])
        assert len(ghosts) == 1

    def test_empty_inputs(self):
        ghosts = self.detector.detect([], [])
        assert ghosts == []

    def test_multiple_claims_max_mas(self):
        """Ghost detection uses MAX MAS across claims, not just one."""
        memories = [Memory(id="m1", content="test")]
        attributions = [
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.01,
                entailment_score=0.05, contribution_type="ghost",
            ),
            Attribution(
                claim_id="c2", memory_id="m1", mas_score=0.3,
                entailment_score=0.5, contribution_type="supporting",
            ),
        ]
        ghosts = self.detector.detect(memories, attributions)
        # max MAS = 0.3 > 0.05, so NOT a ghost
        assert len(ghosts) == 0


class TestEstimateWaste:
    def test_basic_waste(self):
        detector = GhostDetector()
        ghosts = [
            GhostToken(memory_id="m1", max_mas=0.01, waste_tokens=100, reason="low MAS"),
            GhostToken(memory_id="m2", max_mas=0.02, waste_tokens=50, reason="low MAS"),
        ]
        memories = [
            Memory(id="m1", content="x" * 400),
            Memory(id="m2", content="x" * 200),
        ]
        tokens, cost = detector.estimate_waste(ghosts, memories)
        assert tokens == 150
        assert cost > 0

    def test_no_ghosts(self):
        detector = GhostDetector()
        tokens, cost = detector.estimate_waste([], [])
        assert tokens == 0
        assert cost == 0.0
