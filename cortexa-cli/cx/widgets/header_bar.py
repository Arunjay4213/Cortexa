"""Persistent header bar — 2-row cockpit with status, metrics, and health bar."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Static, Sparkline


# Heartbeat frames — subtle pulse for connection indicator
_HEARTBEAT = ["\u2581", "\u2582", "\u2583", "\u2585", "\u2587", "\u2588", "\u2587", "\u2585", "\u2583", "\u2582"]


class HeaderBar(Widget):
    """Top-of-screen 2-row status bar. Always visible."""

    health_score = reactive(0.0)
    memory_count = reactive(0)
    connected = reactive(False)
    mode = reactive("")
    ghost_count = reactive(0)
    contradiction_count = reactive(0)
    mas_scores = reactive(list, always_update=True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._pulse_bright = True
        self._pulse_timer: Timer | None = None
        self._uptime_seconds = 0
        self._uptime_timer: Timer | None = None
        self._glow_on = False
        self._glow_timer: Timer | None = None
        self._breathe_on = False
        self._breathe_timer: Timer | None = None
        self._heartbeat_frame = 0
        self._heartbeat_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        # Row 1: brand + spacer + mode + uptime + connection status
        with Horizontal(id="hdr-row1"):
            yield Static("cortexa", id="hdr-brand")
            yield Static("", classes="hdr-spacer")
            yield Static("", id="hdr-mode")
            yield Static("0:00", id="hdr-uptime")
            yield Static("\u25cb disconnected", id="hdr-status")
        # Row 2: health bar + sparkline + metrics
        with Horizontal(id="hdr-row2"):
            yield Static("", id="hdr-health-bar")
            yield Sparkline([], id="hdr-sparkline")
            yield Static("", classes="hdr-spacer")
            yield Static("", id="hdr-memories")
            yield Static("", id="hdr-ghosts")
            yield Static("", id="hdr-contradictions")

    def on_mount(self) -> None:
        self._uptime_timer = self.set_interval(1.0, self._tick_uptime)
        self._glow_timer = self.set_interval(2.0, self._tick_glow)
        self._breathe_timer = self.set_interval(3.0, self._tick_breathe)

    def _tick_uptime(self) -> None:
        self._uptime_seconds += 1
        mins = self._uptime_seconds // 60
        secs = self._uptime_seconds % 60
        try:
            self.query_one("#hdr-uptime", Static).update(f"{mins}:{secs:02d}")
        except Exception:
            pass

    def _tick_pulse(self) -> None:
        self._pulse_bright = not self._pulse_bright
        try:
            status = self.query_one("#hdr-status", Static)
            if self._pulse_bright:
                status.remove_class("pulse-dim")
                status.add_class("pulse-bright")
            else:
                status.remove_class("pulse-bright")
                status.add_class("pulse-dim")
        except Exception:
            pass

    def _tick_breathe(self) -> None:
        """Subtle brand text breathing — toggles between bold and normal."""
        self._breathe_on = not self._breathe_on
        try:
            brand = self.query_one("#hdr-brand", Static)
            if self._breathe_on:
                t = Text()
                t.append("cortexa", style="#00D4E8 bold")
                t.append(" \u2022", style="#00D4E8")
                brand.update(t)
            else:
                brand.update(Text("cortexa", style="#00D4E8 bold"))
        except Exception:
            pass

    def _tick_heartbeat(self) -> None:
        """Animate heartbeat indicator next to connection status."""
        self._heartbeat_frame = (self._heartbeat_frame + 1) % len(_HEARTBEAT)
        try:
            status = self.query_one("#hdr-status", Static)
            frame = _HEARTBEAT[self._heartbeat_frame]
            t = Text()
            t.append(f"{frame} ", style="#00E87A")
            t.append("connected", style="#00E87A")
            status.update(t)
        except Exception:
            pass

    def _tick_glow(self) -> None:
        self._glow_on = not self._glow_on
        try:
            ghosts_label = self.query_one("#hdr-ghosts", Static)
            contra_label = self.query_one("#hdr-contradictions", Static)
            if self._glow_on:
                if self.ghost_count > 0:
                    ghosts_label.add_class("glow")
                if self.contradiction_count > 0:
                    contra_label.add_class("glow")
            else:
                ghosts_label.remove_class("glow")
                contra_label.remove_class("glow")
        except Exception:
            pass

    def watch_connected(self, connected: bool) -> None:
        status = self.query_one("#hdr-status", Static)
        if connected:
            t = Text()
            t.append("\u25cf ", style="#00E87A")
            t.append("connected", style="#00E87A")
            status.update(t)
            status.add_class("on")
            status.add_class("pulse-bright")
            # Start pulse timer
            if not self._pulse_timer:
                self._pulse_timer = self.set_interval(1.5, self._tick_pulse)
            # Start heartbeat
            if not self._heartbeat_timer:
                self._heartbeat_timer = self.set_interval(0.15, self._tick_heartbeat)
        else:
            status.update("\u25cb disconnected")
            status.remove_class("on")
            status.remove_class("pulse-bright")
            status.remove_class("pulse-dim")
            if self._pulse_timer:
                self._pulse_timer.stop()
                self._pulse_timer = None
            if self._heartbeat_timer:
                self._heartbeat_timer.stop()
                self._heartbeat_timer = None

    def watch_mode(self, mode: str) -> None:
        label = self.query_one("#hdr-mode", Static)
        if mode:
            t = Text()
            t.append(f"[{mode}]", style="#555570")
            label.update(t)
        else:
            label.update("")

    def watch_memory_count(self, count: int) -> None:
        t = Text()
        t.append(f"{count}", style="#E4E4EF bold")
        t.append(" memories", style="#555570")
        self.query_one("#hdr-memories", Static).update(t)

    def watch_health_score(self, score: float) -> None:
        label = self.query_one("#hdr-health-bar", Static)
        t = Text()
        width = 12
        filled = int(score / 100 * width)
        empty = width - filled
        if score >= 75:
            color = "#00E87A"
        elif score >= 40:
            color = "#E8A800"
        else:
            color = "#E83050"
        t.append("\u2588" * filled, style=color)
        t.append("\u2591" * empty, style="#555570")
        t.append(f" {score:.0f}/100", style=f"bold {color}")
        label.update(t)

    def watch_ghost_count(self, count: int) -> None:
        label = self.query_one("#hdr-ghosts", Static)
        if count > 0:
            t = Text()
            t.append(f"{count}", style="#6c6c8a bold")
            t.append(" ghosts", style="#555570")
            label.update(t)
        else:
            label.update("")
            label.remove_class("glow")

    def watch_contradiction_count(self, count: int) -> None:
        label = self.query_one("#hdr-contradictions", Static)
        if count > 0:
            t = Text()
            t.append(f"{count}", style="#E8A800 bold")
            t.append(" contradictions", style="#555570")
            label.update(t)
        else:
            label.update("")
            label.remove_class("glow")

    def watch_mas_scores(self, scores: list) -> None:
        try:
            sparkline = self.query_one("#hdr-sparkline", Sparkline)
            if scores:
                sparkline.data = scores
            else:
                sparkline.data = []
        except Exception:
            pass

    def update_mas_from_adapter(self, adapter) -> None:
        """Pull MAS scores from adapter and update sparkline."""
        try:
            memories = adapter.list_memories()
            scores = [m.mas_score for m in memories if m.mas_score is not None]
            scores.sort()
            self.mas_scores = scores
        except Exception:
            pass
