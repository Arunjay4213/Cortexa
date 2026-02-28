"""CortexOS Python SDK — developer-facing interface to the CortexOS memory engine."""

from cortexos.async_client import AsyncCortex
from cortexos.client import Cortex
from cortexos.errors import (
    AuthError,
    CortexError,
    MemoryNotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from cortexos.exceptions import CortexOSError, MemoryBlockedError
from cortexos.models import CheckResult, ClaimResult, GateResult, ShieldResult
from cortexos.types import (
    Attribution,
    CAMAAttribution,
    CAMAClaim,
    CAMAClaimSource,
    EASScore,
    Memory,
    Page,
    RecallAndAttributeResult,
    RecallResult,
)
from cortexos.verification import VerificationClient

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("cortexos")
except PackageNotFoundError:
    __version__ = "0.2.0"  # fallback for editable installs

__all__ = [
    # Clients
    "Cortex",
    "AsyncCortex",
    "VerificationClient",
    # Types
    "Memory",
    "Attribution",
    "CAMAAttribution",
    "CAMAClaim",
    "CAMAClaimSource",
    "EASScore",
    "RecallResult",
    "RecallAndAttributeResult",
    "Page",
    # Verification models
    "CheckResult",
    "ClaimResult",
    "GateResult",
    "ShieldResult",
    # Errors
    "CortexError",
    "CortexOSError",
    "MemoryBlockedError",
    "AuthError",
    "RateLimitError",
    "MemoryNotFoundError",
    "ValidationError",
    "ServerError",
]
