"""Tool call widget — spinner -> collapsed one-liner -> expandable detail.

This is the #1 UX priority. Progressive disclosure of tool execution.
"""

from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static


_BRAILLE_FRAMES = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"

# Chevrons for expand/collapse
_CHEVRON_RIGHT = "\u25b8"  # ▸
_CHEVRON_DOWN = "\u25be"   # ▾


class ToolCallWidget(Widget):
    """Renders a single tool call with progressive disclosure.

    States:
      - running: shows animated braille spinner + tool name + elapsed time
      - done: shows collapsed one-liner with result summary + chevron
      - expanded: shows full result detail (toggled on click)
    """

    DEFAULT_CSS = """
    ToolCallWidget {
        height: auto;
        margin: 0 0 0 2;
        padding: 0;
        transition: opacity 300ms, background 300ms;
    }

    ToolCallWidget .tool-running {
        color: #E8A800;
    }

    ToolCallWidget .tool-done {
        color: #555570;
    }

    ToolCallWidget .tool-detail {
        color: #555570;
        margin: 0 0 0 2;
        display: none;
    }

    ToolCallWidget .tool-detail.visible {
        display: block;
    }

    ToolCallWidget:hover {
        background: $surface;
    }

    ToolCallWidget .tool-done:hover {
        text-style: bold;
    }
    """

    state = reactive("running")  # "running" | "done"
    expanded = reactive(False)

    def __init__(
        self,
        tool_name: str,
        tool_input_summary: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._tool_name = tool_name
        self._tool_input_summary = tool_input_summary
        self._result_summary = ""
        self._result_detail = ""
        self._spinner_frame = 0
        self._spinner_timer: Timer | None = None
        self._start = time.monotonic()

    def on_mount(self) -> None:
        self._spinner_timer = self.set_interval(0.08, self._advance_spinner)

    def _advance_spinner(self) -> None:
        if self.state != "running":
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(_BRAILLE_FRAMES)
        elapsed = time.monotonic() - self._start
        try:
            line = self.query_one("#tool-line", Static)
            t = Text()
            t.append(f"{_BRAILLE_FRAMES[self._spinner_frame]} ", style="#E8A800")
            t.append(self._tool_name, style="#00D4E8 bold")
            if self._tool_input_summary:
                t.append(f"({self._tool_input_summary})", style="#4A4A6A")
            t.append(f" {elapsed:.1f}s", style="#4A4A6A")
            line.update(t)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield Static(
            f"{_BRAILLE_FRAMES[0]} {self._tool_name}({self._tool_input_summary})",
            id="tool-line",
            classes="tool-running",
        )
        yield Static("", id="tool-detail", classes="tool-detail")

    def complete(self, summary: str, detail: str = "") -> None:
        """Mark tool call as complete with result summary."""
        self._result_summary = summary
        self._result_detail = detail
        # Defer if compose() hasn't run yet
        if self.is_mounted:
            self.state = "done"
        else:
            self.call_after_refresh(self._apply_complete)

    def _apply_complete(self) -> None:
        self.state = "done"

    def watch_state(self, state: str) -> None:
        try:
            line = self.query_one("#tool-line", Static)
        except Exception:
            return  # compose() hasn't run yet
        if state == "done":
            if self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None
            elapsed = time.monotonic() - self._start
            t = Text()
            t.append("\u2713 ", style="#00E87A")
            t.append(self._tool_name, style="#555570")
            t.append(f" \u2014 {self._result_summary}", style="#555570")
            t.append(f" ({elapsed:.1f}s)", style="#4A4A6A")
            if self._result_detail:
                chevron = _CHEVRON_DOWN if self.expanded else _CHEVRON_RIGHT
                t.append(f" {chevron}", style="#4A4A6A")
            line.update(t)
            line.remove_class("tool-running")
            line.add_class("tool-done")
            if self._result_detail:
                self.query_one("#tool-detail", Static).update(self._result_detail)

    def watch_expanded(self, expanded: bool) -> None:
        try:
            detail = self.query_one("#tool-detail", Static)
        except Exception:
            return  # compose() hasn't run yet
        if expanded and self._result_detail:
            detail.add_class("visible")
        else:
            detail.remove_class("visible")

        # Update chevron in summary line
        if self.state == "done" and self._result_detail:
            try:
                line = self.query_one("#tool-line", Static)
                elapsed = time.monotonic() - self._start
                t = Text()
                t.append("\u2713 ", style="#00E87A")
                t.append(self._tool_name, style="#555570")
                t.append(f" \u2014 {self._result_summary}", style="#555570")
                t.append(f" ({elapsed:.1f}s)", style="#4A4A6A")
                chevron = _CHEVRON_DOWN if expanded else _CHEVRON_RIGHT
                t.append(f" {chevron}", style="#4A4A6A")
                line.update(t)
            except Exception:
                pass

    def on_click(self) -> None:
        if self.state == "done" and self._result_detail:
            self.expanded = not self.expanded
