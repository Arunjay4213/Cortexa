"""Live MAS sparkline for watch mode — shows last 30 MAS scores."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Sparkline, Static
from rich.text import Text


class WatchSparkline(Widget):
    """Persistent sparkline showing recent MAS scores during /watch mode."""

    DEFAULT_CSS = """
    WatchSparkline {
        height: 2;
        margin: 0 0 1 2;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scores: list[float] = []
        self._max_points = 30

    def compose(self) -> ComposeResult:
        label = Text()
        label.append("  watch ", style="#555570")
        label.append("last 30 MAS scores", style="#555570")
        yield Static(label, id="watch-label")
        yield Sparkline([], id="watch-sparkline")

    def add_score(self, score: float) -> None:
        """Add a new MAS score data point."""
        self._scores.append(score)
        if len(self._scores) > self._max_points:
            self._scores = self._scores[-self._max_points:]
        try:
            sparkline = self.query_one("#watch-sparkline", Sparkline)
            sparkline.data = list(self._scores)
        except Exception:
            pass
