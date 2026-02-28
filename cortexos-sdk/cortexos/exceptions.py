"""Exceptions for CortexOS verification integrations."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortexos.models import GateResult, ShieldResult


class CortexOSError(Exception):
    """Base exception for all CortexOS integration errors."""


class MemoryBlockedError(CortexOSError):
    """Raised when a memory write is blocked by shield or gate."""

    def __init__(
        self,
        memory: str,
        shield_result: ShieldResult | None = None,
        gate_result: GateResult | None = None,
    ):
        self.memory = memory
        self.shield_result = shield_result
        self.gate_result = gate_result

        reason = "SHIELD" if shield_result else "GATE"
        preview = memory[:100] + "..." if len(memory) > 100 else memory
        super().__init__(
            f"Memory write blocked by CortexOS [{reason}]: {preview}"
        )

    @property
    def is_injection(self) -> bool:
        """Whether the block was due to an instruction injection attempt."""
        return (
            self.shield_result is not None
            and self.shield_result.threat_type == "INSTRUCTION_INJECTION"
        )

    @property
    def reason(self) -> str:
        """Human-readable reason for the block."""
        if self.shield_result and not self.shield_result.safe:
            return f"Shield: {self.shield_result.threat_type} ({self.shield_result.severity})"
        if self.gate_result and not self.gate_result.grounded:
            n = len(self.gate_result.flagged_claims)
            return f"Gate: {n} ungrounded claim(s), HI={self.gate_result.hallucination_index:.2f}"
        return "Unknown"


class VerificationUnavailableError(CortexOSError):
    """Raised when CortexOS API is unreachable (fail-open with warning)."""
