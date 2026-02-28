"""Live event log using RichLog with full color formatting."""

from __future__ import annotations

from textual.widgets import RichLog

from cortexos.tui.helpers import hi_bar, hi_color
from cortexos.tui.state import EventRecord


def _verdict_summary(record: EventRecord) -> str:
    """Compact verdict summary like 4✓ or 3↯."""
    grounded = sum(1 for v in record.verdicts if v == "GROUNDED")
    failed = sum(1 for v in record.verdicts if v in ("UNSUPPORTED", "NUM_MISMATCH"))
    if grounded and not failed:
        return f"[#555555]{grounded}\u2713[/]"
    if failed:
        return f"[#FF6600]{failed}\u21af[/]"
    return ""


def _format_check(record: EventRecord) -> str:
    """Format a check event row."""
    ts = f"[#444444]{record.ts.strftime('%H:%M:%S')}[/]"
    bar = hi_bar(record.hi)
    summary = _verdict_summary(record)

    if record.hi < 0.1:
        icon = "[#00FF88]\u2726[/]"
        type_str = "[#00FF88]check [/]"
        val = f"[#00FF88]{record.hi:.2f}[/]"
    elif record.hi < 0.3:
        icon = "[#F5A623]\u25d0[/]"
        type_str = "[#F5A623]check [/]"
        val = f"[#F5A623]{record.hi:.2f}[/]"
    else:
        icon = "[#FF3366]\u25cf[/]"
        type_str = "[#FF3366]check [/]"
        val = f"[#FF3366]{record.hi:.2f}[/]"

    return f"  {ts}  {icon}  {type_str}  {bar}  {val}  {summary}"


def _format_gate(record: EventRecord) -> str:
    """Format a gate event row."""
    ts = f"[#444444]{record.ts.strftime('%H:%M:%S')}[/]"
    grounded = record.raw.get("grounded", True)

    if grounded:
        icon = "[#00DDFF]\u2726[/]"
        type_str = "[#00DDFF]gate  [/]"
        bar = hi_bar(record.hi)
        val = "[#00DDFF]PASS[/]"
    else:
        icon = "[#FF6600]\u25cf[/]"
        type_str = "[#FF6600]gate  [/]"
        bar = hi_bar(record.hi)
        val = "[bold #FF6600]BLOCKED[/]"

    return f"  {ts}  {icon}  {type_str}  {bar}  {val}"


def _format_shield(record: EventRecord) -> str:
    """Format a shield event row."""
    ts = f"[#444444]{record.ts.strftime('%H:%M:%S')}[/]"
    safe = record.raw.get("safe", True)

    if safe:
        icon = "[#88FF00]\u25c8[/]"
        type_str = "[#88FF00]shield[/]"
        val = "[#88FF00]SAFE[/]"
        return f"  {ts}  {icon}  {type_str}  {hi_bar(0.0)}  {val}"
    else:
        icon = "[bold #FF0044]\u25c8[/]"
        type_str = "[bold #FF0044]shield[/]"
        val = "[bold #FF0044]\U0001f534 INJECT[/]"
        return f"[on #1A0000]  {ts}  {icon}  {type_str}  {hi_bar(1.0)}  {val}[/]"


class EventLog(RichLog):
    """RichLog that formats EventRecords as richly colored lines."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=False, markup=True, wrap=False, **kwargs)
        self._filter_type: str | None = None
        self._auto_scroll = True

    def add_event(self, record: EventRecord) -> None:
        if self._filter_type and record.type != self._filter_type:
            return

        if record.type == "check":
            line = _format_check(record)
        elif record.type == "gate":
            line = _format_gate(record)
        elif record.type == "shield":
            line = _format_shield(record)
        else:
            return

        self.write(line)

        # Notify on injection
        if record.type == "shield" and not record.raw.get("safe", True):
            try:
                self.app.notify("\U0001f534 INJECTION BLOCKED", severity="error")
            except Exception:
                pass

    def set_filter(self, event_type: str | None) -> None:
        self._filter_type = event_type
