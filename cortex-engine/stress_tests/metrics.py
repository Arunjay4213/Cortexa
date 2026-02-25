"""
Metric collection for CortexOS stress tests.

Classes:
  LatencyHistogram  — tracks operation latencies in milliseconds
  ThroughputCounter — sliding-window + cumulative throughput
  ErrorClassifier   — classifies errors by type
  MetricsCollector  — aggregates all metrics for a test run
"""

from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any


class ErrorType(str, Enum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    ATTRIBUTION_MISMATCH = "ATTRIBUTION_MISMATCH"
    CONSISTENCY_VIOLATION = "CONSISTENCY_VIOLATION"
    MEMORY_CORRUPTION = "MEMORY_CORRUPTION"
    SERVER_ERROR = "SERVER_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN = "UNKNOWN"


def classify_error(exc: Exception | None, status_code: int | None = None) -> ErrorType:
    """Classify an error into a known ErrorType."""
    if status_code is not None:
        if status_code == 429:
            return ErrorType.RATE_LIMITED
        if status_code == 422:
            return ErrorType.VALIDATION_ERROR
        if status_code == 404:
            return ErrorType.NOT_FOUND
        if status_code >= 500:
            return ErrorType.SERVER_ERROR
    if exc is not None:
        name = type(exc).__name__.lower()
        if "timeout" in name or "TimeoutException" in type(exc).__name__:
            return ErrorType.TIMEOUT
        if "connect" in name or "connection" in name:
            return ErrorType.CONNECTION_ERROR
    return ErrorType.UNKNOWN


class LatencyHistogram:
    """Simple in-memory latency tracker with percentile computation.

    Stores raw values for exact percentiles (suitable for test runs up to ~1M ops).
    """

    def __init__(self) -> None:
        self._values: list[float] = []
        self._lock = Lock()

    def record(self, latency_ms: float) -> None:
        with self._lock:
            self._values.append(latency_ms)

    def percentile(self, p: float) -> float:
        """Return the p-th percentile (0-100)."""
        with self._lock:
            if not self._values:
                return 0.0
            sorted_v = sorted(self._values)
            idx = math.ceil((p / 100.0) * len(sorted_v)) - 1
            idx = max(0, min(idx, len(sorted_v) - 1))
            return sorted_v[idx]

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._values)

    @property
    def mean(self) -> float:
        with self._lock:
            return sum(self._values) / len(self._values) if self._values else 0.0

    @property
    def min(self) -> float:
        with self._lock:
            return min(self._values) if self._values else 0.0

    @property
    def max(self) -> float:
        with self._lock:
            return max(self._values) if self._values else 0.0

    def summary(self) -> dict[str, float]:
        return {
            "count": self.count,
            "mean_ms": round(self.mean, 2),
            "min_ms": round(self.min, 2),
            "max_ms": round(self.max, 2),
            "p50_ms": round(self.percentile(50), 2),
            "p75_ms": round(self.percentile(75), 2),
            "p90_ms": round(self.percentile(90), 2),
            "p95_ms": round(self.percentile(95), 2),
            "p99_ms": round(self.percentile(99), 2),
        }


class ThroughputCounter:
    """Tracks ops/sec using 1-second buckets plus cumulative count."""

    def __init__(self, window_s: int = 60) -> None:
        self._buckets: deque[tuple[int, int]] = deque()  # (epoch_second, count)
        self._total = 0
        self._window_s = window_s
        self._start_time = time.monotonic()
        self._lock = Lock()

    def record(self, count: int = 1) -> None:
        now = int(time.monotonic())
        with self._lock:
            self._total += count
            if self._buckets and self._buckets[-1][0] == now:
                last = self._buckets[-1]
                self._buckets[-1] = (last[0], last[1] + count)
            else:
                self._buckets.append((now, count))
            # Trim old buckets
            cutoff = now - self._window_s
            while self._buckets and self._buckets[0][0] < cutoff:
                self._buckets.popleft()

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    @property
    def current_rps(self) -> float:
        """Mean ops/sec over the sliding window."""
        with self._lock:
            if not self._buckets:
                return 0.0
            window = len(self._buckets)
            total_in_window = sum(c for _, c in self._buckets)
            return total_in_window / max(window, 1)

    @property
    def overall_rps(self) -> float:
        elapsed = time.monotonic() - self._start_time
        return self._total / elapsed if elapsed > 0 else 0.0

    def per_second_timeline(self) -> list[dict]:
        with self._lock:
            return [{"second": s, "ops": c} for s, c in self._buckets]


@dataclass
class OperationResult:
    """Result of a single API operation."""
    success: bool
    latency_ms: float
    error_type: ErrorType | None = None
    error_msg: str | None = None
    status_code: int | None = None
    data: Any = None


class MetricsCollector:
    """Aggregates latency + throughput + errors for a test run."""

    def __init__(self, name: str, warmup_fraction: float = 0.0) -> None:
        self.name = name
        self.warmup_fraction = warmup_fraction
        self._results: list[OperationResult] = []
        self._lock = Lock()
        self._start_time = time.monotonic()
        self.throughput = ThroughputCounter()

    def record(self, result: OperationResult) -> None:
        with self._lock:
            self._results.append(result)
        if result.success:
            self.throughput.record()

    def _active_results(self) -> list[OperationResult]:
        """Drop warmup fraction from the front."""
        with self._lock:
            total = len(self._results)
        skip = int(total * self.warmup_fraction)
        with self._lock:
            return self._results[skip:]

    @property
    def error_rate(self) -> float:
        results = self._active_results()
        if not results:
            return 0.0
        return sum(1 for r in results if not r.success) / len(results)

    @property
    def error_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for r in self._active_results():
            if not r.success and r.error_type:
                counts[r.error_type.value] += 1
        return dict(counts)

    def latency_histogram(self) -> LatencyHistogram:
        h = LatencyHistogram()
        for r in self._active_results():
            if r.success:
                h.record(r.latency_ms)
        return h

    def report(self) -> dict:
        elapsed = time.monotonic() - self._start_time
        results = self._active_results()
        lat = self.latency_histogram()
        return {
            "test": self.name,
            "duration_s": round(elapsed, 2),
            "total_ops": len(results),
            "success_ops": sum(1 for r in results if r.success),
            "error_rate": round(self.error_rate, 4),
            "error_counts": self.error_counts,
            "throughput_overall_rps": round(self.throughput.overall_rps, 2),
            "latency": lat.summary(),
        }
