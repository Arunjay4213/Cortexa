"""Validation Experiments — ablation studies and mathematical correctness.

These tests verify that each component behaves according to the paper's
mathematical definitions and that removing/degrading components produces
the expected degradation in output quality.
"""

import math
import pytest
import numpy as np
from datetime import datetime, UTC, timedelta


class TestStalenessDecayCurve:
    """Verify staleness follows exponential decay: S(t) = 1 - e^(-λt)."""

    def test_decay_formula_exact(self):
        """Verify staleness matches the formula exactly."""
        from cortex.metrics.health import staleness_score
        now = datetime.now(UTC)
        half_life = 7.0
        lambda_ = math.log(2) / half_life

        for days in [1, 3, 7, 14, 30]:
            expected = 1.0 - math.exp(-lambda_ * days)
            actual = staleness_score(now - timedelta(days=days), now, half_life)
            assert abs(actual - expected) < 1e-10, f"Mismatch at {days} days"

    def test_half_life_parameter_sweep(self):
        """Different half-lives should correctly shift the decay curve."""
        from cortex.metrics.health import staleness_score
        now = datetime.now(UTC)

        for hl in [1, 3, 7, 14, 30]:
            s = staleness_score(now - timedelta(days=hl), now, half_life_days=float(hl))
            assert abs(s - 0.5) < 0.001, f"Half-life {hl}: expected 0.5, got {s}"


class TestCHIWeightSensitivity:
    """Ablation: verify each CHI component's impact."""

    def test_single_component_dominance(self):
        """When one weight is 1.0 and others 0, score = that component."""
        from cortex.metrics.health import compute_chi, CHIWeights

        components = [
            ("accuracy", 0.9, 0.1, 0.1, 0.1, 0.1),
            ("freshness", 0.1, 0.9, 0.1, 0.1, 0.1),
            ("coverage", 0.1, 0.1, 0.9, 0.1, 0.1),
            ("consistency", 0.1, 0.1, 0.1, 0.9, 0.1),
            ("efficiency", 0.1, 0.1, 0.1, 0.1, 0.9),
        ]

        weight_sets = [
            CHIWeights(1, 0, 0, 0, 0),
            CHIWeights(0, 1, 0, 0, 0),
            CHIWeights(0, 0, 1, 0, 0),
            CHIWeights(0, 0, 0, 1, 0),
            CHIWeights(0, 0, 0, 0, 1),
        ]

        for (name, a, f, c, con, e), w in zip(components, weight_sets):
            result = compute_chi(a, f, c, con, e, w)
            # The dominant component should determine the score
            dominant_value = [a, f, c, con, e][["accuracy", "freshness", "coverage", "consistency", "efficiency"].index(name)]
            assert abs(result.score - dominant_value) < 0.01, f"{name}: expected {dominant_value}, got {result.score}"


class TestSharpeRatioProperties:
    """Mathematical properties of the Sharpe ratio."""

    def test_sharpe_increases_with_mean(self):
        """Higher mean returns → higher Sharpe (same volatility)."""
        from cortex.metrics.financial import compute_sharpe_ratio
        low = compute_sharpe_ratio("m", [0.2, 0.3, 0.25, 0.22, 0.28])
        high = compute_sharpe_ratio("m", [0.8, 0.9, 0.85, 0.82, 0.88])
        assert high.sharpe_ratio > low.sharpe_ratio

    def test_sharpe_decreases_with_volatility(self):
        """Higher volatility → lower Sharpe (same mean)."""
        from cortex.metrics.financial import compute_sharpe_ratio
        stable = compute_sharpe_ratio("m", [0.5, 0.51, 0.49, 0.5, 0.505])
        volatile = compute_sharpe_ratio("m", [0.1, 0.9, 0.1, 0.9, 0.5])
        assert stable.sharpe_ratio > volatile.sharpe_ratio

    def test_sharpe_ranking_correctness(self):
        """A consistently good memory should rank higher than erratic one."""
        from cortex.metrics.financial import compute_sharpe_ratio
        consistent = compute_sharpe_ratio("good", [0.7, 0.72, 0.69, 0.71, 0.7])
        erratic = compute_sharpe_ratio("bad", [0.01, 1.0, 0.01, 1.0, 0.01])
        assert consistent.sharpe_ratio > erratic.sharpe_ratio


class TestBeliefPropagationAblation:
    """Verify BP catches contradictions that pairwise detection misses."""

    def test_transitive_detection(self):
        """BP should find A-C contradiction when only A-B and B-C exist."""
        from cortex.attribution.belief_propagation import ContradictionGraph
        g = ContradictionGraph()
        g.add_contradiction("A", "B", 0.9)
        g.add_contradiction("B", "C", 0.9)

        result = g.run_belief_propagation(decay_factor=0.7, min_confidence=0.3)

        # Without BP: only 2 contradictions
        assert result.direct_contradictions == 2
        # With BP: should also find A-C
        assert len(result.transitive_contradictions) >= 1

    def test_bp_vs_pairwise_coverage(self):
        """BP should detect more contradictions than pairwise in a chain."""
        from cortex.attribution.belief_propagation import ContradictionGraph
        g = ContradictionGraph()
        # Chain: A-B-C-D-E
        g.add_contradiction("A", "B", 0.95)
        g.add_contradiction("B", "C", 0.95)
        g.add_contradiction("C", "D", 0.95)
        g.add_contradiction("D", "E", 0.95)

        result = g.run_belief_propagation(decay_factor=0.8, min_confidence=0.2)

        pairwise_only = result.direct_contradictions  # 4
        total_with_bp = pairwise_only + len(result.transitive_contradictions)
        assert total_with_bp > pairwise_only, "BP should find additional contradictions"


