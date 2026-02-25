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

__version__ = "0.1.0"

__all__ = [
    # Clients
    "Cortex",
    "AsyncCortex",
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
    # Errors
    "CortexError",
    "AuthError",
    "RateLimitError",
    "MemoryNotFoundError",
    "ValidationError",
    "ServerError",
]
