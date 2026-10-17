"""Persistent input bar — prompt and text entry with visual feedback.

Features:
  - SpaceAwareInput: fixes space key in all terminal emulators
  - Tab completion for slash commands
  - Visual flash on submit
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Key
from textual.widget import Widget
from textual.widgets import Input, Static

# Slash commands available for tab completion
_SLASH_COMMANDS = [
    "/audit", "/clear", "/config", "/contradictions", "/export",
    "/fix", "/ghosts", "/health", "/help", "/memory",
    "/quit", "/search", "/stale", "/trace", "/watch",
]


class SpaceAwareInput(Input):
    """Input widget that explicitly handles space key for live terminal compatibility.

    Workaround for known Textual issue (#2796) where space key may not be
    properly dispatched in live terminal mode on certain terminal emulators.
    We intercept the space key before Textual's event dispatch and insert
    the character directly, regardless of terminal behavior.
    """

    async def _on_key(self, event: Key) -> None:
        """Override to ensure space is handled in all terminal emulators.

        Some terminals don't set is_printable for space, so we check key name only.
        """
        if event.key == "space":
            event.stop()
            event.prevent_default()
            self.insert_text_at_cursor(" ")
            return

        # Tab completion for slash commands
        if event.key == "tab" and self.value.startswith("/"):
            event.stop()
            event.prevent_default()
            prefix = self.value.lower()
            matches = [c for c in _SLASH_COMMANDS if c.startswith(prefix)]
            if len(matches) == 1:
                self.value = matches[0] + " "
                self.cursor_position = len(self.value)
            elif matches:
                # Find longest common prefix
                common = matches[0]
                for m in matches[1:]:
                    while not m.startswith(common):
                        common = common[:-1]
                if len(common) > len(self.value):
                    self.value = common
                    self.cursor_position = len(self.value)
            return

        await super()._on_key(event)


class InputBar(Widget):
    """Bottom-of-screen input area. Always visible."""

    def compose(self) -> ComposeResult:
        yield Static("\u203a ", id="prompt-char")
        yield SpaceAwareInput(
            placeholder="ask anything, or /help",
            id="prompt-input",
        )

    def flash(self) -> None:
        """Brief visual pulse on submit — border flashes accent then resets."""
        self.add_class("flash")
        self.set_timer(0.3, lambda: self.remove_class("flash"))
