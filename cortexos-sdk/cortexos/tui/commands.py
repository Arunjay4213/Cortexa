"""Command palette provider for CortexOS Monitor."""

from __future__ import annotations

import json
import os
import tempfile
from typing import TYPE_CHECKING

from textual.command import Hit, Hits, Provider

if TYPE_CHECKING:
    from cortexos.tui.app import CortexMonitor


class CortexCommandProvider(Provider):
    """Provides commands for the CortexOS command palette."""

    async def search(self, query: str) -> Hits:
        app: CortexMonitor = self.app  # type: ignore[assignment]
        matcher = self.matcher(query)

        commands = [
            ("clear", "Clear session — reset all data", self._clear),
            ("export", "Export session to JSON file", self._export),
            ("filter check", "Show only check events", lambda: self._filter("check")),
            ("filter gate", "Show only gate events", lambda: self._filter("gate")),
            ("filter all", "Show all event types", lambda: self._filter(None)),
            ("threshold", f"Show gate threshold (HI \u2264 0.3)", self._show_threshold),
            ("connect", f"Show connection URL", self._show_connect),
            ("feed", "Switch to Feed tab", lambda: app.action_switch_tab("tab-feed")),
            ("claims", "Switch to Claims tab", lambda: app.action_switch_tab("tab-claims")),
            ("memory", "Switch to Memory tab", lambda: app.action_switch_tab("tab-memory")),
            ("agents", "Switch to Agents tab", lambda: app.action_switch_tab("tab-agents")),
            ("inspect", "Switch to Inspect tab", lambda: app.action_switch_tab("tab-inspect")),
            ("pause", "Toggle event stream pause", app.action_toggle_pause),
            ("quit", "Exit the monitor", app.action_quit),
        ]

        for name, help_text, callback in commands:
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    help=help_text,
                )

    def _clear(self) -> None:
        app: CortexMonitor = self.app  # type: ignore[assignment]
        app.state.clear()
        app.notify("Session cleared")

    def _export(self) -> None:
        app: CortexMonitor = self.app  # type: ignore[assignment]
        path = os.path.join(tempfile.gettempdir(), "cortex_session.json")
        data = {
            "total_checks": app.state.total_checks,
            "avg_hi": app.state.avg_hi,
            "halluc_pct": app.state.halluc_pct,
            "events": [e.raw for e in app.state.events],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        app.notify(f"Exported to {path}")

    def _filter(self, event_type: str | None) -> None:
        from cortexos.tui.tabs.feed import FeedTab
        from cortexos.tui.widgets.event_log import EventLog

        app: CortexMonitor = self.app  # type: ignore[assignment]
        feed = app.query_one(FeedTab)
        log = feed.query_one("#feed-log", EventLog)
        log.set_filter(event_type)
        app.notify(f"Filter: {event_type or 'all'}")

    def _show_threshold(self) -> None:
        app: CortexMonitor = self.app  # type: ignore[assignment]
        app.notify("Gate threshold: HI \u2264 0.3")

    def _show_connect(self) -> None:
        app: CortexMonitor = self.app  # type: ignore[assignment]
        app.notify(f"Connected to: {app.base_url}")
