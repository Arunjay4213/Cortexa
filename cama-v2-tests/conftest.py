"""Shared fixtures for the CAMA v2 hostile test suite."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from cama.detect import Detector, EmbeddingDetector, get_detector
from cama.attribute import LOODetectorAttributor
from cama.pipeline import CAMAv2
from cama.types import Memory


# ── Detector fixtures ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def embedding_detector():
    """Session-scoped EmbeddingDetector — loads model once."""
    return EmbeddingDetector()


@pytest.fixture(scope="session")
def engine(embedding_detector):
    """Session-scoped CAMAv2 engine with real EmbeddingDetector."""
    return CAMAv2(detector=embedding_detector)


@pytest.fixture(scope="session")
def attributor(embedding_detector):
    """Session-scoped LOODetectorAttributor with real detector."""
    return LOODetectorAttributor(embedding_detector)


# ── Data fixtures ─────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"


def load_scenario(name: str) -> dict:
    """Load a test scenario from data/ directory."""
    path = DATA_DIR / f"{name}.json"
    return json.loads(path.read_text())


@pytest.fixture(scope="session")
def shipping_scenario():
    return load_scenario("shipping_scenario")


@pytest.fixture(scope="session")
def medical_scenario():
    return load_scenario("medical_scenario")


@pytest.fixture(scope="session")
def finance_scenario():
    return load_scenario("finance_scenario")


@pytest.fixture(scope="session")
def legal_scenario():
    return load_scenario("legal_scenario")


# ── Helpers ───────────────────────────────────────────────────────

def timed_trace(engine: CAMAv2, **kwargs) -> tuple:
    """Run engine.trace and return (result, elapsed_ms)."""
    start = time.perf_counter()
    result = engine.trace(**kwargs)
    elapsed = (time.perf_counter() - start) * 1000
    return result, elapsed
