"""CortexOS Live Monitor — Rich-based terminal dashboard.

Warp-inspired design:
  - Each event is an atomic "block" with a colored left-border (green=grounded, red=halluc, amber=blocked)
  - Header: session stats + connection status
  - Feed: scrolling event blocks (last 20)
  - Sidebar: session stats panel + HI sparkline
  - Inspect: last event detail with confidence badges [✓ 92%] per claim
  - Groundedness %, gate blocks, memory writes surfaced in sidebar

Press Ctrl-C to quit.
"""

from __future__ import annotations

import asyncio
import signal
from collections import deque
from datetime import datetime, timezone

from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cortexos.tui.state import EventRecord, SessionState
from cortexos.tui.stream import SSEStream

# ── colour palette ────────────────────────────────────────────────────────────
GREEN   = "#00FF88"
RED     = "#FF3366"
AMBER   = "#F5A623"
CYAN    = "#00DDFF"
PURPLE  = "#AA44FF"
ORANGE  = "#FF6600"
DIM     = "#444444"
MUTED   = "#333333"
WHITE   = "#FFFFFF"
GREY    = "#888888"
BG      = "#0D0D0D"

FEED_MAX      = 20
SPARKLINE_W   = 24


# ── helpers ───────────────────────────────────────────────────────────────────

def _hi_color(hi: float) -> str:
    if hi < 0.25: return GREEN
    if hi < 0.55: return AMBER
    return RED


def _conf_color(conf: float) -> str:
    if conf >= 0.85: return GREEN
    if conf >= 0.60: return AMBER
    return RED


def _verdict_sym(verdict: str) -> tuple[str, str]:
    """(symbol, color)"""
    v = verdict.upper() if verdict else ""
    if v in ("GROUNDED", "ENTAILED", "SUPPORTED"):
        return "✓", GREEN
    if v in ("UNSUPPORTED", "CONTRADICTED", "HALLUCINATED"):
        return "✗", RED
    return "~", AMBER


def _block_border_color(record: EventRecord) -> str:
    """Left-border color for event block — Warp-style status indicator."""
    if record.type == "shield":
        safe = record.raw.get("safe", True)
        return GREEN if safe else ORANGE
    if record.type == "gate":
        grounded = record.raw.get("grounded", True)
        return GREEN if grounded else AMBER
    # check / memory events
    return _hi_color(record.hi)


def _hi_bar(hi: float, width: int = 10) -> Text:
    filled = round(hi * width)
    color = _hi_color(hi)
    bar = Text()
    bar.append("█" * filled, style=color)
    bar.append("░" * (width - filled), style=DIM)
    return bar


def _sparkline(values: list[float], width: int = SPARKLINE_W) -> Text:
    blocks = " ▁▂▃▄▅▆▇█"
    if not values:
        return Text("─" * width, style=DIM)
    recent = values[-width:]
    mx = max(recent) if max(recent) > 0 else 1.0
    t = Text()
    for v in recent:
        idx = round(v / mx * (len(blocks) - 1))
        t.append(blocks[idx], style=_hi_color(v))
    pad = width - len(recent)
    return Text(" " * pad) + t


def _grade(avg_hi: float) -> tuple[str, str]:
    if avg_hi < 0.10: return "A", GREEN
    if avg_hi < 0.25: return "B", CYAN
    if avg_hi < 0.40: return "C", AMBER
    if avg_hi < 0.60: return "D", ORANGE
    return "F", RED


def _rel_time(ts: datetime) -> str:
    diff = (datetime.now(timezone.utc) - ts.replace(
        tzinfo=timezone.utc if ts.tzinfo is None else ts.tzinfo
    )).total_seconds()
    if diff < 60:   return f"{int(diff)}s ago"
    if diff < 3600: return f"{int(diff//60)}m ago"
    return f"{int(diff//3600)}h ago"


def _groundedness(state: SessionState) -> float:
    tc = state.total_claims
    return state.total_grounded / tc if tc > 0 else 0.0


# ── event block renderer (Warp-inspired) ──────────────────────────────────────

