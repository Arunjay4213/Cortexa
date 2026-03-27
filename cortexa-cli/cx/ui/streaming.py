"""Streaming tree renderer for real-time action display."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.tree import Tree

from cx.ui.theme import CX_THEME, CYAN, GREEN, DIM, AMBER, RED


console = Console(theme=CX_THEME)


class StreamingTree:
    """A tree that grows in real-time using rich.live.Live.

    Usage:
        with StreamingTree("investigating...") as tree:
            node = tree.add_action("searching traces...")
            # ... do work ...
            tree.complete_action(node, "found 23 traces")
            tree.add_leaf("root cause: outdated memory")
    """

    def __init__(self, root_label: str = "cx") -> None:
        self._tree = Tree(f"[cx.primary]{root_label}[/]")
        self._live: Live | None = None
        self._active_nodes: dict[str, Tree] = {}

    def start(self) -> None:
        self._live = Live(
            self._tree,
            console=console,
            refresh_per_second=12,
            transient=False,
        )
        self._live.start()

    def stop(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    def __enter__(self) -> StreamingTree:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._tree)

    def add_action(self, label: str, key: str | None = None) -> str:
        """Add a spinning action node. Returns the key for later completion."""
        if key is None:
            key = f"action_{len(self._active_nodes)}"
        spinner = Spinner("dots", text=f"[{CYAN}]{label}[/]", style=CYAN)
        node = self._tree.add(spinner)
        self._active_nodes[key] = node
        self._refresh()
        return key

    def complete_action(self, key: str, result: str, status: str = "success") -> None:
        """Replace spinner with result text."""
        if key not in self._active_nodes:
            return
        node = self._active_nodes.pop(key)
        color = GREEN if status == "success" else AMBER if status == "warning" else RED
        icon = "✓" if status == "success" else "⚠" if status == "warning" else "✗"
        node.label = Text.from_markup(f"[{color}]{icon}[/] [{DIM}]{result}[/]")
        self._refresh()

    def add_leaf(self, text: str, style: str = "") -> None:
        """Add a non-spinning leaf node."""
        markup = f"[{style}]{text}[/]" if style else text
        self._tree.add(markup)
        self._refresh()

    def add_subtree(self, label: str) -> Tree:
        """Add a named subtree and return it for further nesting."""
        sub = self._tree.add(f"[cx.primary]{label}[/]")
        self._refresh()
        return sub


@contextmanager
def streaming_tree(root: str = "cx") -> Generator[StreamingTree, None, None]:
    """Context manager for a streaming tree display."""
    st = StreamingTree(root)
    try:
        st.start()
        yield st
    finally:
        st.stop()
