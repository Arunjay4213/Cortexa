"""Synthetic agent identity generators."""

from __future__ import annotations

import uuid


def generate_agent_ids(count: int, prefix: str = "stress-agent") -> list[str]:
    """Return a list of unique agent ID strings."""
    return [f"{prefix}-{i:04d}" for i in range(count)]


def unique_agent_id(prefix: str = "sa") -> str:
    """Return a single unique agent ID."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
