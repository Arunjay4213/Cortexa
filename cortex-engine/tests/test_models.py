"""Tests for Pydantic model validation and defaults."""

import pytest

from cortex.models import (
    AgentCostConfig,
    AgentSummary,
    AttributionMethod,
    AttributionScore,
    CalibrationPair,
    DashboardOverview,
    MemoryCreate,
    MemoryPnL,
    MemoryProfile,
    MemoryTier,
    MemoryUnit,
    TokenCostConfig,
    Transaction,
    TransactionComplete,
    TransactionCost,
    TransactionCreate,
    TransactionInitiate,
    TransactionStatus,
)


class TestMemoryUnit:
    def test_defaults(self):
        m = MemoryUnit(content="hello world")
        assert m.tier == MemoryTier.warm
        assert m.criticality == 0.5
        assert m.agent_id == "default"
        assert m.embedding == []
        assert m.retrieval_count == 0
        assert m.deleted_at is None

    def test_id_auto_generated(self):
        m1 = MemoryUnit(content="a")
        m2 = MemoryUnit(content="b")
        assert m1.id != m2.id

    def test_memory_create(self):
        mc = MemoryCreate(content="test", agent_id="agent-1", tier=MemoryTier.hot)
        assert mc.tier == MemoryTier.hot
        assert mc.agent_id == "agent-1"


class TestTransaction:
    def test_defaults(self):
        t = Transaction(query_text="q")
        assert t.agent_id == "default"
        assert t.input_tokens == 0
        assert t.model == "unknown"
        assert t.status == TransactionStatus.completed
        assert t.response_text is None

    def test_create_input(self):
        tc = TransactionCreate(
            query_text="What is X?",
            response_text="X is Y.",
            retrieved_memory_ids=["m1", "m2"],
        )
        assert len(tc.retrieved_memory_ids) == 2
        assert tc.query_embedding is None  # will be auto-embedded

    def test_two_phase_models(self):
        init = TransactionInitiate(
            query_text="What is X?",
            retrieved_memory_ids=["m1"],
        )
        assert init.query_embedding is None

        complete = TransactionComplete(response_text="X is Y.")
        assert complete.input_tokens is None


class TestAttributionScore:
    def test_method_enum(self):
        a = AttributionScore(
            memory_id="m1",
            transaction_id="t1",
            score=0.5,
            raw_score=0.3,
            method=AttributionMethod.eas,
        )
        assert a.method == AttributionMethod.eas
        assert a.confidence == 1.0


class TestTokenEconomics:
    def test_config_requires_values(self):
        """TokenCostConfig no longer has defaults — must supply costs."""
        config = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)
        assert config.input_token_cost == 0.00001
        assert config.output_token_cost == 0.00003

    def test_config_no_defaults(self):
        with pytest.raises(Exception):
            TokenCostConfig()

    def test_transaction_cost_model(self):
        tc = TransactionCost(
            transaction_id="t1",
            input_cost=0.01,
            output_cost=0.03,
            total_cost=0.04,
        )
        assert tc.total_cost == 0.04

    def test_memory_pnl_model(self):
        pnl = MemoryPnL(memory_id="m1", revenue=1.0, cost=0.5, pnl=0.5, roi=2.0)
        assert pnl.roi == 2.0


class TestMemoryProfile:
    def test_defaults(self):
        p = MemoryProfile(memory_id="m1")
        assert p.mean_attribution == 0.0
        assert p.m2 == 0.0
        assert p.retrieval_count == 0
        assert p.trend == "stable"

    def test_variance_from_m2(self):
        p = MemoryProfile(memory_id="m1", m2=10.0, retrieval_count=11)
        assert p.attribution_variance == pytest.approx(1.0)  # 10 / (11-1)


class TestCalibrationPair:
    def test_creation(self):
        cp = CalibrationPair(
            memory_id="m1",
            transaction_id="t1",
            eas_score=0.42,
            exact_score=0.45,
        )
        assert cp.method == "contextcite"
        assert cp.eas_score == 0.42


class TestAgentCostConfig:
    def test_creation(self):
        cfg = AgentCostConfig(
            agent_id="agent-1",
            input_token_cost=0.00001,
            output_token_cost=0.00003,
            provider="openai",
            model_id="gpt-4",
        )
        assert cfg.provider == "openai"


class TestDashboardModels:
    def test_agent_summary(self):
        s = AgentSummary(agent_id="agent-1")
        assert s.total_memories == 0
        assert s.tier_distribution == {}

    def test_dashboard_overview(self):
        d = DashboardOverview()
        assert d.agents == []
        assert d.total_memories == 0
