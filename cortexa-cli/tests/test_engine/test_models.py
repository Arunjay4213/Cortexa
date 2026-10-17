"""Tests for cortexa.engine.models."""

from datetime import datetime

from cortexa.engine.models import (
    Attribution,
    AuditResult,
    Claim,
    Contradiction,
    GateResult,
    GhostToken,
    Memory,
    StaleMemory,
    TraceResult,
)


class TestMemory:
    def test_create_with_defaults(self):
        m = Memory(content="test content")
        assert m.content == "test content"
        assert m.id  # auto-generated
        assert m.access_count == 0
        assert m.metadata == {}
        assert m.source is None

    def test_create_with_all_fields(self):
        now = datetime(2026, 3, 24)
        m = Memory(
            id="mem_001",
            content="test",
            source="docs.md",
            source_updated_at=now,
            created_at=now,
            last_accessed=now,
            access_count=5,
            embedding=[0.1, 0.2],
            metadata={"key": "value"},
        )
        assert m.id == "mem_001"
        assert m.source == "docs.md"
        assert m.embedding == [0.1, 0.2]

    def test_unique_ids(self):
        m1 = Memory(content="a")
        m2 = Memory(content="b")
        assert m1.id != m2.id

    def test_metadata_default_isolation(self):
        m1 = Memory(content="a")
        m2 = Memory(content="b")
        m1.metadata["x"] = 1
        assert "x" not in m2.metadata

    def test_optional_fields_none(self):
        m = Memory(content="test")
        assert m.source is None
        assert m.source_updated_at is None
        assert m.last_accessed is None
        assert m.embedding is None


class TestClaim:
    def test_create_factual(self):
        c = Claim(text="Order arrives Thursday", source_response="full response")
        assert c.claim_type == "factual"

    def test_create_numerical(self):
        c = Claim(text="Price is $49.99", source_response="resp", claim_type="numerical")
        assert c.claim_type == "numerical"

    def test_all_claim_types(self):
        for ct in ["factual", "numerical", "temporal", "relational", "opinion"]:
            c = Claim(text="test", source_response="resp", claim_type=ct)
            assert c.claim_type == ct

    def test_auto_id(self):
        c = Claim(text="test", source_response="resp")
        assert len(c.id) == 12

    def test_explicit_id(self):
        c = Claim(id="custom_id", text="test", source_response="resp")
        assert c.id == "custom_id"


class TestAttribution:
    def test_valid_mas_range(self):
        a = Attribution(
            claim_id="c1", memory_id="m1", mas_score=0.5,
            entailment_score=0.8, contribution_type="supporting"
        )
        assert 0.0 <= a.mas_score <= 1.0

    def test_mas_boundary_values(self):
        for val in [0.0, 0.5, 1.0]:
            a = Attribution(
                claim_id="c1", memory_id="m1", mas_score=val,
                entailment_score=val, contribution_type="ghost"
            )
            assert a.mas_score == val

    def test_numerical_match_none(self):
        a = Attribution(
            claim_id="c1", memory_id="m1", mas_score=0.5,
            entailment_score=0.5, contribution_type="neutral"
        )
        assert a.numerical_match is None

    def test_contribution_types(self):
        for ct in ["supporting", "contradicting", "neutral", "ghost"]:
            a = Attribution(
                claim_id="c1", memory_id="m1", mas_score=0.5,
                entailment_score=0.5, contribution_type=ct
            )
            assert a.contribution_type == ct

    def test_invalid_mas_rejected(self):
        import pytest
        with pytest.raises(Exception):
            Attribution(
                claim_id="c1", memory_id="m1", mas_score=1.5,
                entailment_score=0.5, contribution_type="ghost"
            )


class TestTraceResult:
    def test_ghost_memory_ids(self):
        tr = TraceResult(
            query="q", response="r", claims=[], attributions=[],
            ghost_tokens=[
                GhostToken(memory_id="m1", max_mas=0.01, waste_tokens=10, reason="low MAS"),
                GhostToken(memory_id="m2", max_mas=0.02, waste_tokens=20, reason="low MAS"),
            ],
            health_score=80.0,
        )
        assert tr.ghost_memory_ids == ["m1", "m2"]

    def test_empty_trace(self):
        tr = TraceResult(
            query="q", response="r", claims=[], attributions=[], health_score=100.0
        )
        assert tr.ghost_memory_ids == []
        assert tr.contradictions == []

    def test_auto_trace_id(self):
        tr = TraceResult(
            query="q", response="r", claims=[], attributions=[], health_score=100.0
        )
        assert len(tr.trace_id) == 12

    def test_timestamp_auto(self):
        tr = TraceResult(
            query="q", response="r", claims=[], attributions=[], health_score=100.0
        )
        assert isinstance(tr.timestamp, datetime)

    def test_health_score_bounds(self):
        import pytest
        with pytest.raises(Exception):
            TraceResult(
                query="q", response="r", claims=[], attributions=[], health_score=101.0
            )


class TestAuditResult:
    def test_healthy_audit(self):
        ar = AuditResult(
            total_memories=76, ghost_count=0, ghost_percentage=0.0,
            contradiction_count=0, stale_count=0, health_score=100.0,
        )
        assert ar.health_score == 100.0

    def test_unhealthy_audit(self):
        ar = AuditResult(
            total_memories=76, ghost_count=19, ghost_percentage=25.0,
            contradiction_count=3, stale_count=1, health_score=36.0,
        )
        assert ar.ghost_count == 19
        assert ar.estimated_waste_tokens == 0  # default
