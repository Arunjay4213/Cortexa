"""Tests for the calibration loop — isotonic regression bridge."""

import numpy as np
import pytest

from cortex.attribution.calibrator import CalibratorModel


class TestCalibratorFit:
    def test_fit_known_data(self):
        """Isotonic regression should fit correctly on known monotonic data."""
        model = CalibratorModel()
        eas = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        exact = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85]
        model.fit(eas, exact)
        assert model.is_fitted

    def test_transform_monotonic(self):
        """Transform output must be monotonically non-decreasing."""
        model = CalibratorModel()
        # Create non-monotonic data that isotonic regression should fix
        eas = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        exact = [0.2, 0.1, 0.3, 0.25, 0.5, 0.4, 0.7, 0.65, 0.9]
        model.fit(eas, exact)

        test_scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        calibrated = model.transform(test_scores)

        # Check monotonicity
        for i in range(1, len(calibrated)):
            assert calibrated[i] >= calibrated[i-1], \
                f"Not monotonic at index {i}: {calibrated[i]} < {calibrated[i-1]}"

    def test_transform_unfitted_returns_input(self):
        """Unfitted model should return input unchanged."""
        model = CalibratorModel()
        scores = [0.1, 0.5, 0.9]
        result = model.transform(scores)
        assert result == scores


class TestQualityMetrics:
    def test_metrics_fitted(self):
        model = CalibratorModel()
        eas = list(np.linspace(0, 1, 100))
        exact = list(np.linspace(0, 1, 100))  # perfect correlation
        model.fit(eas, exact)

        metrics = model.quality_metrics()
        assert metrics["fitted"] is True
        assert metrics["sample_count"] == 100
        assert metrics["r_squared"] >= 0.99
        assert metrics["mae"] < 0.01

    def test_metrics_unfitted(self):
        model = CalibratorModel()
        metrics = model.quality_metrics()
        assert metrics["fitted"] is False
        assert metrics["sample_count"] == 0


class TestSaveLoad:
    def test_save_load_roundtrip(self, tmp_path):
        model = CalibratorModel()
        eas = [0.1, 0.3, 0.5, 0.7, 0.9]
        exact = [0.15, 0.35, 0.55, 0.75, 0.85]
        model.fit(eas, exact)

        path = tmp_path / "calibrator.pkl"
        model.save(path)

        loaded = CalibratorModel()
        loaded.load(path)

        assert loaded.is_fitted
        # Transform should give same results
        test = [0.2, 0.4, 0.6, 0.8]
        orig = model.transform(test)
        loaded_result = loaded.transform(test)
        np.testing.assert_allclose(orig, loaded_result, atol=1e-6)


class TestGracefulFallback:
    def test_insufficient_pairs(self):
        """Model shouldn't crash with very few data points."""
        model = CalibratorModel()
        model.fit([0.5], [0.5])  # Just one point
        assert model.is_fitted

        result = model.transform([0.3, 0.5, 0.7])
        assert len(result) == 3
