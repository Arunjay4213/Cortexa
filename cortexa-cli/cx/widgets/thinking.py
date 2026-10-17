"""Thinking indicator — animated braille dots with cycling phrases and color shift."""

from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static


_BRAILLE_FRAMES = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"

_PHRASES = [
    "thinking",
    "reasoning",
    "analyzing",
    "connecting",
    "processing",
    "evaluating",
    "synthesizing",
]

# Subtle color cycle for the spinner — shifts through the palette
_SPINNER_COLORS = [
    "#00D4E8",  # accent
    "#00C8E0",
    "#00BCD8",
    "#00B0D0",
    "#00A4C8",
    "#00B0D0",
    "#00BCD8",
    "#00C8E0",
]


class ThinkingIndicator(Widget):
    """Animated braille thinking indicator with elapsed time and color breathing."""

    DEFAULT_CSS = """
    ThinkingIndicator {
        height: 1;
        margin: 0 0 0 2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frame = 0
        self._phrase_idx = 0
        self._phrase_ticks = 0
        self._color_idx = 0
        self._start = time.monotonic()
        self._timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Static("", id="thinking-line")

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.08, self._advance)
        self._advance()

    def _advance(self) -> None:
        self._frame = (self._frame + 1) % len(_BRAILLE_FRAMES)
        self._phrase_ticks += 1
        # Cycle phrase every ~30 ticks (~2.4s)
        if self._phrase_ticks >= 30:
            self._phrase_ticks = 0
            self._phrase_idx = (self._phrase_idx + 1) % len(_PHRASES)

        # Cycle spinner color every 4 ticks (~0.32s)
        if self._frame % 4 == 0:
            self._color_idx = (self._color_idx + 1) % len(_SPINNER_COLORS)

        elapsed = time.monotonic() - self._start
        phrase = _PHRASES[self._phrase_idx]
        spinner = _BRAILLE_FRAMES[self._frame]
        color = _SPINNER_COLORS[self._color_idx]

        t = Text()
        t.append(f" {spinner} ", style=color)
        t.append(f"{phrase}", style="#555570")
        # Animated dots — cycle 1 to 3
        dot_count = (self._frame // 3 % 3) + 1
        t.append("." * dot_count, style="#555570")
        t.append(" " * (3 - dot_count), style="")  # pad to prevent jitter
        t.append(f" {elapsed:.1f}s", style="#4A4A6A")

        try:
            self.query_one("#thinking-line", Static).update(t)
        except Exception:
            pass

    def dismiss(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        self.remove()