class TestSISAEfficiencyScaling:
    """Verify SISA efficiency improves with more shards."""

    def test_efficiency_scales_with_shards(self):
        from cortex.compliance.sisa import SISAPartitioner

        ids = [f"m{i}" for i in range(100)]
        efficiencies = []

        for n_shards in [2, 4, 8, 16]:
            sp = SISAPartitioner(num_shards=n_shards)
            sp.partition(list(ids))
            result = sp.unlearn("m50")
            efficiencies.append(result.efficiency_gain)

        # Efficiency should be monotonically increasing with shard count
        for i in range(len(efficiencies) - 1):
            assert efficiencies[i] < efficiencies[i + 1], \
                f"Efficiency did not increase: {efficiencies}"

    def test_efficiency_bound(self):
        """Efficiency gain should be bounded by 1 - 1/num_shards."""
        from cortex.compliance.sisa import SISAPartitioner

        ids = [f"m{i}" for i in range(100)]
        sp = SISAPartitioner(num_shards=10)
        sp.partition(ids)
        result = sp.unlearn("m50")

        # With 10 equal shards of 10, efficiency = 1 - 10/100 = 0.9
        # Actual may vary due to unequal k-means splits
        assert 0.5 < result.efficiency_gain < 1.0


class TestCalibrationConvergence:
    """Verify isotonic calibration reduces error."""

    def test_calibration_reduces_error(self):
        from cortex.attribution.calibrator import CalibratorModel

        # Simulate noisy EAS scores vs ground-truth exact scores
        rng = np.random.default_rng(42)
        n = 200
        exact = rng.uniform(0, 1, n)
        eas = exact + rng.normal(0, 0.15, n)  # noisy proxy
        eas = np.clip(eas, 0, 1)

        # Before calibration: measure MAE
        mae_before = float(np.mean(np.abs(eas - exact)))

        # After calibration
        cal = CalibratorModel()
        cal.fit(eas.tolist(), exact.tolist())
        calibrated = np.array(cal.transform(eas.tolist()))
        mae_after = float(np.mean(np.abs(calibrated - exact)))

        assert mae_after < mae_before, \
            f"Calibration should reduce MAE: before={mae_before:.4f}, after={mae_after:.4f}"

    def test_calibration_monotonic(self):
        """Isotonic calibration should preserve ordering."""
        from cortex.attribution.calibrator import CalibratorModel

        cal = CalibratorModel()
        cal.fit(
            [0.1, 0.3, 0.5, 0.7, 0.9],
            [0.15, 0.35, 0.55, 0.65, 0.85],
        )

        inputs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        outputs = cal.transform(inputs)

        # Monotonically non-decreasing
        for i in range(len(outputs) - 1):
            assert outputs[i] <= outputs[i + 1] + 1e-10


class TestGiniCoefficient:
    """Verify Gini coefficient mathematical properties."""

    def test_perfect_equality(self):
        """Equal distribution should give Gini = 0."""
        from cortex.metrics.calculator import gini_coefficient
        assert gini_coefficient([1, 1, 1, 1, 1]) == 0.0

    def test_maximum_inequality(self):
        """One memory with all attribution should give Gini near 1."""
        from cortex.metrics.calculator import gini_coefficient
        scores = [0, 0, 0, 0, 100]
        g = gini_coefficient(scores)
        assert g > 0.7  # approaches 1 - 1/n

    def test_gini_increases_with_inequality(self):
        from cortex.metrics.calculator import gini_coefficient
        equal = gini_coefficient([10, 10, 10, 10])
        unequal = gini_coefficient([1, 1, 1, 37])
        assert unequal > equal


class TestContradictionRisk:
    """Verify CRS formula: CRS = 1 - Π(1 - pᵢ)."""

    def test_no_contradictions(self):
        from cortex.metrics.calculator import contradiction_risk
        assert contradiction_risk([]) == 0.0

    def test_certain_contradiction(self):
        from cortex.metrics.calculator import contradiction_risk
        assert contradiction_risk([1.0]) == 1.0

    def test_multiple_low_probabilities(self):
        """Many low probabilities should compound."""
        from cortex.metrics.calculator import contradiction_risk
        # 10 contradictions at p=0.1 each
        # CRS = 1 - (1-0.1)^10 = 1 - 0.9^10 ≈ 0.6513
        crs = contradiction_risk([0.1] * 10)
        expected = 1.0 - 0.9**10
        assert abs(crs - expected) < 1e-10

    def test_risk_monotonic(self):
        """Adding more contradictions should increase risk."""
        from cortex.metrics.calculator import contradiction_risk
        r1 = contradiction_risk([0.5])
        r2 = contradiction_risk([0.5, 0.5])
        r3 = contradiction_risk([0.5, 0.5, 0.5])
        assert r1 < r2 < r3
