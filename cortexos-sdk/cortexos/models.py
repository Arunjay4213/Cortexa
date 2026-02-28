"""Data models for CortexOS verification results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClaimResult:
    """Result of verifying a single claim."""

    text: str
    grounded: bool
    verdict: str  # GROUNDED, NUM_MISMATCH, UNSUPPORTED, OPINION
    reason: str = ""
    source_quote: str | None = None
    confidence: float = 1.0


@dataclass
class CheckResult:
    """Result of a full verification check (POST /v1/check)."""

    hallucination_index: float  # 0.0 (perfect) to 1.0 (all hallucinated)
    total_claims: int
    grounded_count: int
    hallucinated_count: int
    opinion_count: int
    claims: list[ClaimResult]
    latency_ms: float

    @property
    def passed(self) -> bool:
        """Whether the check passed at the default 0.3 threshold."""
        return self.hallucination_index < 0.3

    def passed_at(self, threshold: float) -> bool:
        """Whether the check passed at a custom threshold."""
        return self.hallucination_index < threshold

    @classmethod
    def _from_api(cls, data: dict) -> CheckResult:
        claims = [
            ClaimResult(
                text=c["text"],
                grounded=c["grounded"],
                verdict=c["verdict"],
                reason=c.get("reason", ""),
                source_quote=c.get("source_quote"),
                confidence=c.get("confidence", 1.0),
            )
            for c in data.get("claims", [])
        ]
        return cls(
            hallucination_index=data["hallucination_index"],
            total_claims=data["total_claims"],
            grounded_count=data["grounded_count"],
            hallucinated_count=data["hallucinated_count"],
            opinion_count=data.get("opinion_count", 0),
            claims=claims,
            latency_ms=data.get("latency_ms", 0.0),
        )


@dataclass
class GateResult:
    """Result of a gate check (POST /v1/gate)."""

    grounded: bool
    hallucination_index: float
    flagged_claims: list[dict] = field(default_factory=list)
    suggested_corrections: list[dict] | None = None

    @classmethod
    def _from_api(cls, data: dict) -> GateResult:
        return cls(
            grounded=data["grounded"],
            hallucination_index=data["hallucination_index"],
            flagged_claims=data.get("flagged_claims", []),
            suggested_corrections=data.get("suggested_corrections"),
        )


@dataclass
class ShieldResult:
    """Result of a shield check (injection/anomaly detection)."""

    safe: bool
    threat_type: str | None = None  # INSTRUCTION_INJECTION, ANOMALY, etc.
    severity: str | None = None  # CRITICAL, WARN, INFO
    blocked_content: str | None = None
    source_type: str = "unknown"

    @classmethod
    def _from_api(cls, data: dict) -> ShieldResult:
        return cls(
            safe=data.get("safe", True),
            threat_type=data.get("threat_type"),
            severity=data.get("severity"),
            blocked_content=data.get("blocked_content"),
            source_type=data.get("source_type", "unknown"),
        )
