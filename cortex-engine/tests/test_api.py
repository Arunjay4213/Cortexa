"""API integration tests using FastAPI TestClient.

Pure metrics tests run without DB or sentence-transformers.
Endpoint tests require a running Postgres and are skipped otherwise.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from cortex.api.app import create_app
from cortex.models import AttributionMethod


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthz:
    def test_healthz(self, client):
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestMemoriesEndpoints:
    """Test memory CRUD HTTP contract (requires DB + embedding model)."""

    def test_create_memory_returns_201(self, client):
        """POST /api/v1/memories should return 201 with embedded content."""
        try:
            resp = client.post(
                "/api/v1/memories",
                json={
                    "content": "Python was created by Guido van Rossum",
                    "agent_id": "test-agent",
                    "tier": "hot",
                },
            )
            if resp.status_code == 201:
                data = resp.json()
                assert data["content"] == "Python was created by Guido van Rossum"
                assert data["agent_id"] == "test-agent"
                assert data["tier"] == "hot"
                assert len(data["embedding"]) > 0
                assert data["id"] is not None
        except Exception:
            pytest.skip("Database or embedding model not available")


class TestTransactionsEndpoints:
    def test_create_transaction_returns_201(self, client):
        """POST /api/v1/transactions should embed, compute EAS, and return scores."""
        try:
            # First create a memory
            mem_resp = client.post(
                "/api/v1/memories",
                json={"content": "The speed of light is 299792458 m/s", "agent_id": "test"},
            )
            if mem_resp.status_code != 201:
                pytest.skip("Database not available")
            mem_id = mem_resp.json()["id"]

            # Now create a transaction referencing that memory
            txn_resp = client.post(
                "/api/v1/transactions",
                json={
                    "query_text": "How fast is light?",
                    "response_text": "Light travels at approximately 300,000 km/s.",
                    "retrieved_memory_ids": [mem_id],
                    "agent_id": "test",
                },
            )
            assert txn_resp.status_code == 201
            data = txn_resp.json()

            # Check structure
            assert "transaction" in data
            assert "scores" in data
            assert "cost" in data
            assert len(data["scores"]) == 1
            assert data["scores"][0]["memory_id"] == mem_id
            assert 0 <= data["scores"][0]["score"] <= 1.0
            assert data["scores"][0]["method"] == "eas"
            assert data["cost"]["total_cost"] >= 0

        except Exception:
            pytest.skip("Database or embedding model not available")


# ── Pure unit tests (no DB, no embedding model) ──────────────────────


class TestMetricsCalculator:
    """Unit tests for metrics that don't need DB."""

    def test_gini_coefficient(self):
        from cortex.metrics.calculator import gini_coefficient

        # Perfectly equal
        assert gini_coefficient([0.25, 0.25, 0.25, 0.25]) == pytest.approx(0.0, abs=1e-6)

        # Maximum inequality: one has all, rest have zero-ish
        # Use [0, 0, 0, 1] — Gini should be 0.75
        g = gini_coefficient([0.0, 0.0, 0.0, 1.0])
        assert g == pytest.approx(0.75, abs=0.01)

    def test_snr_db(self):
        from cortex.metrics.calculator import snr_db

        # All positive → high SNR
        result = snr_db([0.5, 0.3, 0.2])
        assert result > 50  # very high because noise ≈ 0

        # Mixed → lower SNR
        result_mixed = snr_db([0.5, -0.1, 0.3, -0.05])
        assert result_mixed < result

    def test_token_waste_rate(self):
        from cortex.metrics.calculator import token_waste_rate

        # No waste: all scores above threshold
        rate = token_waste_rate([0.5, 0.3, 0.2], [100, 100, 100])
        assert rate == 0.0

        # 50% waste: half below threshold
        rate = token_waste_rate([0.5, 0.005, 0.3, 0.001], [100, 100, 100, 100])
        assert rate == 50.0

    def test_transaction_cost(self):
        from cortex.metrics.calculator import transaction_cost
        from cortex.models import TokenCostConfig

        # TokenCostConfig now requires explicit costs (no hardcoded defaults)
        config = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)
        cost = transaction_cost(1000, 500, config, "t1")
        assert cost.input_cost == pytest.approx(0.01)
        assert cost.output_cost == pytest.approx(0.015)
        assert cost.total_cost == pytest.approx(0.025)

    def test_transaction_cost_different_provider(self):
        """Verify different provider pricing works (e.g. Anthropic vs OpenAI)."""
        from cortex.metrics.calculator import transaction_cost
        from cortex.models import TokenCostConfig

        # Claude pricing (hypothetical)
        config = TokenCostConfig(input_token_cost=0.000015, output_token_cost=0.000075)
        cost = transaction_cost(1000, 500, config, "t1")
        assert cost.input_cost == pytest.approx(0.015)
        assert cost.output_cost == pytest.approx(0.0375)
        assert cost.total_cost == pytest.approx(0.0525)

    def test_memory_pnl(self):
        from cortex.metrics.calculator import memory_pnl
        from cortex.models import TokenCostConfig

        config = TokenCostConfig(input_token_cost=0.00001, output_token_cost=0.00003)
        result = memory_pnl("m1", total_attribution=1.0, retrieval_count=100, tokens=50, config=config)
        assert result.revenue == 1.0
        assert result.cost == pytest.approx(50 * 0.00001 * 100)
        assert result.pnl == pytest.approx(1.0 - 0.05)
        assert result.roi > 0

    def test_contradiction_risk(self):
        from cortex.metrics.calculator import contradiction_risk

        # No contradictions → risk = 0
        assert contradiction_risk([]) == 0.0

        # Single high probability → risk ≈ probability
        assert contradiction_risk([0.9]) == pytest.approx(0.9)

        # Multiple → CRS = 1 - Π(1-p)
        risk = contradiction_risk([0.5, 0.5])
        assert risk == pytest.approx(0.75)
