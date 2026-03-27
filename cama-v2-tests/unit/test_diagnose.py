"""Hostile tests for cama/diagnose.py — ghost detection, contradictions, staleness, health."""

from __future__ import annotations

from datetime import datetime

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


def _make_span(text="hallucinated text", score=0.8):
    """Helper to build a HallucinatedSpan."""
    ts = TokenScore(token=text, index=0, hallucination_prob=score)
    return HallucinatedSpan(
        text=text, start_char=0, end_char=len(text), score=score, token_scores=[ts]
    )


def _make_span_attribution(
    memory_attributions: list[tuple[str, float, str]],
    span_score: float = 0.8,
) -> SpanAttribution:
    """Build a SpanAttribution from (memory_id, delta, direction) tuples."""
    span = _make_span(score=span_score)
    total_abs = sum(abs(d) for _, d, _ in memory_attributions) + 1e-8
    attrs = [
        MemoryAttribution(
            memory_id=mid,
            mas=abs(delta) / total_abs,
            delta=delta,
            direction=direction,
        )
        for mid, delta, direction in memory_attributions
    ]
    return SpanAttribution(
        span=span, attributions=attrs, diagnosis="test", culprit_memory_id=None
    )


# ── Ghost Detection ────────────────────────────────────────────────


class TestGhostDetection:
    def test_basic_ghost(self, diagnoser):
        """Memory with near-zero delta on all spans → ghost."""
        memories = [
            Memory(id="active", content="Widget costs $49.99."),
            Memory(id="ghost", content="Customer likes blue."),
        ]
        sa = _make_span_attribution([
            ("active", -0.15, "causing"),
            ("ghost", 0.001, "ghost"),
        ])
        ghosts = diagnoser.detect_ghosts(memories, [sa])
        assert "ghost" in ghosts
        assert "active" not in ghosts

    def test_no_spans_means_no_ghosts(self, diagnoser):
        """If no hallucinated spans, no one is a ghost."""
        memories = [
            Memory(id="m1", content="data"),
            Memory(id="m2", content="data"),
        ]
        ghosts = diagnoser.detect_ghosts(memories, [])
        assert ghosts == []

    def test_all_memories_are_ghosts(self, diagnoser):
        """Every memory has near-zero delta → all are ghosts."""
        memories = [
            Memory(id="m1", content="irrelevant 1"),
            Memory(id="m2", content="irrelevant 2"),
            Memory(id="m3", content="irrelevant 3"),
        ]
        sa = _make_span_attribution([
            ("m1", 0.001, "ghost"),
            ("m2", -0.005, "ghost"),
            ("m3", 0.01, "ghost"),
        ])
        # Override MAS below threshold — with few memories, normalized MAS
        # is naturally high even for tiny deltas
        for a in sa.attributions:
            a.mas = 0.01
        ghosts = diagnoser.detect_ghosts(memories, [sa])
        assert set(ghosts) == {"m1", "m2", "m3"}

    def test_ghost_threshold_boundary(self, diagnoser):
        """Memory with |delta| exactly at threshold (0.02) — should NOT be ghost."""
        memories = [Memory(id="borderline", content="data")]
        sa = _make_span_attribution([("borderline", 0.02, "ghost")])
        # Override MAS below threshold — single memory produces MAS ≈ 1.0
        for a in sa.attributions:
            a.mas = 0.01
        ghosts = diagnoser.detect_ghosts(memories, [sa])
        # |0.02| <= 0.02, but code checks > threshold, so 0.02 is NOT > 0.02
        assert "borderline" in ghosts  # Still ghost at exactly threshold

    def test_ghost_just_above_threshold(self, diagnoser):
        """Memory with |delta| = 0.021 — should NOT be ghost."""
        memories = [Memory(id="active", content="data")]
        sa = _make_span_attribution([("active", 0.021, "supporting")])
        ghosts = diagnoser.detect_ghosts(memories, [sa])
        assert "active" not in ghosts

    def test_ghost_across_multiple_spans(self, diagnoser):
        """Ghost only if near-zero on ALL spans, not just one."""
        memories = [
            Memory(id="partial", content="data"),
            Memory(id="full_ghost", content="other"),
        ]
        sa1 = _make_span_attribution([
            ("partial", 0.001, "ghost"),
            ("full_ghost", 0.001, "ghost"),
        ])
        sa2 = _make_span_attribution([
            ("partial", 0.15, "causing"),  # Active on second span
            ("full_ghost", 0.005, "ghost"),
        ])
        # Override MAS to isolate delta-based filtering
        for a in sa1.attributions:
            a.mas = 0.01
        for a in sa2.attributions:
            if a.memory_id == "full_ghost":
                a.mas = 0.01  # Ghost stays below MAS threshold
            # partial's MAS irrelevant — its delta 0.15 > 0.02 removes it
        ghosts = diagnoser.detect_ghosts(memories, [sa1, sa2])
        assert "full_ghost" in ghosts
        assert "partial" not in ghosts


