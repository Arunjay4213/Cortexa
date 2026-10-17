"""Tab 4: Agents — Per-agent breakdown with risk ranking and mini sparklines."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static, TabPane

from cortexos.tui.helpers import hi_color
from cortexos.tui.state import EventRecord, SessionState


_SPARK_BARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def _mini_trend(hi_history: list[float]) -> str:
    """5-char sparkline of recent HI values with per-bar coloring."""
    recent = hi_history[-5:]
    result = ""
    for v in recent:
        idx = min(7, int(v * 8))
        if v < 0.2:
            c = "#00FF88"
        elif v < 0.5:
            c = "#F5A623"
        else:
            c = "#FF3366"
        result += f"[{c}]{_SPARK_BARS[idx]}[/{c}]"
    # Pad to 5 if fewer
    result += "[dim]\u2591[/]" * (5 - len(recent))
    return result


class AgentsTab(TabPane):
    """Per-agent stats table sorted by avg HI descending."""

    def __init__(self, state: SessionState, **kwargs) -> None:
        super().__init__("AGENTS", id="tab-agents", **kwargs)
        self._state = state
        self._agent_hi_history: dict[str, list[float]] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="agents-pane"):
            yield DataTable(id="agents-table")
            yield Static("", id="agents-banner")

    def on_mount(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.add_columns("AGENT", "CHECKS", "AVG HI", "HALLUC%", "TREND", "LAST SEEN")
        table.cursor_type = "row"

    def add_event(self, record: EventRecord) -> None:
        # Use agent_id from the event (preferred over api_key_id)
        agent_id = record.agent_id if record.agent_id != "unknown" else (record.api_key_id or "unknown")
        if agent_id not in self._agent_hi_history:
            self._agent_hi_history[agent_id] = []
        self._agent_hi_history[agent_id].append(record.hi)
        self._rebuild()

    def _rebuild(self) -> None:
        table = self.query_one("#agents-table", DataTable)
        table.clear()

        # Sort agents by avg HI descending (worst at top)
        agents = sorted(
            self._state.agents.values(),
            key=lambda a: a.avg_hi,
            reverse=True,
        )

        for agent in agents:
            hi_val = agent.avg_hi
            color = hi_color(hi_val)
            hi_str = f"[{color}]{hi_val:.2f}[/]"

            pct = agent.halluc_pct
            if pct <= 0.1:
                pct_str = f"[#00FF88]{pct:.0%}[/]"
            elif pct <= 0.3:
                pct_str = f"[#F5A623]{pct:.0%}[/]"
            else:
                pct_str = f"[#FF3366]{pct:.0%}[/]"

            # Mini 5-value trend for this agent
            history = self._agent_hi_history.get(agent.api_key_id, [])
            trend = _mini_trend(history) if history else "[#333333]\u2500[/]"

            last = agent.last_seen.strftime("%H:%M:%S") if agent.last_seen else "\u2014"

            # Display name (truncate long names)
            name = agent.api_key_id
            if len(name) > 28:
                name = name[:25] + "..."

            table.add_row(name, str(agent.checks), hi_str, pct_str, trend, last)

        # Update risk banner
        banner = self.query_one("#agents-banner", Static)
        if agents and agents[0].halluc_pct > 0.2:
            worst = agents[0]
            banner.update(
                f"[bold #FF3366]\u2500\u2500 {worst.api_key_id} is your "
                f"highest-risk agent ({worst.halluc_pct:.0%} halluc rate) \u2500\u2500[/]"
            )
        elif agents:
            worst = agents[0]
            banner.update(
                f"[#555555]\u2500\u2500 {worst.api_key_id} "
                f"(avg HI={worst.avg_hi:.2f}, H%={worst.halluc_pct:.0%}) \u2500\u2500[/]"
            )
        else:
            banner.update("")
