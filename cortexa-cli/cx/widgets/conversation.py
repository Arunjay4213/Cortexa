"""Scrollable conversation area — the main content zone."""

from textual.containers import VerticalScroll


class ConversationView(VerticalScroll):
    """Middle zone: scrollable container for messages, tool calls, panels.

    can_focus is disabled so the Input widget keeps focus at all times.
    Scrolling still works via mouse wheel and programmatic scroll_end().
    """

    can_focus = False

    DEFAULT_CSS = """
    ConversationView {
        scrollbar-color: #4A4A6A;
        scrollbar-color-hover: #00D4E8;
        scrollbar-color-active: #00D4E8;
        scrollbar-background: #12121A;
        scrollbar-size-vertical: 1;
    }
    """
