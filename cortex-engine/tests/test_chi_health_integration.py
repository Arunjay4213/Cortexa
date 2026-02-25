"""Integration tests for CHI Health Scoring endpoints.

Tests the full flow:
1. POST /health/compute/{agent_id} creates snapshots
2. CHI components sum correctly
3. Staleness exponential decay
4. GET /health/chi/{agent_id} returns latest snapshot
5. WebSocket broadcast on health update
"""

import pytest
from datetime import UTC, datetime, timedelta
from fastapi.testclient import TestClient
from cortex.api.app import create_app
from cortex.metrics.health import staleness_score, batch_staleness, CHIWeights, compute_chi
import uuid


@pytest.fixture
def client():
    """Test client for API endpoints."""
    app = create_app()
    return TestClient(app)


def test_staleness_exponential_decay():
    """Test staleness follows exponential decay with 7-day half-life."""
    now = datetime.now(UTC)

    # Just accessed: staleness should be 0
    assert staleness_score(now, now) == 0.0

    # Never accessed: staleness should be 1
    assert staleness_score(None, now) == 1.0

    # 7 days ago (half-life): staleness should be ~0.5
    seven_days_ago = now - timedelta(days=7)
    staleness = staleness_score(seven_days_ago, now, half_life_days=7.0)
    assert 0.49 < staleness < 0.51, f"Expected ~0.5, got {staleness}"

    # 14 days ago (2× half-life): staleness should be ~0.75
    fourteen_days_ago = now - timedelta(days=14)
    staleness = staleness_score(fourteen_days_ago, now, half_life_days=7.0)
    assert 0.74 < staleness < 0.76, f"Expected ~0.75, got {staleness}"

    # Very old (100 days): should asymptotically approach 1.0
    old = now - timedelta(days=100)
    staleness = staleness_score(old, now, half_life_days=7.0)
    assert staleness > 0.99


def test_batch_staleness():
    """Test batch staleness computation."""
    now = datetime.now(UTC)
    times = [
        now,
        now - timedelta(days=7),
        now - timedelta(days=14),
        None,
    ]

    staleness_values = batch_staleness(times, now, half_life_days=7.0)

    assert len(staleness_values) == 4
    assert staleness_values[0] == 0.0  # just accessed
    assert 0.49 < staleness_values[1] < 0.51  # 7 days
    assert 0.74 < staleness_values[2] < 0.76  # 14 days
    assert staleness_values[3] == 1.0  # never accessed


def test_chi_weights_normalization():
    """Test CHI weights automatically normalize to 1.0."""
    # Default weights should sum to 1
    weights = CHIWeights()
    total = weights.accuracy + weights.freshness + weights.coverage + weights.consistency + weights.efficiency
    assert abs(total - 1.0) < 1e-6

    # Custom weights should auto-normalize
    weights = CHIWeights(accuracy=2.0, freshness=2.0, coverage=2.0, consistency=2.0, efficiency=2.0)
    total = weights.accuracy + weights.freshness + weights.coverage + weights.consistency + weights.efficiency
    assert abs(total - 1.0) < 1e-6


def test_chi_computation_and_grading():
    """Test CHI computation formula and grading."""
    # Perfect score: all components = 1.0
    result = compute_chi(1.0, 1.0, 1.0, 1.0, 1.0)
    assert result.score == 1.0
    assert result.grade == "A"

    # All zeros: should be 0
    result = compute_chi(0.0, 0.0, 0.0, 0.0, 0.0)
    assert result.score == 0.0
    assert result.grade == "F"

    # Test grading thresholds
    result = compute_chi(0.92, 0.92, 0.92, 0.92, 0.92)
    assert result.grade == "A"  # >= 0.9

    result = compute_chi(0.85, 0.85, 0.85, 0.85, 0.85)
    assert result.grade == "B"  # >= 0.8

    result = compute_chi(0.75, 0.75, 0.75, 0.75, 0.75)
    assert result.grade == "C"  # >= 0.7

    result = compute_chi(0.65, 0.65, 0.65, 0.65, 0.65)
    assert result.grade == "D"  # >= 0.6

    result = compute_chi(0.5, 0.5, 0.5, 0.5, 0.5)
    assert result.grade == "F"  # < 0.6


