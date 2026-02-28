"""Abstract base class for verified memory clients."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Callable

from cortexos.exceptions import MemoryBlockedError
from cortexos.models import GateResult, ShieldResult
from cortexos.verification import VerificationClient, _fail_open_warning

logger = logging.getLogger("cortexos.integrations")

_DEFAULT_BASE_URL = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")


class VerifiedMemoryClient(ABC):
    """
    Abstract base for verified memory clients.
    Subclass this to wrap any memory provider with CortexOS verification.

    Shield runs first (lightweight). If it blocks, gate is skipped.
    Gate only runs if sources are configured.
    If CortexOS is unreachable, writes are allowed with a warning (fail-open).
    """

    def __init__(
        self,
        cortex_api_key: str | None = None,
        cortex_base_url: str = _DEFAULT_BASE_URL,
        sources: list[str] | Callable[..., list[str]] | None = None,
        shield_enabled: bool = True,
        gate_enabled: bool = True,
        gate_threshold: float = 0.3,
        on_block: Callable[[str, GateResult], Any] | None = None,
        on_threat: Callable[[str, ShieldResult], Any] | None = None,
    ):
        """
        Args:
            cortex_api_key:  API key for CortexOS verification engine.
            cortex_base_url: Base URL of the CortexOS engine.
            sources:         Ground-truth documents for gate verification.
                             - list[str]: static source docs for all users
                             - callable: (user_id) -> list[str], dynamic per user
                             - None: shield-only mode (no gate check)
            shield_enabled:  Whether to run shield checks on writes.
            gate_enabled:    Whether to run gate checks on writes.
            gate_threshold:  Hallucination index threshold for gate (0.0-1.0).
            on_block:        Callback when gate blocks a write: (memory, gate_result).
            on_threat:       Callback when shield detects a threat: (memory, shield_result).
        """
        self.cortex = VerificationClient(
            api_key=cortex_api_key,
            base_url=cortex_base_url,
        )
        self.sources = sources
        self.shield_enabled = shield_enabled
        self.gate_enabled = gate_enabled
        self.gate_threshold = gate_threshold
        self.on_block = on_block
        self.on_threat = on_threat

    def _resolve_sources(self, user_id: str | None = None) -> list[str]:
        """Resolve sources for a given user."""
        if self.sources is None:
            return []
        if callable(self.sources):
            return self.sources(user_id)
        return self.sources

    async def _verify_write(
        self,
        candidate_memory: str,
        user_id: str | None = None,
        source_type: str = "user_session",
    ) -> tuple[bool, ShieldResult | None, GateResult | None]:
        """
        Run shield + gate on a candidate memory.

        Returns:
            (allowed, shield_result, gate_result)
            - allowed: True if the write should proceed
            - shield_result: non-None if shield blocked
            - gate_result: non-None if gate blocked
        """
        # 1. Shield check (runs first — cheaper)
        if self.shield_enabled:
            try:
                shield = await self.cortex.shield(candidate_memory, source_type)
                if not shield.safe:
                    if self.on_threat:
                        self.on_threat(candidate_memory, shield)
                    return False, shield, None
            except Exception as e:
                _fail_open_warning("shield", e)

        # 2. Gate check (only if sources configured)
        sources = self._resolve_sources(user_id)
        if self.gate_enabled and sources:
            try:
                gate = await self.cortex.gate(candidate_memory, sources)
                if not gate.grounded:
                    if self.on_block:
                        self.on_block(candidate_memory, gate)
                    return False, None, gate
            except Exception as e:
                _fail_open_warning("gate", e)

        return True, None, None

    def _verify_write_sync(
        self,
        candidate_memory: str,
        user_id: str | None = None,
        source_type: str = "user_session",
    ) -> tuple[bool, ShieldResult | None, GateResult | None]:
        """Synchronous wrapper for _verify_write."""
        return self.cortex._run_sync(
            self._verify_write(candidate_memory, user_id, source_type)
        )

    @staticmethod
    def _normalize_messages(messages: str | list[dict] | Any) -> str:
        """Convert messages (str or list[dict]) to plain text for verification."""
        if isinstance(messages, str):
            return messages
        if isinstance(messages, list):
            return " ".join(
                m.get("content", "") for m in messages if isinstance(m, dict)
            )
        return str(messages)
