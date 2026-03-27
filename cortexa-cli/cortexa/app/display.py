"""Rich rendering for the cx CLI.

All terminal output goes through here — spinners, trees, health bars,
banners, and styled text. Progressive reveal with animations.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Generator

from rich.console import Console
from rich.live import Live
from rich.progress import BarColumn, Progress, TextColumn
from rich.spinner import Spinner
from rich.style import Style
from rich.text import Text
from rich.theme import Theme
from rich.tree import Tree

__version__ = "0.1.0"

# ── Brand Colors ─────────────────────────────────────────────────────
LIME = "#C6E227"
RED = "#f87171"
PURPLE = "#BF5AF2"
ORANGE = "#FF9F0A"
GREEN = "#6ee7b7"
AMBER = "#fbbf24"
BG = "#0f0e0d"
TEXT = "#f0ede8"
DIM = "#6b6b6b"

CORTEXA_THEME = Theme(
    {
        "brand": Style(color=LIME, bold=True),
        "success": Style(color=GREEN),
        "error": Style(color=RED),
        "ghost": Style(color=PURPLE),
        "stale": Style(color=AMBER),
        "contradiction": Style(color=ORANGE),
        "dim": Style(color=DIM),
        "score.good": Style(color=GREEN, bold=True),
        "score.warn": Style(color=AMBER, bold=True),
        "score.bad": Style(color=RED, bold=True),
    }
)

console = Console(theme=CORTEXA_THEME)

# ── Progressive Reveal ────────────────────────────────────────────────

_REVEAL_DELAY = 0.06  # seconds between progressive reveal steps

def _reveal_pause() -> None:
    """Brief pause for progressive reveal effect."""
    time.sleep(_REVEAL_DELAY)


# ── Banner ───────────────────────────────────────────────────────────

def banner() -> None:
    """Print the cortexa banner line."""
    console.print(
        Text.assemble(
            ("◆ ", Style(color=LIME, bold=True)),
            ("cortexa", Style(color=TEXT, bold=True)),
            (f" v{__version__}", Style(color=DIM)),
        )
    )
    console.print()


# ── Spinners ─────────────────────────────────────────────────────────

@contextmanager
def spinner(message: str) -> Generator[Live, None, None]:
    """Show an animated spinner with a message. Yields the Live instance."""
    sp = Spinner("dots", text=Text(f" {message}", style=Style(color=LIME)))
    with Live(sp, console=console, refresh_per_second=12, transient=True) as live:
        yield live


# ── Score Formatting ─────────────────────────────────────────────────

def score_style(score: float) -> str:
    """Return the style name for a health score."""
    if score >= 80:
        return "score.good"
    elif score >= 50:
        return "score.warn"
    return "score.bad"


def format_score(score: float) -> Text:
    """Format a health score with color."""
    style = score_style(score)
    return Text(f"{score:.0f}/100", style=style)


# ── Health Bar ───────────────────────────────────────────────────────

def health_bar(score: float, label: str = "Memory Health", animate: bool = True) -> None:
    """Render a health bar, animating from 0 → final value."""
    style = score_style(score)
    bar_color = GREEN if score >= 80 else (AMBER if score >= 50 else RED)

    progress = Progress(
        TextColumn(f"  {label}"),
        BarColumn(bar_width=30, complete_style=Style(color=bar_color), finished_style=Style(color=bar_color)),
        TextColumn("[{task.percentage:.0f}%]", style=style),
        console=console,
        transient=False,
    )
    with progress:
        task = progress.add_task("health", total=100)
        if animate and score > 0:
            steps = 25
            for i in range(1, steps + 1):
                progress.update(task, completed=score * i / steps)
                time.sleep(0.02)
        progress.update(task, completed=score)


# ── Trace Results ────────────────────────────────────────────────────

def trace_header(query: str, response: str) -> None:
    """Print trace query/response header with progressive reveal."""
    _reveal_pause()
    console.print(f"  [dim]query:[/dim] {query}")
    _reveal_pause()
    console.print(f"  [dim]response:[/dim] {response}")
    console.print()


def claim_tree(claims: list, attributions: list) -> None:
    """Render claims and their attributions as a Rich Tree with progressive reveal."""
    # Build attribution lookup: claim_id -> list of attributions
    attr_map: dict[str, list] = {}
    for a in attributions:
        attr_map.setdefault(a.claim_id, []).append(a)

    console.print("[brand]Claims[/brand]")
    for claim in claims:
        _reveal_pause()
        tree = Tree(f"[bold]{claim.text}[/bold]", guide_style="dim")
        claim_attrs = attr_map.get(claim.id, [])
        for attr in claim_attrs:
            mas = attr.mas_score
            ctype = attr.contribution_type
            ms = _mas_style(mas)
            bar = _mas_bar(mas)
            cs = _contribution_style(ctype)
            tree.add(f"[{cs}]{attr.memory_id}[/{cs}]  [{ms}]{bar} {mas:.2f}[/{ms}]  [{cs}]{ctype}[/{cs}]")
        console.print(tree)

    console.print()


def _contribution_style(ctype: str) -> str:
    """Map contribution type to style name."""
    return {
        "supporting": "success",
        "contradicting": "contradiction",
        "ghost": "ghost",
        "neutral": "dim",
    }.get(ctype, "dim")


def _mas_style(mas: float) -> str:
    """Color style for a MAS score: green >0.5, amber 0.2-0.5, dim <0.2."""
    if mas > 0.5:
        return "success"
    elif mas >= 0.2:
        return "stale"
    return "dim"


def _mas_bar(mas: float, width: int = 8) -> str:
    """Render a mini visual bar for a MAS score."""
    filled = round(mas * width)
    return "━" * filled + "╸" + "─" * max(0, width - filled - 1)


def issues_section(ghost_tokens: list, contradictions: list, stale_memories: list) -> None:
    """Print issues found with progressive reveal."""
    if not ghost_tokens and not contradictions and not stale_memories:
        _reveal_pause()
        console.print("  [success]✓ No issues found[/success]")
        console.print()
        return

    if ghost_tokens:
        _reveal_pause()
        console.print(f"  [ghost]GHOST Ghost Tokens ({len(ghost_tokens)})[/ghost]")
        for g in ghost_tokens:
            _reveal_pause()
            console.print(f"    [ghost]{g.memory_id}[/ghost] — [dim]{g.reason}[/dim]  (~{g.waste_tokens} tokens wasted)")
        console.print()

    if contradictions:
        _reveal_pause()
        console.print(f"  [contradiction]CONFLICT Contradictions ({len(contradictions)})[/contradiction]")
        for c in contradictions:
            _reveal_pause()
            console.print(f"    [contradiction]{c.memory_id_1} ↔ {c.memory_id_2}[/contradiction] — [dim]{c.explanation}[/dim]")
        console.print()

    if stale_memories:
        _reveal_pause()
        console.print(f"  [stale]STALE Stale Memories ({len(stale_memories)})[/stale]")
        for s in stale_memories:
            _reveal_pause()
            console.print(f"    [stale]{s.memory_id}[/stale] — [dim]{s.reason}[/dim]  ({s.days_since_update}d old)")
        console.print()


# ── Audit Results ────────────────────────────────────────────────────

def audit_summary(result) -> None:
    """Render full audit results with progressive reveal."""
    console.print(f"  [bold]Memories scanned:[/bold] {result.total_memories}")
    health_bar(result.health_score)
    console.print()

    # Stats — progressive reveal
    if result.ghost_count > 0:
        _reveal_pause()
        console.print(f"  [ghost]GHOST Ghosts:[/ghost] {result.ghost_count} ({result.ghost_percentage:.0f}%)")
    if result.contradiction_count > 0:
        _reveal_pause()
        console.print(f"  [contradiction]CONFLICT Contradictions:[/contradiction] {result.contradiction_count}")
    if result.stale_count > 0:
        _reveal_pause()
        console.print(f"  [stale]STALE Stale:[/stale] {result.stale_count}")
    if result.estimated_waste_tokens > 0:
        _reveal_pause()
        console.print(f"  [dim]Wasted tokens:[/dim] ~{result.estimated_waste_tokens:,}")
        if result.estimated_waste_cost_monthly > 0:
            console.print(f"  [dim]Est. monthly waste:[/dim] ${result.estimated_waste_cost_monthly:.2f}")
    console.print()

    # Detailed issues
    issues_section([], result.contradictions, result.stale_memories)

    # Recommendations
    if result.recommendations:
        _reveal_pause()
        console.print("  [brand]Recommendations[/brand]")
        for rec in result.recommendations:
            _reveal_pause()
            console.print(f"    → {rec}")
        console.print()


# ── Gate Results ─────────────────────────────────────────────────────

def gate_result(result) -> None:
    """Render gate/shield results."""
    if result.safe_to_generate:
        console.print("  [success]✓ Safe to generate[/success]")
    else:
        console.print("  [error]✗ Risk detected[/error]")
    console.print(f"  [dim]{result.risk_summary}[/dim]")
    console.print(f"  [dim]Memories scored:[/dim] {result.memories_scored}")
    console.print()

    if result.high_risk:
        console.print(f"  [error]High-risk memories:[/error] {', '.join(result.high_risk)}")
        console.print()

    issues_section([], result.contradictions, result.stale)


# ── Watch / Live Events ─────────────────────────────────────────────

def watch_event(event: dict) -> None:
    """Render a single watch event line with colored left border."""
    etype = event.get("type", "info")
    ts = event.get("timestamp", "")
    msg = event.get("message", "")

    style_map = {
        "trace": "brand",
        "ghost": "ghost",
        "contradiction": "contradiction",
        "stale": "stale",
        "health": "success",
        "error": "error",
    }
    style = style_map.get(etype, "dim")
    prefix = {
        "trace": "→",
        "ghost": "GHOST",
        "contradiction": "CONFLICT",
        "stale": "STALE",
        "health": "✓",
        "error": "✗",
    }.get(etype, "·")

    console.print(f"  [{style}]│[/{style}] [dim]{ts}[/dim]  [{style}]{prefix} {msg}[/{style}]")


# ── Verdict ──────────────────────────────────────────────────────────

def verdict_line(health_score: float, ghost_count: int, contradiction_count: int, stale_count: int) -> None:
    """Print a one-line verdict summary at end of trace."""
    _reveal_pause()
    issues = []
    if ghost_count:
        issues.append(f"{ghost_count} ghost{'s' if ghost_count != 1 else ''}")
    if contradiction_count:
        issues.append(f"{contradiction_count} conflict{'s' if contradiction_count != 1 else ''}")
    if stale_count:
        issues.append(f"{stale_count} stale")

    if health_score >= 80 and not issues:
        console.print(f"  [success]VERDICT  Clean — {health_score:.0f}% health, no issues[/success]")
    elif health_score >= 50:
        issue_str = ", ".join(issues) if issues else "minor concerns"
        console.print(f"  [stale]VERDICT  Caution — {health_score:.0f}% health, {issue_str}[/stale]")
    else:
        issue_str = ", ".join(issues) if issues else "low confidence"
        console.print(f"  [error]VERDICT  Risk — {health_score:.0f}% health, {issue_str}[/error]")
    console.print()


# ── Diff / Fix ──────────────────────────────────────────────────────

def diff_view(memory_id: str, old_content: str, current_content: str, source: str, days_old: int) -> None:
    """Render a diff between stale memory content and current source."""
    console.print(f"  [bold]{memory_id}[/bold]  [dim]source: {source}[/dim]  [stale]{days_old}d old[/stale]")
    console.print()
    _reveal_pause()
    console.print(f"  [error]- {old_content}[/error]")
    _reveal_pause()
    console.print(f"  [success]+ {current_content}[/success]")
    console.print()


def fix_proposal(memory_id: str, old_content: str, proposed: str) -> None:
    """Show a fix proposal for a stale memory."""
    console.print(f"  [bold]Proposed fix for {memory_id}[/bold]")
    console.print()
    _reveal_pause()
    console.print(f"  [error]  old:[/error] {old_content}")
    _reveal_pause()
    console.print(f"  [success]  new:[/success] {proposed}")
    console.print()


def report_md(result) -> str:
    """Format an audit result as Markdown."""
    lines = [
        "# Cortexa Memory Health Report",
        "",
        f"**Health Score:** {result.health_score:.0f}/100",
        f"**Memories Scanned:** {result.total_memories}",
        "",
    ]
    if result.ghost_count:
        lines.append(f"## Ghosts ({result.ghost_count})")
        lines.append(f"{result.ghost_percentage:.0f}% of memories are ghosts.")
        lines.append("")
    if result.contradiction_count:
        lines.append(f"## Contradictions ({result.contradiction_count})")
        for c in result.contradictions:
            lines.append(f"- {c.memory_id_1} vs {c.memory_id_2}: {c.explanation}")
        lines.append("")
    if result.stale_count:
        lines.append(f"## Stale Memories ({result.stale_count})")
        for s in result.stale_memories:
            lines.append(f"- {s.memory_id}: {s.reason} ({s.days_since_update}d old)")
        lines.append("")
    if result.estimated_waste_tokens:
        lines.append(f"**Wasted Tokens:** ~{result.estimated_waste_tokens:,}")
        if result.estimated_waste_cost_monthly:
            lines.append(f"**Est. Monthly Waste:** ${result.estimated_waste_cost_monthly:.2f}")
        lines.append("")
    if result.recommendations:
        lines.append("## Recommendations")
        for rec in result.recommendations:
            lines.append(f"- {rec}")
        lines.append("")
    return "\n".join(lines)


def init_success(config_path: str) -> None:
    """Print init success message."""
    console.print()
    success(f"Config saved to {config_path}")
    dim("Run `cx health --demo` to verify setup.")
    console.print()


# ── Chat ─────────────────────────────────────────────────────────────

def chat_prompt() -> str | None:
    """Read a line of input. Returns None on EOF."""
    try:
        return console.input("[brand]cx>[/brand] ")
    except (EOFError, KeyboardInterrupt):
        return None


def chat_response(text: str) -> None:
    """Print a chat response."""
    console.print(f"  {text}")
    console.print()


def chat_tool_call(name: str, args: str = "") -> None:
    """Print a tool call indicator."""
    console.print(f"  [dim]:: {name}[/dim] {args}")


# ── Utility ──────────────────────────────────────────────────────────

def error(msg: str) -> None:
    """Print an error message."""
    console.print(f"  [error]✗ {msg}[/error]")


def success(msg: str) -> None:
    """Print a success message."""
    console.print(f"  [success]✓ {msg}[/success]")


def dim(msg: str) -> None:
    """Print a dim informational message."""
    console.print(f"  [dim]{msg}[/dim]")