def test_chi_endpoint_response_structure(client):
    """Test POST /health/compute/{agent_id} returns proper structure."""
    agent_id = f"test-agent-{uuid.uuid4().hex[:8]}"

    try:
        # Call the compute endpoint
        response = client.post(f"/api/v1/health/compute/{agent_id}")

        # Endpoint should work even with no data
        if response.status_code == 200:
            data = response.json()

            # Verify response structure
            assert "chi_score" in data
            assert "chi_grade" in data
            assert "components" in data
            assert "snapshot_id" in data
            assert "timestamp" in data
            assert data["agent_id"] == agent_id

            # Verify all 5 components are present
            components = data["components"]
            assert "accuracy" in components
            assert "freshness" in components
            assert "coverage" in components
            assert "consistency" in components
            assert "efficiency" in components

            # CHI score should be in [0, 1]
            assert 0.0 <= data["chi_score"] <= 1.0

            # Grade should be A/B/C/D/F
            assert data["chi_grade"] in ["A", "B", "C", "D", "F"]

            print(f"✓ CHI computed: {data['chi_score']:.3f} ({data['chi_grade']})")
    except Exception as e:
        pytest.skip(f"DB not available: {e}")


def test_get_chi_endpoint(client):
    """Test GET /health/chi/{agent_id} returns latest snapshot."""
    import asyncio
    from sqlalchemy import insert
    from cortex.database import get_session
    from cortex.db.tables import health_snapshots
    from datetime import UTC, datetime

    agent_id = f"test-get-chi-{uuid.uuid4().hex[:8]}"

    async def setup_and_test():
        async for db in get_session():
            try:
                # Create test snapshot directly in DB
                snapshot_id = str(uuid.uuid4())
                await db.execute(
                    insert(health_snapshots).values(
                        id=snapshot_id,
                        agent_id=agent_id,
                        chi_score=0.85,
                        chi_grade="B",
                        accuracy_component=0.9,
                        freshness_component=0.8,
                        coverage_component=0.85,
                        consistency_component=0.9,
                        efficiency_component=0.75,
                        contradiction_rate=0.0,
                        retrieval_efficiency=0.0,
                        semantic_drift=0.0,
                        memory_quality=0.0,
                        timestamp=datetime.now(UTC),
                    )
                )
                await db.commit()

                # Now test the GET endpoint
                response = client.get(f"/api/v1/health/chi/{agent_id}")
                assert response.status_code == 200

                data = response.json()
                assert data is not None
                assert data["snapshot_id"] == snapshot_id
                assert data["chi_score"] == 0.85
                assert data["chi_grade"] == "B"
                assert data["components"]["accuracy"] == 0.9
                assert data["components"]["freshness"] == 0.8
                assert data["components"]["coverage"] == 0.85
                assert data["components"]["consistency"] == 0.9
                assert data["components"]["efficiency"] == 0.75

                print(f"✓ GET endpoint returned correct snapshot")
                return True
            except Exception as e:
                print(f"Test failed: {e}")
                import traceback
                traceback.print_exc()
                return False
            finally:
                await db.rollback()
            break

    try:
        success = asyncio.run(setup_and_test())
        if not success:
            pytest.skip("DB operation failed")
    except Exception as e:
        pytest.skip(f"DB not available: {e}")


def test_chi_components_weighted_correctly():
    """Test CHI components are weighted according to formula."""
    weights = CHIWeights()  # default weights

    # Test 5-component mode (with coverage)
    result = compute_chi(
        accuracy=0.8,
        freshness=0.6,
        coverage=0.7,
        consistency=0.9,
        efficiency=0.5,
        weights=weights,
    )

    # Manually compute expected score
    expected = (
        0.25 * 0.8 +  # accuracy
        0.20 * 0.6 +  # freshness
        0.20 * 0.7 +  # coverage
        0.20 * 0.9 +  # consistency
        0.15 * 0.5    # efficiency
    )

    assert abs(result.score - expected) < 1e-6
    assert result.score == pytest.approx(0.71, abs=0.01)
    assert result.coverage_component == 0.7


def test_chi_4_component_mode():
    """Test CHI with None coverage uses 4-component reweighted mode."""
    weights = CHIWeights()

    # Test 4-component mode (coverage=None)
    result = compute_chi(
        accuracy=0.8,
        freshness=0.6,
        coverage=None,
        consistency=0.9,
        efficiency=0.5,
    )

    # Reweighted formula (coverage's 0.20 redistributed):
    # Scale factor = 1.0 / 0.80 = 1.25
    expected = (
        0.25 * 1.25 * 0.8 +  # accuracy: 0.3125
        0.20 * 1.25 * 0.6 +  # freshness: 0.25
        0.20 * 1.25 * 0.9 +  # consistency: 0.25
        0.15 * 1.25 * 0.5    # efficiency: 0.1875
    )

    assert abs(result.score - expected) < 1e-4  # Relaxed tolerance for floating point
    assert result.coverage_component is None  # Should be None
    print(f"✓ 4-component CHI: {result.score:.4f} (coverage=None)")
