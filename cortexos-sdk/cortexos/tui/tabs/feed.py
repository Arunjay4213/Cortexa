"""Tab 1: Feed — Live event feed with stats sidebar and HI sparkline."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, TabPane

from cortexos.tui.state import EventRecord, SessionState
from cortexos.tui.widgets.event_log import EventLog
from cortexos.tui.widgets.hi_sparkline import HISparkline
from cortexos.tui.widgets.stats_panel import StatsPanel


class FeedTab(TabPane):
    """Live event feed with stats sidebar and HI sparkline."""

    BINDINGS = [
        ("f", "filter_type", "Filter"),
        ("p", "toggle_pause", "Pause"),
    ]

    def __init__(self, state: SessionState, **kwargs) -> None:
        super().__init__("\u26a1 FEED", id="tab-feed", **kwargs)
        self._state = state
        self._paused = False
        self._pending: list[EventRecord] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="feed-pane"):
            with Vertical(id="feed-left"):
                yield Static("\u26a1 LIVE FEED", id="feed-panel-title")
                with Vertical(id="feed-panel"):
                    yield EventLog(id="feed-log")
            with Vertical(id="feed-right"):
                yield Static("SESSION", id="session-title")
                with Vertical(id="session-panel"):
                    yield StatsPanel(self._state, id="session-stats")
                    yield Static("HI TREND  last 30", id="sparkline-title")
                    with Vertical(id="sparkline-panel"):
                        yield HISparkline(id="sparkline-content")

    def add_event(self, record: EventRecord) -> None:
        if self._paused:
            self._pending.append(record)
            return
        log = self.query_one("#feed-log", EventLog)
        log.add_event(record)

        stats = self.query_one("#session-stats", StatsPanel)
        stats.refresh_stats()

        sparkline = self.query_one("#sparkline-content", HISparkline)
        sparkline.update_values(self._state.hi_trend)

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        if not self._paused:
            for record in self._pending:
                self.add_event(record)
            self._pending.clear()

    def action_filter_type(self) -> None:
        log = self.query_one("#feed-log", EventLog)
        current = log._filter_type
        cycle = [None, "check", "gate", "shield"]
        idx = cycle.index(current) if current in cycle else 0
        next_filter = cycle[(idx + 1) % len(cycle)]
        log.set_filter(next_filter)
        self.notify(f"Filter: {next_filter or 'all'}")
