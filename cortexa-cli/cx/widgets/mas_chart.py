"""MAS distribution histogram using textual-plotext."""

from __future__ import annotations

from textual.widget import Widget
from textual.app import ComposeResult


class MASChart(Widget):
    """Renders a MAS distribution histogram using textual-plotext.

    Falls back silently if textual-plotext is not installed.
    """

    DEFAULT_CSS = """
    MASChart {
        height: 12;
        margin: 0 0 1 2;
        padding: 0;
    }
    """

    def __init__(self, mas_scores: list[float], **kwargs) -> None:
        super().__init__(**kwargs)
        self._mas_scores = mas_scores

    def compose(self) -> ComposeResult:
        try:
            from textual_plotext import PlotextPlot
            yield PlotextPlot(id="mas-plot")
        except ImportError:
            from textual.widgets import Static
            yield Static("")  # silent fallback

    def on_mount(self) -> None:
        try:
            from textual_plotext import PlotextPlot
            plot_widget = self.query_one("#mas-plot", PlotextPlot)
        except Exception:
            return

        plt = plot_widget.plt
        plt.clear_figure()
        plt.theme("dark")

        # Bin the scores
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        bin_labels = ["0-.2", ".2-.4", ".4-.6", ".6-.8", ".8-1"]
        counts = [0, 0, 0, 0, 0]

        for s in self._mas_scores:
            if s < 0.2:
                counts[0] += 1
            elif s < 0.4:
                counts[1] += 1
            elif s < 0.6:
                counts[2] += 1
            elif s < 0.8:
                counts[3] += 1
            else:
                counts[4] += 1

        colors = ["red", "red+", "yellow", "green", "green+"]
        plt.bar(bin_labels, counts, color=colors, width=0.8)
        plt.title("MAS Distribution")
        plt.xlabel("Score Range")
        plt.ylabel("Count")