def _render_event_block(record: EventRecord) -> Text:
    """Render a single event as a Warp-style block with left-border color hint."""
    border_color = _block_border_color(record)
    hi_color = _hi_color(record.hi)

    t = Text()

    # ── line 1: type + timestamp + latency ──
    ts_str = record.ts.strftime("%H:%M:%S")
    type_colors = {"check": CYAN, "gate": AMBER, "shield": PURPLE,
                   "memory_write": GREEN, "memory_duplicate": DIM}
    type_color = type_colors.get(record.type, DIM)

    t.append("▌ ", style=f"bold {border_color}")  # Warp-style left border
    t.append(f"{record.type.upper():<7}", style=f"bold {type_color}")
    t.append(f"  {ts_str}", style=DIM)
    t.append(f"  {record.latency_ms:.0f}ms\n", style=CYAN)

    # ── line 2: HI bar + verdict ──
    t.append("▌ ", style=f"bold {border_color}")
    hi_bar = _hi_bar(record.hi, width=10)
    t.append_text(hi_bar)
    t.append(f"  {record.hi*100:.0f}%", style=f"bold {hi_color}")

    # verdict text
    if record.type == "check":
        verdict = "HALLUCINATED" if record.hi >= 0.5 else "GROUNDED"
        t.append(f"  {verdict}", style=f"bold {hi_color}")
    elif record.type == "gate":
        grounded = record.raw.get("grounded", True)
        t.append("  PASS" if grounded else "  BLOCKED", style=f"bold {'GREEN' if grounded else AMBER}")
    elif record.type == "shield":
        safe = record.raw.get("safe", True)
        t.append("  SAFE" if safe else "  INJECT!", style=f"bold {GREEN if safe else ORANGE}")
    elif record.type in ("memory_write", "memory_duplicate"):
        is_dup = record.type == "memory_duplicate"
        t.append("  DUPLICATE" if is_dup else "  STORED", style=f"{'DIM' if is_dup else f'bold {GREEN}'}")
    t.append("\n")

    # ── line 3: agent + claims summary ──
    t.append("▌ ", style=f"bold {border_color}")
    agent_short = (record.agent_id or "unknown")[:18]
    t.append(f"{agent_short}", style=DIM)
    if record.total_claims > 0:
        grnd = record.grounded
        hall = record.hallucinated
        neut = record.total_claims - grnd - hall
        t.append(f"  ·  ", style=DIM)
        t.append(f"{grnd}✓", style=GREEN)
        if neut > 0:
            t.append(f" {neut}~", style=AMBER)
        if hall > 0:
            t.append(f" {hall}✗", style=RED)
        t.append(f" / {record.total_claims} claims", style=DIM)
    t.append("\n")

    return t


# ── panel builders ────────────────────────────────────────────────────────────

def _make_header(state: SessionState, status: str, url: str, elapsed: int) -> Panel:
    hi_color = _hi_color(state.avg_hi)
    gnd_pct = _groundedness(state) * 100

    m, s = divmod(elapsed, 60)
    elapsed_str = f"{m}:{s:02d}"

    row = Text()
    row.append("▓▓ CORTEX ", style=f"bold {GREEN}")
    row.append("MONITOR  ", style=f"bold {WHITE}")
    row.append(f"{url}", style=DIM)
    row.append(f"   checks: ", style=DIM)
    row.append(f"{state.total_checks}", style=WHITE)
    row.append(f"   HI: ", style=DIM)
    row.append(f"{state.avg_hi*100:.0f}%", style=f"bold {hi_color}")
    row.append(f"   grounded: ", style=DIM)
    row.append(f"{gnd_pct:.0f}%", style=f"bold {_hi_color(1-_groundedness(state))}")
    row.append(f"   latency: ", style=DIM)
    row.append(f"{state.avg_latency:.0f}ms", style=CYAN)
    row.append(f"   {elapsed_str}", style=DIM)

    if status == "connected":
        row.append("   ● LIVE", style=f"bold {GREEN}")
    elif status == "connecting":
        row.append("   ● ...", style=AMBER)
    else:
        row.append("   ● DEAD", style=f"bold {RED}")

    return Panel(row, style=f"on {BG}", border_style=MUTED, padding=(0, 1))


def _make_feed(records: list[EventRecord]) -> Panel:
    """Warp-style event blocks feed."""
    content = Text()
    for i, r in enumerate(records):
        content.append_text(_render_event_block(r))
        # thin separator between blocks (not after last)
        if i < len(records) - 1:
            content.append("  ─────────────────────────────\n", style=f"{MUTED}")

    if not records:
        content.append("\n  waiting for events...\n", style=MUTED)

    return Panel(
        content,
        title=f"[{GREEN}]FEED[/]  [{DIM}]last {len(records)} events[/]",
        border_style=MUTED,
        style=f"on {BG}",
        padding=(0, 1),
    )


