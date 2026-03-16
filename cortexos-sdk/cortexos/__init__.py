"""CortexOS Python SDK — hallucination detection for LLM agents."""

from __future__ import annotations

import os
from importlib.metadata import version, PackageNotFoundError
from typing import Any

from cortexos.async_client import AsyncCortex
from cortexos.client import Cortex, _DEFAULT_BASE_URL
from cortexos.errors import (
    AuthError,
    CortexError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from cortexos.exceptions import CortexOSError, MemoryBlockedError
from cortexos.models import (
    CheckResult,
    ClaimResult,
    GateResult,
    MemoryHealthResult,
    MemoryWriteResult,
    ShieldResult,
    TraceMatch,
    TraceResult,
)
from cortexos.verification import VerificationClient

try:
    __version__ = version("cortexos")
except PackageNotFoundError:
    __version__ = "0.3.0"  # fallback for editable installs


# ── Module-level configuration ─────────────────────────────────────────────

_config: dict[str, Any] = {}


def configure(
    api_key: str | None = None,
    base_url: str | None = None,
) -> None:
    """
    Set module-level defaults for convenience functions.

    Args:
        api_key:  API key for CortexOS engine.
        base_url: Base URL for CortexOS engine.
    """
    if api_key is not None:
        _config["api_key"] = api_key
    if base_url is not None:
        _config["base_url"] = base_url


def _get_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> Cortex:
    """Resolve a Cortex client from explicit args, configure(), or env vars."""
    key = api_key or _config.get("api_key") or os.environ.get("CORTEX_API_KEY")
    url = base_url or _config.get("base_url") or _DEFAULT_BASE_URL
    return Cortex(api_key=key, base_url=url)


# ── Top-level convenience functions ────────────────────────────────────────


def check(
    response: str,
    sources: list[str],
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    config: dict[str, Any] | None = None,
) -> CheckResult:
    """
    Run a hallucination check on an LLM response against source documents.

    Uses CORTEX_API_KEY env var if api_key is not provided.

    Args:
        response: The LLM response text to verify.
        sources:  Ground-truth source documents.
        api_key:  API key (overrides env var and configure()).
        base_url: Base URL (overrides env var and configure()).
        config:   Optional overrides (e.g. attribution settings).

    Returns:
        CheckResult with hallucination_index and per-claim verdicts.
    """
    cx = _get_client(api_key, base_url)
    try:
        return cx.check(response, sources, config=config)
    finally:
        cx.close()


def gate(
    memory: str,
    sources: list[str],
    *,
    api_key: str | None = None,
    base_url: str | None = None,
) -> GateResult:
    """
    Gate check: should this memory be stored?

    Uses CORTEX_API_KEY env var if api_key is not provided.

    Args:
        memory:   The candidate memory text.
        sources:  Source documents to verify against.
        api_key:  API key (overrides env var and configure()).
        base_url: Base URL (overrides env var and configure()).

    Returns:
        GateResult with grounded flag and flagged claims.
    """
    cx = _get_client(api_key, base_url)
    try:
        return cx.gate(memory, sources)
    finally:
        cx.close()


__all__ = [
    # Clients
    "Cortex",
    "AsyncCortex",
    "VerificationClient",
    # Top-level API
    "check",
    "gate",
    "configure",
    # Result types
    "CheckResult",
    "ClaimResult",
    "GateResult",
    "MemoryHealthResult",
    "MemoryWriteResult",
    "ShieldResult",
    "TraceMatch",
    "TraceResult",
    # Errors
    "CortexError",
    "CortexOSError",
    "MemoryBlockedError",
    "AuthError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
]
