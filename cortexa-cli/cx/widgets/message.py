"""Message bubble widget — user, system, agent, and error messages.

Each message gets a role icon, optional timestamp, and fade-in animation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Union

from rich.text import Text
from textual.widgets import Static


_ROLE_ICONS = {
    "user": "\u203a",      # › user prompt
    "agent": "\u25c6",     # ◆ agent response
    "system": "\u00b7",    # · system info
    "error": "\u2716",     # ✖ error
    "warning": "\u25b2",   # ▲ warning
}

_ROLE_COLORS = {
    "user": "#00D4E8",
    "agent": "#00E87A",
    "system": "#555570",
    "error": "#E83050",
    "warning": "#E8A800",
}


class MessageBubble(Static):
    """A single message in the conversation view with role identity."""

    DEFAULT_CSS = """
    MessageBubble {
        transition: opacity 400ms;
    }
    """

    def __init__(
        self,
        content: Union[str, Text],
        role: str = "system",
        show_timestamp: bool = True,
        **kwargs,
    ) -> None:
        # Build display content with role icon and optional timestamp
        display = self._build_display(content, role, show_timestamp)
        super().__init__(display, **kwargs)
        self.add_class(f"message-{role}")
        self._role = role

    @staticmethod
    def _build_display(
        content: Union[str, Text],
        role: str,
        show_timestamp: bool,
    ) -> Union[str, Text]:
        """Prepend role icon and timestamp to content."""
        icon = _ROLE_ICONS.get(role, "\u00b7")
        color = _ROLE_COLORS.get(role, "#555570")

        # If content is already a Rich Text, prepend icon as a new Text
        if isinstance(content, Text):
            t = Text()
            t.append(f"{icon} ", style=f"bold {color}")
            if show_timestamp:
                ts = datetime.now().strftime("%H:%M")
                t.append(f"{ts} ", style="#4A4A6A")
            t.append_text(content)
            return t

        # Plain string content
        t = Text()
        t.append(f"{icon} ", style=f"bold {color}")
        if show_timestamp:
            ts = datetime.now().strftime("%H:%M")
            t.append(f"{ts} ", style="#4A4A6A")
        t.append(str(content))
        return t

    def on_mount(self) -> None:
        self.styles.opacity = 0.0
        self.call_after_refresh(self._animate_in)

    def _animate_in(self) -> None:
        self.styles.animate("opacity", 1.0, duration=0.35, easing="out_cubic")
