"""Tab 1: Feed — Live event feed with stats sidebar and HI sparkline."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, TabPane

from cortexos.tui.state import EventRecord, SessionState
from cortexos.tui.widgets.feed_list import FeedList
from cortexos.tui.widgets.hi_sparkline import HISparkline
from cortexos.tui.widgets.stats_panel import StatsPanel


class FeedTab(TabPane):
    """Live event feed with stats sidebar and HI sparkline."""

    BINDINGS = [
        ("f", "filter_type", "Filter"),
        ("p", "toggle_pause", "Pause"),
        Binding("enter", "inspect_selected", "Inspect", show=False),
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
                    yield FeedList(id="feed-log")
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
        feed_list = self.query_one("#feed-log", FeedList)
        feed_list.add_event(record)

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
        feed_list = self.query_one("#feed-log", FeedList)
        current = feed_list._filter_type
        cycle = [None, "check", "gate", "shield", "memory_write", "memory_duplicate"]
        idx = cycle.index(current) if current in cycle else 0
        next_filter = cycle[(idx + 1) % len(cycle)]
        feed_list.set_filter(next_filter)
        self.notify(f"Filter: {next_filter or 'all'}")

    def action_inspect_selected(self) -> None:
        feed_list = self.query_one("#feed-log", FeedList)
        highlighted = feed_list.highlighted_child
        if highlighted is not None:
            record = getattr(highlighted, "_record", None)
            if record is not None:
                self.app.inspect_event(record)
                return
        # Fallback: inspect most recent event
        events = self._state.events
        if events:
            self.app.inspect_event(events[-1])
        else:
            self.notify("No events to inspect", severity="warning")

    def on_feed_list_event_selected(self, message: FeedList.EventSelected) -> None:
        self.app.inspect_event(message.record)