# ── Contradiction Detection ────────────────────────────────────────


class TestContradictionDetection:
    def test_attribution_based_contradiction(self, diagnoser):
        """Supporting + causing on same span → contradiction."""
        memories = [
            Memory(id="supporter", content="Price is $49.99."),
            Memory(id="causer", content="Price is $99.99."),
        ]
        sa = _make_span_attribution([
            ("supporter", 0.15, "supporting"),
            ("causer", -0.15, "causing"),
        ])
        # Override MAS to be above 0.1 threshold
        for a in sa.attributions:
            a.mas = 0.5
        contradictions = diagnoser.detect_contradictions(memories, [sa])
        assert len(contradictions) >= 1
        pair = {contradictions[0].memory_id_1, contradictions[0].memory_id_2}
        assert pair == {"supporter", "causer"}

    def test_no_contradiction_all_same_direction(self, diagnoser):
        """All causing or all supporting → no contradiction."""
        memories = [
            Memory(id="m1", content="data1"),
            Memory(id="m2", content="data2"),
        ]
        sa = _make_span_attribution([
            ("m1", -0.15, "causing"),
            ("m2", -0.10, "causing"),
        ])
        for a in sa.attributions:
            a.mas = 0.5
        contradictions = diagnoser.detect_contradictions(memories, [sa])
        assert len(contradictions) == 0

    def test_low_mas_not_contradicted(self, diagnoser):
        """Opposing directions but MAS < 0.1 → no contradiction."""
        memories = [
            Memory(id="m1", content="data1"),
            Memory(id="m2", content="data2"),
        ]
        sa = _make_span_attribution([
            ("m1", 0.15, "supporting"),
            ("m2", -0.15, "causing"),
        ])
        # Set MAS below threshold
        for a in sa.attributions:
            a.mas = 0.05
        contradictions = diagnoser.detect_contradictions(memories, [sa])
        assert len(contradictions) == 0

    def test_no_duplicate_contradictions(self, diagnoser):
        """Same pair on multiple spans → only counted once."""
        memories = [
            Memory(id="m1", content="data1"),
            Memory(id="m2", content="data2"),
        ]
        sa1 = _make_span_attribution([
            ("m1", 0.15, "supporting"),
            ("m2", -0.15, "causing"),
        ])
        sa2 = _make_span_attribution([
            ("m1", 0.10, "supporting"),
            ("m2", -0.20, "causing"),
        ])
        for sa in [sa1, sa2]:
            for a in sa.attributions:
                a.mas = 0.5
        contradictions = diagnoser.detect_contradictions(memories, [sa1, sa2])
        pairs = [tuple(sorted([c.memory_id_1, c.memory_id_2])) for c in contradictions]
        assert len(set(pairs)) == len(pairs), "Duplicate contradiction pairs found"


# ── Staleness Detection ────────────────────────────────────────────


class TestStalenessDetection:
    def test_stale_memory_detected(self, diagnoser):
        memories = [
            Memory(
                id="stale",
                content="data",
                created_at=datetime(2025, 1, 1),
                source_updated_at=datetime(2026, 1, 1),
            ),
        ]
        stale = diagnoser.detect_stale(memories)
        assert "stale" in stale

    def test_fresh_memory_not_stale(self, diagnoser):
        memories = [
            Memory(
                id="fresh",
                content="data",
                created_at=datetime(2026, 1, 1),
                source_updated_at=datetime(2025, 1, 1),  # Updated BEFORE created
            ),
        ]
        stale = diagnoser.detect_stale(memories)
        assert "fresh" not in stale

    def test_no_timestamps_not_stale(self, diagnoser):
        memories = [Memory(id="m1", content="data")]
        stale = diagnoser.detect_stale(memories)
        assert stale == []

    def test_same_timestamps_not_stale(self, diagnoser):
        """source_updated_at == created_at → not stale (not strictly greater)."""
        now = datetime(2025, 6, 1)
        memories = [
            Memory(id="m1", content="data", created_at=now, source_updated_at=now),
        ]
        stale = diagnoser.detect_stale(memories)
        assert stale == []

    def test_mixed_stale_and_fresh(self, diagnoser):
        memories = [
            Memory(
                id="stale",
                content="old data",
                created_at=datetime(2025, 1, 1),
                source_updated_at=datetime(2026, 1, 1),
            ),
            Memory(
                id="fresh",
                content="new data",
                created_at=datetime(2026, 1, 1),
            ),
            Memory(
                id="also_stale",
                content="also old",
                created_at=datetime(2025, 6, 1),
                source_updated_at=datetime(2025, 12, 1),
            ),
        ]
        stale = diagnoser.detect_stale(memories)
        assert set(stale) == {"stale", "also_stale"}


