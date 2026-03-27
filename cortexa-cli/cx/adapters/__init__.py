"""Memory system adapters."""

from cx.adapters.base import MemoryAdapter, MemoryRecord
from cx.adapters.demo import DemoAdapter

__all__ = ["MemoryAdapter", "MemoryRecord", "DemoAdapter", "get_adapter"]


def get_adapter(name: str, options: dict | None = None) -> MemoryAdapter:
    """Factory: instantiate an adapter by name."""
    options = options or {}
    if name == "demo":
        return DemoAdapter(**options)
    if name == "mem0":
        from cx.adapters.mem0 import Mem0Adapter
        return Mem0Adapter(**options)
    if name == "custom":
        from cx.adapters.custom import CustomAdapter
        return CustomAdapter(**options)
    raise ValueError(f"Unknown adapter: {name!r}. Available: demo, mem0, custom")
