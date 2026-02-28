"""Tab 3: Memory — Gate/shield operations + memory health stats."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog, Static, TabPane

from cortexos.tui.state import EventRecord, SessionState


def _trust_bar(pct: float, width: int = 20) -> str:
    """Render a percentage as a filled bar."""
    filled = int(pct / 100 * width)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


class MemoryTab(TabPane):
    """Gate/shield event log with memory health stats."""

    def __init__(self, state: SessionState, **kwargs) -> None:
        super().__init__("MEMORY", id="tab-memory", **kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-pane"):
            yield Static("RECENT MEMORY OPERATIONS", id="memory-ops-title")
            with Vertical(id="memory-ops-panel"):
                yield RichLog(
                    highlight=False, markup=True, wrap=False,
                    id="memory-ops-log",
                )
            yield Static("MEMORY HEALTH", id="memory-health-title")
            with Vertical(id="memory-health-panel"):
                yield Static(self._render_health(), id="memory-health-content")

    def add_event(self, record: EventRecord) -> None:
        if record.type not in ("gate", "shield"):
            return

        log = self.query_one("#memory-ops-log", RichLog)
        ts = f"[#444444]{record.ts.strftime('%H:%M:%S')}[/]"
        agent = record.api_key_id or "unknown"
        preview = record.response_preview[:50] + "..." if len(record.response_preview) > 50 else record.response_preview

        if record.type == "shield":
            safe = record.raw.get("safe", True)
            if safe:
                status = "[#00FF88]\u2726 SAFE    [/]"
                line2 = f"          [#555555]src:shield_check[/]"
            else:
                status = "[bold #FF0044]\U0001f534 INJECT  [/]"
                line2 = f"          [#FF0044]src:shield_check  BLOCKED[/]"
                log.write(f"[on #1A0000]  {ts}  {status}  shield  {preview}[/]")
                log.write(f"[on #1A0000]{line2}[/]")
                self._refresh_health()
                return
        else:
            grounded = record.raw.get("grounded", True)
            if grounded:
                status = "[#00FF88]\u2726 PASSED  [/]"
                line2 = f"          [#555555]src:gate_check   score:{record.hi:.2f}[/]"
            else:
                status = "[#FF6600]\u25cf BLOCKED [/]"
                line2 = f"          [#FF6600]src:gate_check   HI:{record.hi:.2f}  flagged:{record.flagged}[/]"

        log.write(f"  {ts}  {status}  {'gate  ' if record.type == 'gate' else 'shield'}  {preview}")
        log.write(f"{line2}")
        log.write("")
        self._refresh_health()

    def _refresh_health(self) -> None:
        health = self.query_one("#memory-health-content", Static)
        health.update(self._render_health())

    def _render_health(self) -> str:
        s = self._state
        gate_events = s.gate_events()
        total = len(gate_events)
        blocked = s.blocked_count
        injections = s.injection_count
        anomalies = sum(
            1 for e in gate_events
            if e.type == "gate" and e.hi > 0.5
        )
        block_pct = f"{blocked / total * 100:.1f}%" if total > 0 else "0%"

        inj_color = "#FF0044" if injections > 0 else "#555555"
        inj_style = "bold " if injections > 0 else ""

        # Source trust distribution from agent stats
        agents = s.agents
        total_checks = max(sum(a.checks for a in agents.values()), 1)

        lines = [
            f"[#555555]writes attempted[/]  [#FFFFFF]{total:>3}[/]    "
            f"[#555555]blocked[/]       [#FF6600]{blocked:>3}[/]  [#555555]({block_pct})[/]",
            f"[#555555]injections caught[/] [{inj_style}{inj_color}]{injections:>3}[/]    "
            f"[#555555]anomalies[/]     [#F5A623]{anomalies:>3}[/]",
            "",
            "[#555555]SOURCE TRUST DISTRIBUTION[/]",
        ]

        # Show agent breakdown as source trust
        for agent_id, agent in sorted(agents.items(), key=lambda x: x[1].checks, reverse=True):
            pct = agent.checks / total_checks * 100
            name = agent_id[:14] if len(agent_id) > 14 else agent_id.ljust(14)
            if agent.avg_hi < 0.2:
                color = "#00FF88"
            elif agent.avg_hi < 0.5:
                color = "#F5A623"
            else:
                color = "#FF6600"
            bar = _trust_bar(pct)
            lines.append(f"[#555555]{name}[/]  [{color}]{bar}[/]  [{color}]{pct:>3.0f}%[/]")

        if not agents:
            lines.append("[#333333]no data yet[/]")

        return "\n".join(lines)
