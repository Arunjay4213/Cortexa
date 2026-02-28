"""Inline confidence visualization widget."""

from __future__ import annotations

from textual.widgets import Static

from cortexos.tui.helpers import conf_color


class ConfidenceBar(Static):
    """Renders a 16-char inline bar showing confidence 0-1."""

    def __init__(self, confidence: float = 0.0, **kwargs) -> None:
        self._confidence = confidence
        super().__init__(self._format(confidence), **kwargs)

    def set_confidence(self, value: float) -> None:
        self._confidence = value
        self.update(self._format(value))

    @staticmethod
    def _format(conf: float) -> str:
        width = 16
        filled = int(conf * width)
        bar = "\u2588" * filled + "\u2591" * (width - filled)
        color = conf_color(conf)
        return f"[{color}]{bar}[/] {conf:.2f}"