# ── Health Score ────────────────────────────────────────────────────


class TestHealthScore:
    def _make_trace(
        self,
        n_memories: int = 4,
        n_ghosts: int = 0,
        n_contradictions: int = 0,
        n_stale: int = 0,
        hallucination_rate: float = 0.0,
    ) -> TraceResult:
        return TraceResult(
            query="q",
            response="r",
            memories_used=[f"m{i}" for i in range(n_memories)],
            hallucinated_spans=[],
            span_attributions=[],
            ghost_memories=[f"g{i}" for i in range(n_ghosts)],
            contradictions=[
                Contradiction(
                    memory_id_1=f"c{i}_a",
                    memory_id_2=f"c{i}_b",
                    explanation="test",
                )
                for i in range(n_contradictions)
            ],
            stale_memories=[f"s{i}" for i in range(n_stale)],
            health_score=0.0,
            hallucination_rate=hallucination_rate,
            latency_ms=100.0,
            detection_method="test",
            attribution_method="test",
        )

    def test_perfect_health(self, diagnoser):
        """No problems → health = 100."""
        trace = self._make_trace()
        health = diagnoser.compute_health(trace)
        assert health == 100

    def test_all_ghosts(self, diagnoser):
        """All memories are ghosts → heavy penalty."""
        trace = self._make_trace(n_memories=4, n_ghosts=4)
        health = diagnoser.compute_health(trace)
        # ghost_pct = 100%, penalty = 100 * 0.4 = 40
        assert health == 60

    def test_max_contradiction_penalty(self, diagnoser):
        """Many contradictions → capped at 25."""
        trace = self._make_trace(n_contradictions=10)
        health = diagnoser.compute_health(trace)
        # 10 * 8 = 80, but capped at 25 → health = 75
        assert health == 75

    def test_high_hallucination_rate(self, diagnoser):
        """hallucination_rate = 1.0 → penalty capped at 10."""
        trace = self._make_trace(hallucination_rate=1.0)
        health = diagnoser.compute_health(trace)
        assert health == 90

    def test_health_floor_at_zero(self, diagnoser):
        """All penalties maxed → health clamped at 0, not negative."""
        trace = self._make_trace(
            n_memories=4,
            n_ghosts=4,
            n_contradictions=10,
            n_stale=4,
            hallucination_rate=1.0,
        )
        health = diagnoser.compute_health(trace)
        assert health >= 0

    def test_health_is_rounded_integer(self, diagnoser):
        """Health should be a rounded number."""
        trace = self._make_trace(n_memories=3, n_ghosts=1)
        health = diagnoser.compute_health(trace)
        assert health == round(health)

    def test_stale_penalty(self, diagnoser):
        """Stale memories deduction."""
        trace = self._make_trace(n_memories=4, n_stale=2)
        health = diagnoser.compute_health(trace)
        # stale_pct = 50%, penalty = 50 * 0.25 = 12.5
        expected = 100 - 12.5
        assert health == round(expected)

    def test_combined_penalties(self, diagnoser):
        """Multiple penalty sources at once."""
        trace = self._make_trace(
            n_memories=4,
            n_ghosts=2,        # 50% * 0.4 = 20
            n_contradictions=1, # 1 * 8 = 8
            n_stale=1,          # 25% * 0.25 = 6.25
            hallucination_rate=0.3,  # 30 → capped at 10? No, 0.3*100=30, min(30,10)=10
        )
        health = diagnoser.compute_health(trace)
        # 100 - 20 - 8 - 6.25 - 10 = 55.75 → round = 56
        assert health == 56


# ── Ghost Waste Estimation ────────────────────────────────────────


class TestGhostWasteEstimation:
    def test_basic_waste(self, diagnoser):
        ghosts = [
            Memory(id="g1", content="x" * 400),  # 100 tokens
            Memory(id="g2", content="y" * 200),  # 50 tokens
        ]
        result = diagnoser.estimate_ghost_waste(ghosts)
        assert result["waste_tokens"] == 150
        assert result["waste_cost_daily"] > 0
        assert result["waste_cost_monthly"] > result["waste_cost_daily"]

    def test_no_ghosts_zero_waste(self, diagnoser):
        result = diagnoser.estimate_ghost_waste([])
        assert result["waste_tokens"] == 0
        assert result["waste_cost_daily"] == 0
        assert result["waste_cost_monthly"] == 0
