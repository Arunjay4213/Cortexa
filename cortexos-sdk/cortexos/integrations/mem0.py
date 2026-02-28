"""Drop-in replacement for mem0.MemoryClient with CortexOS verification."""

from __future__ import annotations

from typing import Any, Callable

from cortexos.exceptions import MemoryBlockedError
from cortexos.integrations.base import VerifiedMemoryClient, _DEFAULT_BASE_URL
from cortexos.models import GateResult, ShieldResult


class Mem0Client(VerifiedMemoryClient):
    """
    Drop-in replacement for ``mem0.MemoryClient``.
    Adds cx.shield() + cx.gate() on every .add() call.
    Identical API surface to the official Mem0 client.

    Usage::

        from cortexos.integrations import Mem0Client

        client = Mem0Client(
            mem0_api_key="m0-...",
            cortex_api_key="cx-...",
            sources=["Product ships from warehouse in 2-3 days."],
        )

        # Verified add — shield + gate run before write reaches Mem0
        result = client.add(
            "User said they want 2-day shipping",
            user_id="user-123",
        )

        # All other methods pass through unchanged
        results = client.search("shipping preferences", user_id="user-123")
    """

    def __init__(
        self,
        mem0_api_key: str,
        cortex_api_key: str | None = None,
        cortex_base_url: str = _DEFAULT_BASE_URL,
        sources: list[str] | Callable[..., list[str]] | None = None,
        shield_enabled: bool = True,
        gate_enabled: bool = True,
        gate_threshold: float = 0.3,
        on_block: Callable[[str, GateResult], Any] | None = None,
        on_threat: Callable[[str, ShieldResult], Any] | None = None,
        **mem0_kwargs: Any,
    ):
        """
        Args:
            mem0_api_key:    API key for the Mem0 platform.
            cortex_api_key:  API key for CortexOS verification engine.
            cortex_base_url: Base URL of the CortexOS engine.
            sources:         Ground-truth docs for gate. See VerifiedMemoryClient.
            shield_enabled:  Run shield checks on writes.
            gate_enabled:    Run gate checks on writes.
            gate_threshold:  HI threshold for gate (0.0-1.0).
            on_block:        Callback when gate blocks: (memory, gate_result).
            on_threat:       Callback when shield fires: (memory, shield_result).
            **mem0_kwargs:   Extra kwargs passed to mem0.MemoryClient().
        """
        super().__init__(
            cortex_api_key=cortex_api_key,
            cortex_base_url=cortex_base_url,
            sources=sources,
            shield_enabled=shield_enabled,
            gate_enabled=gate_enabled,
            gate_threshold=gate_threshold,
            on_block=on_block,
            on_threat=on_threat,
        )

        try:
            from mem0 import MemoryClient
        except ImportError:
            raise ImportError(
                "mem0 is not installed. Run: pip install mem0ai"
            ) from None

        self._mem0 = MemoryClient(api_key=mem0_api_key, **mem0_kwargs)

    # ── Verified write ───────────────────────────────────────────────────

    def add(
        self,
        messages: str | list[dict],
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: dict | None = None,
        filters: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Verified add. Shield + gate run before write reaches Mem0.

        Args:
            messages:  Text string or list of message dicts (role/content).
            user_id:   Mem0 user identifier.
            agent_id:  Mem0 agent identifier.
            run_id:    Mem0 run identifier.
            metadata:  Arbitrary metadata dict.
            filters:   Mem0 filters.
            **kwargs:  Extra kwargs passed to Mem0's add().

        Returns:
            Mem0's add() response on success.

        Raises:
            MemoryBlockedError: When shield or gate blocks the write.
        """
        memory_text = self._normalize_messages(messages)

        source_type = "user_session"
        if metadata and "source_type" in metadata:
            source_type = metadata["source_type"]

        allowed, shield_result, gate_result = self._verify_write_sync(
            memory_text, user_id=user_id, source_type=source_type
        )

        if not allowed:
            raise MemoryBlockedError(
                memory=memory_text,
                shield_result=shield_result,
                gate_result=gate_result,
            )

        return self._mem0.add(
            messages,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            metadata=metadata,
            filters=filters,
            **kwargs,
        )

    # ── Pass-through reads ───────────────────────────────────────────────

    def search(
        self,
        query: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        filters: dict | None = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> Any:
        """Pass-through to Mem0 search. No verification needed on reads."""
        return self._mem0.search(
            query,
            user_id=user_id,
            agent_id=agent_id,
            run_id=run_id,
            filters=filters,
            limit=limit,
            **kwargs,
        )

    def get_all(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        filters: dict | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """Pass-through to Mem0 get_all."""
        kw: dict[str, Any] = {}
        if user_id is not None:
            kw["user_id"] = user_id
        if agent_id is not None:
            kw["agent_id"] = agent_id
        if run_id is not None:
            kw["run_id"] = run_id
        if filters is not None:
            kw["filters"] = filters
        if limit is not None:
            kw["limit"] = limit
        kw.update(kwargs)
        return self._mem0.get_all(**kw)

    def update(
        self,
        memory_id: str,
        text: str,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """Pass-through to Mem0 update."""
        kw: dict[str, Any] = {"memory_id": memory_id, "text": text}
        if metadata is not None:
            kw["metadata"] = metadata
        kw.update(kwargs)
        return self._mem0.update(**kw)

    def delete(self, memory_id: str, **kwargs: Any) -> Any:
        """Pass-through to Mem0 delete."""
        return self._mem0.delete(memory_id, **kwargs)

    def delete_all(
        self,
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        filters: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """Pass-through to Mem0 delete_all."""
        kw: dict[str, Any] = {}
        if user_id is not None:
            kw["user_id"] = user_id
        if agent_id is not None:
            kw["agent_id"] = agent_id
        if run_id is not None:
            kw["run_id"] = run_id
        if filters is not None:
            kw["filters"] = filters
        kw.update(kwargs)
        return self._mem0.delete_all(**kw)

    def history(self, memory_id: str, **kwargs: Any) -> Any:
        """Pass-through to Mem0 history."""
        return self._mem0.history(memory_id, **kwargs)
