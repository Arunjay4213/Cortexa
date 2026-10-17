"""Tab 3: Memory — Memory health dashboard (top) + operations log (bottom)."""

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


def _dup_bar(pct: float, width: int = 20) -> str:
    """Duplicate % bar — red when high."""
    filled = int(pct / 100 * width)
    empty = width - filled
    if pct >= 40:
        color = "#FF3366"
    elif pct >= 20:
        color = "#F5A623"
    else:
        color = "#00FF88"
    return f"[{color}]{'█' * filled}[/][dim]{'░' * empty}[/]"


def _health_grade(avg_hi: float, dup_pct: float) -> tuple[str, str]:
    """Return (grade letter, color hex) based on HI and dup rate."""
    score = (1 - avg_hi) * 0.7 + (1 - dup_pct / 100) * 0.3
    if score >= 0.9:
        return "A", "#00FF88"
    if score >= 0.75:
        return "B", "#AAFF00"
    if score >= 0.6:
        return "C", "#F5A623"
    if score >= 0.4:
        return "D", "#FF6600"
    return "F", "#FF3366"


class MemoryTab(TabPane):
    """Memory health dashboard + gate/shield/write operations log."""

    def __init__(self, state: SessionState, **kwargs) -> None:
        super().__init__("MEMORY", id="tab-memory", **kwargs)
        self._state = state

    def on_mount(self) -> None:
        self.set_interval(30, self._refresh_health)

    def compose(self) -> ComposeResult:
        with Vertical(id="memory-pane"):
            yield Static("◈ MEMORY HEALTH", id="memory-health-title")
            with Vertical(id="memory-health-panel"):
                yield Static(self._render_health(), id="memory-health-content")
            yield Static("RECENT MEMORY OPERATIONS", id="memory-ops-title")
            with Vertical(id="memory-ops-panel"):
                yield RichLog(
                    highlight=False, markup=True, wrap=False,
                    id="memory-ops-log",
                )

    def add_event(self, record: EventRecord) -> None:
        if record.type not in ("gate", "shield", "memory_write", "memory_duplicate"):
            return

        log = self.query_one("#memory-ops-log", RichLog)
        ts = f"[#444444]{record.ts.strftime('%H:%M:%S')}[/]"
        agent = record.agent_id or record.api_key_id or "unknown"
        preview = record.response_preview[:50] + "..." if len(record.response_preview) > 50 else record.response_preview

        if record.type == "memory_write":
            mem_id = record.memory_id or ""
            status = "[#00FF88]\u2726 WRITE   [/]"
            log.write(f"  {ts}  {status}  {preview}")
            log.write(f"          [#555555]agent:{agent}  id:{mem_id[:12]}[/]")
            log.write("")

        elif record.type == "memory_duplicate":
            dup_pct = record.duplicate_pct or 0.0
            dup_pct_str = f"{dup_pct:.1f}%"
            status = "[#F5A623]\u25cf DUP     [/]"
            log.write(f"  {ts}  {status}  {preview}")
            dup_of = (record.duplicate_of or "")[:40]
            log.write(f"          [#F5A623]dup_of: '{dup_of}'  store_dup:{dup_pct_str}[/]")
            log.write("")

        elif record.type == "shield":
            safe = record.raw.get("safe", True)
            if safe:
                status = "[#00FF88]\u2726 SAFE    [/]"
                line2 = "          [#555555]src:shield_check[/]"
            else:
                status = "[bold #FF0044]\U0001f534 INJECT  [/]"
                line2 = "          [#FF0044]src:shield_check  BLOCKED[/]"
                log.write(f"[on #1A0000]  {ts}  {status}  shield  {preview}[/]")
                log.write(f"[on #1A0000]{line2}[/]")
                self._refresh_health()
                return
            log.write(f"  {ts}  {status}  shield  {preview}")
            log.write(line2)
            log.write("")
        else:
            # gate event
            grounded = record.raw.get("grounded", True)
            if grounded:
                status = "[#00FF88]\u2726 PASSED  [/]"
                line2 = f"          [#555555]src:gate_check   score:{record.hi:.2f}[/]"
            else:
                status = "[#FF6600]\u25cf BLOCKED [/]"
                line2 = f"          [#FF6600]src:gate_check   HI:{record.hi:.2f}  flagged:{record.flagged}[/]"
            log.write(f"  {ts}  {status}  gate    {preview}")
            log.write(f"{line2}")
            log.write("")

        self._refresh_health()

    def _refresh_health(self) -> None:
        try:
            health = self.query_one("#memory-health-content", Static)
            health.update(self._render_health())
        except Exception:
            pass

    def _render_health(self) -> str:
        s = self._state
        gate_events = s.gate_events()
        total_gates = len(gate_events)
        blocked = s.blocked_count
        injections = s.injection_count
        anomalies = sum(
            1 for e in gate_events
            if e.type == "gate" and e.hi > 0.5
        )
        block_pct = f"{blocked / total_gates * 100:.1f}%" if total_gates > 0 else "0%"

        inj_color = "#FF0044" if injections > 0 else "#555555"
        inj_style = "bold " if injections > 0 else ""

        # Memory write / duplicate stats
        total_writes = s.memory_write_count + s.memory_duplicate_count
        dup_count = s.memory_duplicate_count
        dup_pct = s.memory_duplicate_pct
        dup_bar = _dup_bar(dup_pct)

        if dup_pct >= 40:
            dup_color = "#FF3366"
            dup_warn = "  [bold #FF3366]\u26a0 HIGH[/]"
        elif dup_pct >= 20:
            dup_color = "#F5A623"
            dup_warn = "  [#F5A623]\u25cf WARN[/]"
        else:
            dup_color = "#00FF88"
            dup_warn = ""

        # Per-agent health grades (prominent at top)
        agents = s.agents
        total_checks = max(sum(a.checks for a in agents.values()), 1)

        lines: list[str] = []

        # ── Agent health grades ─────────────────────────────
        if agents:
            lines.append("[#555555]AGENT HEALTH[/]")
            lines.append(f"[#333333]{'─' * 50}[/]")
            for agent_id, agent in sorted(agents.items(), key=lambda x: x[1].checks, reverse=True):
                grade, grade_color = _health_grade(agent.avg_hi, s.memory_duplicate_pct)
                hi_val = agent.avg_hi
                if hi_val < 0.2:
                    hi_color = "#00FF88"
                elif hi_val < 0.5:
                    hi_color = "#F5A623"
                else:
                    hi_color = "#FF3366"
                pct = agent.checks / total_checks * 100
                bar = _trust_bar(pct)
                name = agent_id[:16] if len(agent_id) > 16 else agent_id.ljust(16)
                lines.append(
                    f"  [{grade_color}]{grade}[/]  [#DDDDDD]{name}[/]  "
                    f"[{hi_color}]HI:{hi_val:.2f}[/]  [{grade_color}]{bar}[/]  "
                    f"[#555555]{agent.checks}chk[/]"
                )
            lines.append("")
        else:
            lines.append("[#333333]no agent data yet — send a /v1/check request[/]")
            lines.append("")

        # ── Gate / shield stats ─────────────────────────────
        lines.append("[#555555]GATE & SHIELD[/]")
        lines.append(
            f"  [#555555]gates[/]  [#FFFFFF]{total_gates:>3}[/]   "
            f"[#555555]blocked[/]  [#FF6600]{blocked:>3}[/]  [#555555]({block_pct})[/]   "
            f"[#555555]anomalies[/]  [#F5A623]{anomalies:>3}[/]"
        )
        lines.append(
            f"  [#555555]injections caught[/]  [{inj_style}{inj_color}]{injections:>3}[/]"
        )
        lines.append("")

        # ── Memory store health ─────────────────────────────
        lines.append("[#555555]MEMORY STORE[/]")
        lines.append(
            f"  [#555555]writes[/]  [#FFFFFF]{s.memory_write_count:>4}[/]   "
            f"[#555555]dups[/]  [{dup_color}]{dup_count:>3}[/]   "
            f"[#555555]dup%[/]  [{dup_color}]{dup_pct:>5.1f}%[/]"
        )
        lines.append(f"  {dup_bar}{dup_warn}")
        if dup_pct > 0:
            lines.append(
                f"  [#555555]token savings if deduped:[/] [{dup_color}]{dup_pct:.1f}% fewer tokens/call[/]"
            )

        return "\n".join(lines)
