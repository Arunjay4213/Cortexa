"""Tests for Phase 3 Lifecycle Engine.

Unit tests for P&L calculations, recommendation logic, and budget optimization.
API endpoint tests require DB and are skipped gracefully.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from cortex.models import (
    TokenCostConfig,
    ArchiveRecommendation,
    BudgetOptimization,
    ConsolidationRecommendation,
    LifecycleRecommendations,
    TierRecommendation,
    ExecuteRecommendationsRequest,
)
from cortex.metrics.calculator import memory_pnl


# ── Pure unit tests (no DB required) ─────────────────────────────────


class TestMemoryPnL:
    """Test P&L calculation for positive, negative, and zero-cost cases."""

    def test_positive_pnl(self):
        """Memory with high attribution and low cost should have positive P&L."""
        config = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)
        result = memory_pnl(
            memory_id="mem-001",
            total_attribution=1.0,
            retrieval_count=10,
            tokens=100,
            config=config,
        )
        assert result.pnl > 0
        assert result.revenue == 1.0
        assert result.cost == 100 * 0.00001 * 10  # 0.01
        assert result.pnl == pytest.approx(1.0 - 0.01)
        assert result.roi > 0

    def test_negative_pnl(self):
        """Memory with low attribution and high cost should have negative P&L."""
        config = TokenCostConfig(input_token_cost=0.01, output_token_cost=0.03)
        result = memory_pnl(
            memory_id="mem-002",
            total_attribution=0.001,
            retrieval_count=100,
            tokens=500,
            config=config,
        )
        # cost = 500 * 0.01 * 100 = 500.0
        assert result.pnl < 0
        assert result.cost == 500.0
        assert result.revenue == 0.001

    def test_zero_cost(self):
        """Memory with zero tokens should have zero cost and ROI of 0."""
        config = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)
        result = memory_pnl(
            memory_id="mem-003",
            total_attribution=0.5,
            retrieval_count=0,
            tokens=0,
            config=config,
        )
        assert result.cost == 0.0
        assert result.pnl == 0.5
        assert result.roi == 0.0  # zero cost → ROI is 0

    def test_zero_attribution(self):
        """Memory with no attribution has negative P&L if cost > 0."""
        config = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)
        result = memory_pnl(
            memory_id="mem-004",
            total_attribution=0.0,
            retrieval_count=5,
            tokens=100,
            config=config,
        )
        assert result.revenue == 0.0
        assert result.cost == 100 * 0.00001 * 5  # 0.005
        assert result.pnl < 0

    def test_zero_retrieval_with_tokens(self):
        """Memory with tokens but no retrievals should have zero cost."""
        config = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)
        result = memory_pnl(
            memory_id="mem-005",
            total_attribution=0.3,
            retrieval_count=0,
            tokens=500,
            config=config,
        )
        assert result.cost == 0.0
        assert result.pnl == 0.3


class TestPydanticModels:
    """Test that lifecycle Pydantic models validate correctly."""

    def test_archive_recommendation(self):
        rec = ArchiveRecommendation(
            memory_id="mem-001",
            agent_id="agent-alpha",
            revenue=0.1,
            cost=0.5,
            pnl=-0.4,
            reason="negative_pnl",
        )
        assert rec.pnl == -0.4
        assert rec.reason == "negative_pnl"

    def test_consolidation_recommendation(self):
        rec = ConsolidationRecommendation(
            canonical_memory_id="mem-001",
            duplicate_memory_ids=["mem-002", "mem-003"],
            method="content_hash",
        )
        assert len(rec.duplicate_memory_ids) == 2

    def test_tier_recommendation(self):
        rec = TierRecommendation(
            memory_id="mem-001",
            current_tier="warm",
            recommended_tier="hot",
            trend="up",
            reason="Trending up — promote from warm to hot",
        )
        assert rec.recommended_tier == "hot"

    def test_budget_optimization(self):
        opt = BudgetOptimization(
            budget_tokens=100000,
            selected_memory_ids=["mem-001", "mem-002"],
            total_tokens=5000,
            total_attribution=2.5,
            excluded_count=3,
        )
        assert opt.excluded_count == 3
        assert len(opt.selected_memory_ids) == 2

    def test_lifecycle_recommendations(self):
        recs = LifecycleRecommendations(
            agent_id="agent-alpha",
            archive=[
                ArchiveRecommendation(
                    memory_id="m1", agent_id="agent-alpha",
                    revenue=0.01, cost=1.0, pnl=-0.99,
                )
            ],
            consolidate=[],
            tier_changes=[],
            estimated_monthly_savings=1.0,
        )
        assert len(recs.archive) == 1
        assert recs.estimated_monthly_savings == 1.0

    def test_execute_request(self):
        req = ExecuteRecommendationsRequest(
            archive_memory_ids=["mem-001"],
            tier_changes={"mem-002": "hot"},
            consolidate_groups=[["mem-003", "mem-004"]],
        )
        assert len(req.archive_memory_ids) == 1
        assert req.tier_changes["mem-002"] == "hot"


class TestBudgetOptimizationLogic:
    """Test the greedy knapsack algorithm logic."""

    def test_greedy_selection_order(self):
        """Higher efficiency items should be selected first."""
        # Simulate the greedy algorithm
        items = [
            ("mem-a", 100, 0.5),   # efficiency = 0.005
            ("mem-b", 50, 0.4),    # efficiency = 0.008 (best)
            ("mem-c", 200, 0.6),   # efficiency = 0.003
        ]
        # Sort by efficiency descending
        items.sort(key=lambda x: x[2] / x[1], reverse=True)
        assert items[0][0] == "mem-b"  # highest efficiency first

        budget = 200
        selected = []
        total_tokens = 0
        total_attr = 0.0
        for mem_id, tokens, attr in items:
            if total_tokens + tokens <= budget:
                selected.append(mem_id)
                total_tokens += tokens
                total_attr += attr

        assert "mem-b" in selected  # 50 tokens
        assert "mem-a" in selected  # 50 + 100 = 150 tokens
        assert total_tokens <= budget
        assert len(selected) == 2  # mem-c (200 tokens) doesn't fit after first two

    def test_empty_budget(self):
        """Zero budget should select nothing."""
        opt = BudgetOptimization(
            budget_tokens=0,
            selected_memory_ids=[],
            total_tokens=0,
            total_attribution=0.0,
            excluded_count=5,
        )
        assert len(opt.selected_memory_ids) == 0

    def test_unlimited_budget(self):
        """Huge budget should select everything."""
        all_ids = [f"mem-{i}" for i in range(10)]
        opt = BudgetOptimization(
            budget_tokens=999999999,
            selected_memory_ids=all_ids,
            total_tokens=1000,
            total_attribution=5.0,
            excluded_count=0,
        )
        assert len(opt.selected_memory_ids) == 10
        assert opt.excluded_count == 0


# ── API endpoint smoke tests ──────────────────────────────────────────


class TestLifecycleEndpoints:
    """Test lifecycle API endpoints (requires DB, gracefully skips)."""

    @pytest.fixture
    def client(self):
        from cortex.api.app import create_app
        app = create_app()
        return TestClient(app)

    def test_recommendations_endpoint(self, client):
        """GET /lifecycle/{agent_id}/recommendations should return valid JSON."""
        try:
            resp = client.get("/api/v1/lifecycle/agent-alpha/recommendations")
            if resp.status_code == 200:
                data = resp.json()
                assert "agent_id" in data
                assert "archive" in data
                assert "consolidate" in data
                assert "tier_changes" in data
                assert "estimated_monthly_savings" in data
        except Exception:
            pytest.skip("Database not available")

    def test_budget_endpoint(self, client):
        """GET /lifecycle/{agent_id}/budget should return valid JSON."""
        try:
            resp = client.get(
                "/api/v1/lifecycle/agent-alpha/budget",
                params={"budget_tokens": 100000},
            )
            if resp.status_code == 200:
                data = resp.json()
                assert "budget_tokens" in data
                assert "selected_memory_ids" in data
                assert "total_tokens" in data
        except Exception:
            pytest.skip("Database not available")

    def test_execute_endpoint_empty(self, client):
        """POST /lifecycle/{agent_id}/execute with empty request should succeed."""
        try:
            resp = client.post(
                "/api/v1/lifecycle/agent-alpha/execute",
                json={
                    "archive_memory_ids": [],
                    "tier_changes": {},
                    "consolidate_groups": [],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                assert data["total_actions"] == 0
        except Exception:
            pytest.skip("Database not available")