def _make_stats(state: SessionState) -> Panel:
    """Session stats panel — key metrics surfaced prominently."""
    gnd = _groundedness(state)
    gnd_color = _hi_color(1 - gnd)  # inverse: high groundedness = green

    t = Table(
        show_header=False,
        box=None,
        padding=(0, 1),
        expand=True,
    )
    t.add_column("label", style=DIM, min_width=14)
    t.add_column("value", justify="right")

    def row(label: str, val: str, color: str = WHITE):
        t.add_row(label, Text(val, style=f"bold {color}"))

    def divider():
        t.add_row(Text("─" * 13, style=MUTED), Text("─" * 7, style=MUTED))

    row("Checks",       f"{state.total_checks}")
    row("Claims",       f"{state.total_claims}")
    divider()
    row("Groundedness", f"{gnd*100:.0f}%",       gnd_color)
    row("Avg HI",       f"{state.avg_hi*100:.0f}%", _hi_color(state.avg_hi))
    divider()
    row("Avg Latency",  f"{state.avg_latency:.0f}ms",  CYAN)
    row("P95 Latency",  f"{state.p95_latency:.0f}ms",  CYAN)
    divider()
    row("Mem Writes",   f"{state.memory_write_count}",     PURPLE)
    row("Duplicates",   f"{state.memory_duplicate_count}", ORANGE if state.memory_duplicate_count > 0 else DIM)
    row("Gate Blocks",  f"{state.blocked_count}",          AMBER  if state.blocked_count > 0 else DIM)
    row("Injections",   f"{state.injection_count}",        RED    if state.injection_count > 0 else GREEN)

    return Panel(
        t,
        title=f"[{GREEN}]SESSION[/]",
        border_style=MUTED,
        style=f"on {BG}",
        padding=(0, 0),
    )


def _make_spark(state: SessionState) -> Panel:
    trend = state.hi_trend
    spark = _sparkline(trend, width=SPARKLINE_W)

    stats = Text()
    if trend:
        mn, mx = min(trend), max(trend)
        stats.append(f"  min:{mn*100:.0f}%  max:{mx*100:.0f}%", style=DIM)
    else:
        stats.append("  waiting...", style=MUTED)

    content = Text.assemble(spark, stats)
    return Panel(
        Align.left(content),
        title=f"[{GREEN}]HI TREND[/]  [{DIM}]30[/]",
        border_style=MUTED,
        style=f"on {BG}",
        padding=(0, 1),
    )


def _make_inspect(record: EventRecord | None) -> Panel:
    if record is None:
        return Panel(
            Text("  no event selected", style=MUTED),
            title=f"[{GREEN}]INSPECT[/]",
            border_style=MUTED,
            style=f"on {BG}",
            padding=(0, 1),
        )

    hi_color = _hi_color(record.hi)
    lines = Text()

    # ── event header ──
    ts_str = record.ts.strftime("%H:%M:%S")
    verdict_text = "HALLUCINATED" if record.hi >= 0.5 else "GROUNDED"
    lines.append(f"  {ts_str}  ", style=DIM)
    lines.append(f"{record.type.upper():<8}", style=CYAN)
    lines.append(f"  HI={record.hi*100:.0f}%  ", style=f"bold {hi_color}")
    lines.append(verdict_text, style=f"bold {hi_color}")
    lines.append(f"  agent={record.agent_id[:20]}  {record.latency_ms:.0f}ms\n", style=DIM)

    # ── verdict summary line (Patronus/TruLens pattern) ──
    if record.total_claims > 0:
        grnd = record.grounded
        hall = record.hallucinated
        neut = record.total_claims - grnd - hall
        gnd_pct = grnd / record.total_claims * 100
        lines.append(f"  ")
        lines.append(f"{grnd}/{record.total_claims} grounded", style=GREEN)
        lines.append("  ·  ", style=DIM)
        if neut > 0:
            lines.append(f"{neut} neutral", style=AMBER)
            lines.append("  ·  ", style=DIM)
        if hall > 0:
            lines.append(f"{hall} contradicted", style=RED)
            lines.append("  ·  ", style=DIM)
        lines.append(f"{gnd_pct:.0f}% grounded\n", style=f"bold {_hi_color(1 - gnd_pct/100)}")

    # ── response preview ──
    if record.response_preview:
        preview = record.response_preview[:110]
        lines.append(f"  ↳ \"{preview}\"\n", style=GREY)

    # ── per-claim list with confidence badges [✓ 92%] ──
    for c in record.claims[:5]:
        verdict = c.get("verdict", "")
        conf = c.get("confidence", 0.0)
        text = c.get("text", "")[:72]
        sym, v_color = _verdict_sym(verdict)
        conf_color = _conf_color(conf)

        lines.append(f"  {sym} ", style=f"bold {v_color}")
        lines.append(f"[{conf*100:.0f}%] ", style=f"{conf_color}")
        lines.append(f"{text}\n", style=GREY)

    if record.flagged_claims:
        lines.append(f"  ⚠ {len(record.flagged_claims)} flagged\n", style=f"bold {AMBER}")

    return Panel(
        lines,
        title=f"[{GREEN}]INSPECT[/]  [{DIM}]last event[/]",
        border_style=MUTED,
        style=f"on {BG}",
        padding=(0, 0),
    )


