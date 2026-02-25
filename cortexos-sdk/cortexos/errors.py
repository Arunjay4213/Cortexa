"""Exceptions raised by the CortexOS SDK."""

from __future__ import annotations


class CortexError(Exception):
    """Base exception for all CortexOS SDK errors."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={str(self)!r}, status_code={self.status_code})"


class AuthError(CortexError):
    """Raised when the API key is missing, invalid, or expired (HTTP 401/403)."""


class RateLimitError(CortexError):
    """Raised when the server returns HTTP 429 (Too Many Requests)."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class MemoryNotFoundError(CortexError):
    """Raised when a requested memory_id does not exist (HTTP 404)."""

    def __init__(self, memory_id: str):
        super().__init__(f"Memory not found: {memory_id!r}", status_code=404)
        self.memory_id = memory_id


class ValidationError(CortexError):
    """Raised when the server rejects the request payload (HTTP 422)."""


class ServerError(CortexError):
    """Raised on unexpected 5xx responses from the server."""
