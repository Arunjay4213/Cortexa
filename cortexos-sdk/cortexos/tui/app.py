"""Cortexa Monitor — 5-tab interactive verification debugger.

Bloomberg Terminal / cyberpunk aesthetic with semantic color coding.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import ContentSwitcher, Input, Static

from cortexos.tui.commands import CortexCommandProvider
from cortexos.tui.state import EventRecord, SessionState
from cortexos.tui.stream import SSEEvent, SSEStream
from cortexos.tui.tabs.agents import AgentsTab
from cortexos.tui.tabs.claims import ClaimsTab
from cortexos.tui.tabs.feed import FeedTab
from cortexos.tui.tabs.inspect import InspectTab
from cortexos.tui.tabs.memory import MemoryTab

CSS_PATH = Path(__file__).parent / "styles.tcss"

COMMANDS = {CortexCommandProvider}

_TAB_LABELS = [
    ("tab-feed", "[#00FF88][1][/] FEED"),
    ("tab-claims", "[#00FF88][2][/] CLAIMS"),
    ("tab-memory", "[#00FF88][3][/] MEMORY"),
    ("tab-agents", "[#00FF88][4][/] AGENTS"),
    ("tab-inspect", "[#00FF88][5][/] INSPECT"),
]

_CMD_HINTS = (
    "  check <text> <source>       threshold <0.0-1.0>\n"
    "  gate  <memory>              filter grounded|hallucinated|all\n"
    "  shield <text>               export\n"
    "  connect <url>               clear\n"
)


class CortexMonitor(App):
    """Real-time Cortexa verification monitor with 5 tabs."""

    CSS_PATH = str(CSS_PATH)
    TITLE = "Cortexa Monitor"
    COMMANDS = COMMANDS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("1", "switch_tab('tab-feed')", "Feed", show=False),
        Binding("2", "switch_tab('tab-claims')", "Claims", show=False),
        Binding("3", "switch_tab('tab-memory')", "Memory", show=False),
        Binding("4", "switch_tab('tab-agents')", "Agents", show=False),
        Binding("5", "switch_tab('tab-inspect')", "Inspect", show=False),
        Binding("p", "toggle_pause", "Pause", show=False),
        Binding("c", "clear_session", "Clear", show=False),
        Binding("colon", "show_command_palette", "Commands", show=False),
        Binding("escape", "dismiss_command_palette", "Dismiss", show=False),
    ]

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.state = SessionState()
        self._stream = SSEStream(base_url, api_key)
        self._paused = False
        self._active_tab = "tab-feed"
        self._connection_status = "connecting"

    def compose(self) -> ComposeResult:
        # Custom header (3 lines)
        with Vertical(id="cortex-header"):
            with Horizontal(id="header-bar"):
                yield Static(
                    "[bold #00FF88]\u2593\u2593 CORTEXA MONITOR \u2593\u2593[/]",
                    id="header-title",
                )
                yield Static(f"[#444444]{self.base_url}[/]", id="header-url")
                yield Static("[#F5A623]\u25cf ...[/]", id="header-status")
            with Horizontal(id="tab-bar"):
                for btn in self._make_tab_buttons():
                    yield btn
            yield Static("[#222222]" + "\u2500" * 200 + "[/]", id="header-sep")

        # Main content — manual ContentSwitcher instead of TabbedContent
        with ContentSwitcher(initial="tab-feed", id="main-content"):
            yield FeedTab(self.state)
            yield ClaimsTab(self.state)
            yield MemoryTab(self.state)
            yield AgentsTab(self.state)
            yield InspectTab()

        # Custom footer (1 line)
        yield Static(self._footer_text(), id="cortex-footer")

        # Command palette overlay
        with Vertical(id="cmd-overlay"):
            with Vertical(id="cmd-panel"):
                yield Input(placeholder=": ", id="cmd-input")
                yield Static(f"[#444444]{_CMD_HINTS}[/]", id="cmd-hints")

    def _make_tab_buttons(self) -> list[Static]:
        buttons = []
        for tab_id, label in _TAB_LABELS:
            active = tab_id == self._active_tab
            classes = "tab-btn --active" if active else "tab-btn"
            if active:
                display_label = label.replace("[#00FF88]", "[dim #00FF88]").replace("[/]", "[/]")
                btn = Static(f"[bold #FFFFFF]{display_label}[/]", classes=classes, id=f"btn-{tab_id}")
            else:
                display_label = label.replace("[#00FF88]", "[#00FF88 dim]")
                btn = Static(f"[#555555]{display_label}[/]", classes=classes, id=f"btn-{tab_id}")
            buttons.append(btn)
        return buttons

    def _footer_text(self) -> str:
        return (
            "[#00FF88][1-5][/] [#444444]tabs[/]  "
            "[#00FF88][enter][/] [#444444]inspect[/]  "
            "[#00FF88][:][/] [#444444]command[/]  "
            "[#00FF88][p][/] [#444444]pause[/]  "
            "[#00FF88][c][/] [#444444]clear[/]  "
            "[#00FF88][q][/] [#444444]quit[/]"
        )

    def on_mount(self) -> None:
        # Hide command palette overlay initially
        self.query_one("#cmd-overlay").display = False

        self._update_status("connecting", "#F5A623")
        self._stream.start(
            on_event=self._handle_sse_data,
            on_connected=lambda: self._update_status("connected", "#00FF88"),
            on_disconnected=lambda: self._update_status("reconnecting...", "#FF3366"),
        )

    def _update_status(self, text: str, color: str) -> None:
        self._connection_status = text
        try:
            bar = self.query_one("#header-status", Static)
            if text == "connected":
                bar.update(f"[{color}]\u25cf LIVE[/]")
            elif text == "connecting":
                bar.update(f"[{color}]\u25cf ...[/]")
            else:
                bar.update(f"[{color}]\u25cf DEAD[/]")
        except Exception:
            pass

    def _update_tab_bar(self) -> None:
        """Refresh tab button styling to reflect active tab."""
        for tab_id, label in _TAB_LABELS:
            try:
                btn = self.query_one(f"#btn-{tab_id}", Static)
                if tab_id == self._active_tab:
                    btn.add_class("--active")
                    btn.update(f"[bold #FFFFFF]{label}[/]")
                else:
                    btn.remove_class("--active")
                    btn.update(f"[#555555]{label}[/]")
            except Exception:
                pass

    # ── SSE event handling ─────────────────────────────────

    def _handle_sse_data(self, data: dict) -> None:
        event_type = data.get("type", "")

        if event_type == "connected":
            self._update_status("connected", "#00FF88")
            return

        if event_type == "heartbeat":
            return

        record = EventRecord.from_sse(data)
        if record is None:
            return

        self.state.add_event(record)

        try:
            self.query_one(FeedTab).add_event(record)
            self.query_one(ClaimsTab).add_event(record)
            self.query_one(MemoryTab).add_event(record)
            self.query_one(AgentsTab).add_event(record)
        except Exception:
            pass

    def on_sse_event(self, message: SSEEvent) -> None:
        self._handle_sse_data(message.data)

    # ── Actions ───────────────────────────────────────────────

    def action_switch_tab(self, tab_id: str) -> None:
        self._active_tab = tab_id
        switcher = self.query_one("#main-content", ContentSwitcher)
        switcher.current = tab_id
        self._update_tab_bar()

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        feed = self.query_one(FeedTab)
        feed.action_toggle_pause()
        if self._paused:
            self._update_status("paused", "#F5A623")
        else:
            self._update_status("connected", "#00FF88")

    def action_clear_session(self) -> None:
        self.state.clear()
        self.notify("Session cleared")

    def inspect_event(self, record: EventRecord) -> None:
        inspect = self.query_one(InspectTab)
        inspect.show_event(record)
        self.action_switch_tab("tab-inspect")

    def action_show_command_palette(self) -> None:
        overlay = self.query_one("#cmd-overlay")
        overlay.display = True
        inp = self.query_one("#cmd-input", Input)
        inp.value = ""
        inp.focus()

    def action_dismiss_command_palette(self) -> None:
        overlay = self.query_one("#cmd-overlay")
        overlay.display = False

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "cmd-input":
            cmd = event.value.strip()
            self.action_dismiss_command_palette()
            if cmd:
                self._execute_command(cmd)

    def _execute_command(self, cmd: str) -> None:
        parts = cmd.split(maxsplit=1)
        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if verb == "clear":
            self.action_clear_session()
        elif verb == "export":
            # Trigger command provider export
            import json, os, tempfile
            path = os.path.join(tempfile.gettempdir(), "cortex_session.json")
            data = {
                "total_checks": self.state.total_checks,
                "avg_hi": self.state.avg_hi,
                "halluc_pct": self.state.halluc_pct,
                "events": [e.raw for e in self.state.events],
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            self.notify(f"Exported to {path}")
        elif verb == "filter":
            from cortexos.tui.widgets.event_log import EventLog
            log = self.query_one(FeedTab).query_one("#feed-log", EventLog)
            filt = arg.lower() if arg else None
            if filt == "all":
                filt = None
            log.set_filter(filt)
            self.notify(f"Filter: {filt or 'all'}")
        elif verb == "threshold":
            self.notify(f"Gate threshold: HI \u2264 {arg or '0.3'}")
        elif verb == "connect":
            self.notify(f"Connected to: {arg or self.base_url}")
        elif verb in ("feed", "claims", "memory", "agents", "inspect"):
            self.action_switch_tab(f"tab-{verb}")
        elif verb == "quit":
            self.action_quit()
        else:
            self.notify(f"Unknown command: {verb}", severity="warning")

    # ── Feed row selection → Inspect ──────────────────────────

    def on_rich_log_link_clicked(self, message) -> None:
        """Not used but placeholder for future click handling."""
        pass

    async def on_unmount(self) -> None:
        await self._stream.stop()
