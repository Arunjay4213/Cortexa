"""Tests for cortex.metrics.financial — Sharpe Ratio & Portfolio ROI."""

import pytest
import numpy as np
from cortex.metrics.financial import compute_sharpe_ratio, compute_portfolio_roi, MemorySharpeRatio, PortfolioROI


# --- Sharpe Ratio Tests ---

def test_sharpe_empty_data():
    """Empty attribution list should return insufficient_data."""
    sr = compute_sharpe_ratio("m1", [])
    assert sr.interpretation == "insufficient_data"
    assert sr.sharpe_ratio == 0.0


def test_sharpe_single_observation():
    """Single observation = insufficient data."""
    sr = compute_sharpe_ratio("m1", [0.5])
    assert sr.interpretation == "insufficient_data"


def test_sharpe_positive_excess_return():
    """Consistent high returns should give excellent Sharpe."""
    sr = compute_sharpe_ratio("m1", [0.8, 0.9, 0.85, 0.88, 0.92])
    assert sr.sharpe_ratio > 3.0
    assert sr.interpretation == "excellent"


def test_sharpe_zero_volatility_above_rf():
    """Zero volatility with mean > rf should cap at 10.0."""
    sr = compute_sharpe_ratio("m1", [0.5, 0.5, 0.5, 0.5])
    assert sr.sharpe_ratio == 10.0


def test_sharpe_zero_volatility_below_rf():
    """Zero volatility with mean <= rf should be 0."""
    sr = compute_sharpe_ratio("m1", [0.005, 0.005, 0.005], risk_free_rate=0.01)
    assert sr.sharpe_ratio == 0.0


def test_sharpe_negative_returns():
    """Returns below risk-free rate should give negative Sharpe."""
    sr = compute_sharpe_ratio("m1", [0.001, 0.002, 0.001, 0.003], risk_free_rate=0.1)
    assert sr.sharpe_ratio < 0
    assert sr.interpretation == "poor"


def test_sharpe_volatile_returns():
    """Highly volatile returns should lower Sharpe ratio."""
    stable = compute_sharpe_ratio("m1", [0.5, 0.51, 0.49, 0.5, 0.5])
    volatile = compute_sharpe_ratio("m1", [0.1, 0.9, 0.1, 0.9, 0.1])
    assert stable.sharpe_ratio > volatile.sharpe_ratio


def test_sharpe_custom_risk_free_rate():
    """Custom risk-free rate should shift the ratio."""
    sr_low = compute_sharpe_ratio("m1", [0.3, 0.4, 0.35], risk_free_rate=0.0)
    sr_high = compute_sharpe_ratio("m1", [0.3, 0.4, 0.35], risk_free_rate=0.5)
    assert sr_low.sharpe_ratio > sr_high.sharpe_ratio


def test_sharpe_interpretation_boundaries():
    """Test interpretation buckets."""
    # Use controlled data to hit each bucket
    excellent = compute_sharpe_ratio("m", [10, 10.1, 10, 10.1, 10])  # very high mean, low std
    assert excellent.interpretation == "excellent"


# --- Portfolio ROI Tests ---

def test_portfolio_empty():
    """Empty portfolio should return zeros."""
    roi = compute_portfolio_roi("a1", [])
    assert roi.total_roi == 0.0
    assert roi.memory_count == 0
    assert roi.top_performers == []


def test_portfolio_single_memory():
    """Single memory portfolio."""
    roi = compute_portfolio_roi("a1", [
        {"memory_id": "m1", "revenue": 10.0, "cost": 2.0, "tokens": 100, "roi": 5.0}
    ])
    assert roi.memory_count == 1
    assert roi.total_roi == 4.0  # (10-2)/2
    assert roi.weighted_roi == 5.0  # only one memory, weight = 1.0


def test_portfolio_multiple_memories():
    """Multiple memories with different ROI."""
    data = [
        {"memory_id": "m1", "revenue": 10.0, "cost": 2.0, "tokens": 100, "roi": 5.0},
        {"memory_id": "m2", "revenue": 5.0, "cost": 5.0, "tokens": 200, "roi": 1.0},
        {"memory_id": "m3", "revenue": 1.0, "cost": 4.0, "tokens": 100, "roi": 0.25},
    ]
    roi = compute_portfolio_roi("a1", data)
    assert roi.memory_count == 3
    assert roi.total_revenue == 16.0
    assert roi.total_cost == 11.0


def test_portfolio_top_bottom_performers():
    """Top and bottom performers should be sorted correctly."""
    data = [
        {"memory_id": f"m{i}", "revenue": float(i), "cost": 1.0, "tokens": 100, "roi": float(i)}
        for i in range(10)
    ]
    roi = compute_portfolio_roi("a1", data)
    # Top should be m9, m8, m7, m6, m5
    assert roi.top_performers[0]["memory_id"] == "m9"
    # Bottom 5 from sorted descending: m4, m3, m2, m1, m0
    assert roi.bottom_performers[0]["memory_id"] == "m4"
    assert roi.bottom_performers[-1]["memory_id"] == "m0"


def test_portfolio_diversification():
    """Equal revenue distribution should give high diversification."""
    equal_data = [
        {"memory_id": f"m{i}", "revenue": 10.0, "cost": 1.0, "tokens": 100, "roi": 10.0}
        for i in range(5)
    ]
    skewed_data = [
        {"memory_id": "m0", "revenue": 100.0, "cost": 1.0, "tokens": 100, "roi": 100.0},
    ] + [
        {"memory_id": f"m{i}", "revenue": 0.01, "cost": 1.0, "tokens": 100, "roi": 0.01}
        for i in range(1, 5)
    ]
    equal_roi = compute_portfolio_roi("a1", equal_data)
    skewed_roi = compute_portfolio_roi("a1", skewed_data)
    assert equal_roi.diversification_score > skewed_roi.diversification_score


def test_portfolio_zero_cost():
    """Zero total cost should not divide by zero."""
    data = [{"memory_id": "m1", "revenue": 10.0, "cost": 0.0, "tokens": 100, "roi": 0.0}]
    roi = compute_portfolio_roi("a1", data)
    assert roi.total_roi == 0.0  # can't compute ROI without cost


def test_portfolio_weighted_roi():
    """Token-weighted ROI should weight larger memories more."""
    data = [
        {"memory_id": "m1", "revenue": 1.0, "cost": 1.0, "tokens": 900, "roi": 1.0},  # 90% weight
        {"memory_id": "m2", "revenue": 1.0, "cost": 1.0, "tokens": 100, "roi": 10.0},  # 10% weight
    ]
    roi = compute_portfolio_roi("a1", data)
    # weighted = 0.9 * 1.0 + 0.1 * 10.0 = 1.9
    assert abs(roi.weighted_roi - 1.9) < 0.01
