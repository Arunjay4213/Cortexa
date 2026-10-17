"""Hallucination Index score bar widget."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static

from cortexos.tui.helpers import hi_color


class ScoreBar(Static):
    """Colored bar showing hallucination index 0-1."""

    score: reactive[float] = reactive(0.0)

    def watch_score(self, value: float) -> None:
        width = 20
        filled = int(value * width)
        bar = "\u2588" * filled + "\u2591" * (width - filled)
        color = hi_color(value)
        self.update(f"[{color}]{bar}[/] {value:.1%}")