def _make_footer() -> Text:
    t = Text(justify="left")
    t.append("  Ctrl-C", style=f"bold {GREEN}")
    t.append(" quit", style=DIM)
    t.append("  ·  ", style=MUTED)
    t.append("live hallucination feed", style=MUTED)
    return t


# ── layout assembler ──────────────────────────────────────────────────────────

def build_layout(
    state: SessionState,
    feed: list[EventRecord],
    last_event: EventRecord | None,
    status: str,
    url: str,
    elapsed: int,
) -> Layout:
    root = Layout()
    root.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="inspect", size=9),
        Layout(name="footer", size=1),
    )

    root["header"].update(_make_header(state, status, url, elapsed))

    root["body"].split_row(
        Layout(name="feed", ratio=7),
        Layout(name="sidebar", ratio=3),
    )
    root["body"]["feed"].update(_make_feed(feed))

    root["body"]["sidebar"].split_column(
        Layout(name="stats", ratio=3),
        Layout(name="spark", ratio=1),
    )
    root["body"]["sidebar"]["stats"].update(_make_stats(state))
    root["body"]["sidebar"]["spark"].update(_make_spark(state))

    root["inspect"].update(_make_inspect(last_event))
    root["footer"].update(_make_footer())

    return root


# ── entry point ───────────────────────────────────────────────────────────────

class RichMonitor:
    """Rich Live dashboard — Warp-inspired block feed for hallucination monitoring."""

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.state = SessionState()
        self._stream = SSEStream(base_url, api_key)
        self._status = "connecting"
        self._feed: deque[EventRecord] = deque(maxlen=FEED_MAX)
        self._last_event: EventRecord | None = None
        self._start = datetime.now(timezone.utc)
        self._stop_event = asyncio.Event()

    def _on_event(self, data: dict) -> None:
        etype = data.get("type", "")
        if etype in ("connected", "heartbeat"):
            return
        record = EventRecord.from_sse(data)
        if record is None:
            return
        self.state.add_event(record)
        self._feed.appendleft(record)
        self._last_event = record

    def _on_connected(self) -> None:
        self._status = "connected"

    def _on_disconnected(self) -> None:
        self._status = "disconnected"

    def run(self) -> None:
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            pass

    async def _run(self) -> None:
        console = Console()
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._stop_event.set)

        self._stream.start(
            on_event=self._on_event,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
        )

        with Live(
            console=console,
            refresh_per_second=4,
            screen=True,
            transient=False,
        ) as live:
            while not self._stop_event.is_set():
                elapsed = int((datetime.now(timezone.utc) - self._start).total_seconds())
                layout = build_layout(
                    state=self.state,
                    feed=list(self._feed),
                    last_event=self._last_event,
                    status=self._status,
                    url=self.base_url,
                    elapsed=elapsed,
                )
                live.update(layout)
                await asyncio.sleep(0.25)

        await self._stream.stop()
        console.print(f"\n[{DIM}]CortexOS Monitor stopped.[/]\n")
