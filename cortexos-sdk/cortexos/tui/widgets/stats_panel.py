"""Session statistics panel widget with visual hierarchy."""

from __future__ import annotations

from textual.widgets import Static

from cortexos.tui.helpers import hi_color
from cortexos.tui.state import SessionState


def _render_stats(s: SessionState) -> str:
    tc = s.total_claims
    grounded_pct = s.total_grounded / tc if tc > 0 else 0.0
    halluc_pct = s.halluc_pct

    avg_hi = s.avg_hi
    avg_hi_color = hi_color(avg_hi)
    avg_lat = s.avg_latency
    p95_lat = s.p95_latency

    inj_color = "#FF0044" if s.injection_count > 0 else "#555555"
    inj_style = "bold " if s.injection_count > 0 else ""

    # Token savings estimate: deduped writes save one retrieval each
    total_mem = s.memory_write_count + s.memory_duplicate_count
    token_savings_pct = s.memory_duplicate_pct
    tok_color = "#00FF88" if token_savings_pct < 20 else "#F5A623" if token_savings_pct < 40 else "#FF3366"

    lines = [
        f"[#555555]checks    [/] [#FFFFFF]{s.total_checks:>6}[/]",
        f"[#555555]grounded  [/] [#00FF88]{grounded_pct:>5.0%}[/]",
        f"[#555555]halluc    [/] [#FF3366]{halluc_pct:>5.0%}[/]",
        f"[#222222]{'─' * 19}[/]",
        f"[#555555]avg HI    [/] [{avg_hi_color}]{avg_hi:>6.2f}[/]",
        f"[#555555]avg lat   [/] [#00DDFF]{avg_lat:>4.0f}ms[/]",
        f"[#555555]p95 lat   [/] [#00DDFF]{p95_lat:>4.0f}ms[/]",
        f"[#222222]{'─' * 19}[/]",
        f"[#555555]gates     [/] [#00DDFF]{len(s.gate_events()):>6}[/]",
        f"[#555555]blocked   [/] [#FF6600]{s.blocked_count:>6}[/]",
        f"[#555555]shield \U0001f6e1  [/] [{inj_style}{inj_color}]{s.injection_count:>6}[/]",
        f"[#222222]{'─' * 19}[/]",
        f"[#555555]mem writes[/] [#00DDFF]{s.memory_write_count:>6}[/]",
        f"[#555555]tok saved [/] [{tok_color}]{token_savings_pct:>5.1f}%[/]",
    ]
    return "\n".join(lines)


class StatsPanel(Static):
    """Displays live session statistics with semantic colors."""

    def __init__(self, state: SessionState, **kwargs) -> None:
        self._state = state
        super().__init__(_render_stats(state), **kwargs)

    def refresh_stats(self) -> None:
        self.update(_render_stats(self._state))

    def on_mount(self) -> None:
        self.update(_render_stats(self._state))
