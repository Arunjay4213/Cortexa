"""Calibration Loop — Two-Speed Bridge (§3.4).

ContextCite writes (EAS, exact) pairs to calibration_pairs. The calibrator
fits an isotonic regression so EAS scores self-improve over time.

Isotonic regression ensures the calibration mapping is monotonic — higher
raw EAS scores always map to higher calibrated scores.
"""

from __future__ import annotations

from pathlib import Path

import joblib
from typing import Any

import numpy as np

# Global calibrator — loaded on startup, refreshed periodically
_calibrator: "CalibratorModel | None" = None


class CalibratorModel:
    """Isotonic regression calibrator for EAS → calibrated scores."""

    def __init__(self):
        self._model: Any = None
        self._fitted = False
        self._sample_count = 0

    def fit(self, eas_scores: list[float], exact_scores: list[float]) -> None:
        """Fit isotonic regression on (EAS, exact) calibration pairs."""
        from sklearn.isotonic import IsotonicRegression

        X = np.array(eas_scores)
        y = np.array(exact_scores)

        self._model = IsotonicRegression(
            y_min=0.0, y_max=1.0, out_of_bounds="clip"
        )
        self._model.fit(X, y)
        self._fitted = True
        self._sample_count = len(eas_scores)

    def transform(self, eas_scores: list[float]) -> list[float]:
        """Apply calibration to raw EAS scores."""
        if not self._fitted or self._model is None:
            return eas_scores
        X = np.array(eas_scores)
        return self._model.transform(X).tolist()

    def save(self, path: str | Path) -> None:
        """Serialize the fitted model using joblib (sklearn's standard)."""
        joblib.dump({
            "model": self._model,
            "fitted": self._fitted,
            "sample_count": self._sample_count,
        }, path)

    def load(self, path: str | Path) -> None:
        """Load a serialized model."""
        data = joblib.load(path)
        self._model = data["model"]
        self._fitted = data["fitted"]
        self._sample_count = data["sample_count"]

    def quality_metrics(self) -> dict:
        """R-squared, mean absolute error, sample count."""
        if not self._fitted or self._model is None:
            return {
                "r_squared": 0.0,
                "mae": 0.0,
                "sample_count": 0,
                "fitted": False,
            }

        X = self._model.X_thresholds_
        y_true = self._model.y_thresholds_
        y_pred = self._model.transform(X)

        # R-squared
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # MAE
        mae = float(np.mean(np.abs(y_true - y_pred)))

        return {
            "r_squared": float(r_squared),
            "mae": mae,
            "sample_count": self._sample_count,
            "fitted": True,
        }

    @property
    def is_fitted(self) -> bool:
        return self._fitted


async def refresh_calibrator(
    min_pairs: int = 50,
) -> CalibratorModel | None:
    """Read calibration pairs from DB and fit a new calibrator.

    Returns None if fewer than min_pairs available.
    """
    from sqlalchemy import select
    from cortex.database import async_session
    from cortex.db.tables import calibration_pairs

    async with async_session() as db:
        rows = (
            await db.execute(
                select(calibration_pairs)
                .order_by(calibration_pairs.c.created_at.desc())
                .limit(5000)
            )
        ).all()

    if len(rows) < min_pairs:
        return None

    eas_scores = [r.eas_score for r in rows]
    exact_scores = [r.exact_score for r in rows]

    model = CalibratorModel()
    model.fit(eas_scores, exact_scores)
    return model


async def refresh_calibrator_on_startup() -> None:
    """Called from app lifespan — best-effort load."""
    global _calibrator
    try:
        _calibrator = await refresh_calibrator()
    except Exception:
        _calibrator = None


def get_calibrator() -> CalibratorModel | None:
    """Get the global calibrator instance."""
    return _calibrator


def set_calibrator(model: CalibratorModel | None) -> None:
    """Set the global calibrator instance (for testing)."""
    global _calibrator
    _calibrator = model
