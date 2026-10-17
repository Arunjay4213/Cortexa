"""Drop-in replacement for supermemory.Supermemory with CortexOS verification."""

from __future__ import annotations

from typing import Any, Callable

from cortexos.exceptions import MemoryBlockedError
from cortexos.integrations.base import VerifiedMemoryClient, _DEFAULT_BASE_URL
from cortexos.models import GateResult, ShieldResult


class SuperMemoryClient(VerifiedMemoryClient):
    """
    Drop-in replacement for ``supermemory.Supermemory``.
    Adds cx.shield() + cx.gate() on every document add.
    Proxies the official SuperMemory SDK's API surface.

    Usage::

        from cortexos.integrations import SuperMemoryClient

        client = SuperMemoryClient(
            supermemory_api_key="sm-...",
            cortex_api_key="cx-...",
            sources=["Ground truth document text here."],
        )

        # Verified add — shield + gate run before write reaches SuperMemory
        result = client.add("Machine learning is a subset of AI.")

        # Search passes through unchanged
        results = client.search("machine learning")
    """

    def __init__(
        self,
        supermemory_api_key: str,
        cortex_api_key: str | None = None,
        cortex_base_url: str = _DEFAULT_BASE_URL,
        sources: list[str] | Callable[..., list[str]] | None = None,
        shield_enabled: bool = True,
        gate_enabled: bool = True,
        gate_threshold: float = 0.3,
        on_block: Callable[[str, GateResult], Any] | None = None,
        on_threat: Callable[[str, ShieldResult], Any] | None = None,
        **supermemory_kwargs: Any,
    ):
        """
        Args:
            supermemory_api_key: API key for SuperMemory.
            cortex_api_key:     API key for CortexOS verification engine.
            cortex_base_url:    Base URL of the CortexOS engine.
            sources:            Ground-truth docs for gate. See VerifiedMemoryClient.
            shield_enabled:     Run shield checks on writes.
            gate_enabled:       Run gate checks on writes.
            gate_threshold:     HI threshold for gate (0.0-1.0).
            on_block:           Callback when gate blocks: (memory, gate_result).
            on_threat:          Callback when shield fires: (memory, shield_result).
            **supermemory_kwargs: Extra kwargs passed to Supermemory().
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
            from supermemory import Supermemory
        except ImportError:
            raise ImportError(
                "supermemory is not installed. Run: pip install supermemory"
            ) from None

        self._sm = Supermemory(
            api_key=supermemory_api_key,
            **supermemory_kwargs,
        )

    # ── Verified write ───────────────────────────────────────────────────

    def add(
        self,
        content: str,
        container_tag: str | None = None,
        custom_id: str | None = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Verified document add. Shield + gate run before write reaches SuperMemory.

        Args:
            content:       The document text to store.
            container_tag: Optional container tag for organization.
            custom_id:     Optional custom identifier.
            metadata:      Arbitrary metadata dict.
            **kwargs:      Extra kwargs passed to SuperMemory's documents.add().

        Returns:
            SuperMemory's add() response on success.

        Raises:
            MemoryBlockedError: When shield or gate blocks the write.
        """
        source_type = "document"
        if metadata and "source_type" in metadata:
            source_type = metadata["source_type"]

        allowed, shield_result, gate_result = self._verify_write_sync(
            content, source_type=source_type
        )

        if not allowed:
            raise MemoryBlockedError(
                memory=content,
                shield_result=shield_result,
                gate_result=gate_result,
            )

        add_kwargs: dict[str, Any] = {"content": content}
        if container_tag is not None:
            add_kwargs["container_tag"] = container_tag
        if custom_id is not None:
            add_kwargs["custom_id"] = custom_id
        if metadata is not None:
            add_kwargs["metadata"] = metadata
        add_kwargs.update(kwargs)

        return self._sm.documents.add(**add_kwargs)

    def add_batch(
        self,
        documents: list[dict],
        **kwargs: Any,
    ) -> Any:
        """
        Verified batch add. Each document is verified before the batch is sent.

        Args:
            documents: List of document dicts with 'content' key.
            **kwargs:  Extra kwargs passed to SuperMemory's documents.batch().

        Returns:
            SuperMemory's batch response on success.

        Raises:
            MemoryBlockedError: When any document is blocked.
        """
        for doc in documents:
            content = doc.get("content", "")
            if not content:
                continue

            allowed, shield_result, gate_result = self._verify_write_sync(
                content, source_type="document"
            )
            if not allowed:
                raise MemoryBlockedError(
                    memory=content,
                    shield_result=shield_result,
                    gate_result=gate_result,
                )

        return self._sm.documents.batch(documents=documents, **kwargs)

    # ── Pass-through reads ───────────────────────────────────────────────

    def search(self, q: str, **kwargs: Any) -> Any:
        """Pass-through to SuperMemory document search."""
        return self._sm.search.documents(q=q, **kwargs)

    def search_memories(self, q: str, **kwargs: Any) -> Any:
        """Pass-through to SuperMemory memory search."""
        return self._sm.search.memories(q=q, **kwargs)

    def get(self, document_id: str, **kwargs: Any) -> Any:
        """Pass-through to SuperMemory document get."""
        return self._sm.documents.get(document_id, **kwargs)

    def list(self, **kwargs: Any) -> Any:
        """Pass-through to SuperMemory document list."""
        return self._sm.documents.list(**kwargs)

    def delete(self, document_id: str, **kwargs: Any) -> Any:
        """Pass-through to SuperMemory document delete."""
        return self._sm.documents.delete(document_id, **kwargs)

    def update(
        self,
        document_id: str,
        content: str | None = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> Any:
        """Pass-through to SuperMemory document update."""
        update_kwargs: dict[str, Any] = {}
        if content is not None:
            update_kwargs["content"] = content
        if metadata is not None:
            update_kwargs["metadata"] = metadata
        update_kwargs.update(kwargs)
        return self._sm.documents.update(document_id, **update_kwargs)

    def upload_file(self, file: Any, **kwargs: Any) -> Any:
        """Pass-through to SuperMemory file upload (no verification on binary)."""
        return self._sm.documents.upload_file(file=file, **kwargs)
