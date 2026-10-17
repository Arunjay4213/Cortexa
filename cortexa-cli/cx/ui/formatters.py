"""Cortexa TUI formatters — sleek terminal aesthetic.

All visual rendering lives here. Functions return Rich Text objects
for MessageBubble to display.
"""

from __future__ import annotations

from rich.text import Text

from cx.ui.theme import CYAN, AMBER, GREEN, RED, GHOST, DIM, WHITE, BLUE

# ── Glyphs ───────────────────────────────────────────────────────────

_DOT = "\u00b7"       # middle dot separator
_RULE = "\u2500"       # horizontal rule
_RULE_L = "\u2576"     # left cap
_RULE_R = "\u2574"     # right cap
_CHECK = "\u2713"      # checkmark
_PENDING = "\u25cc"    # dotted circle
_DIAMOND_H = "\u25c7"  # hollow diamond
_DIAMOND_F = "\u25c6"  # filled diamond
_UP = "\u25b2"         # up triangle
_DOWN = "\u25bc"       # down triangle
_LINK = "\u2194"       # left-right arrow
_BULLET = "\u25b8"     # small right triangle
_CROSS = "\u2716"      # heavy X
_WARN = "\u26a0"       # warning sign
_GHOST_ICO = "\u2620"  # skull
_SEARCH_ICO = "\u2315" # search icon (telephone recorder)
_TRACE_ICO = "\u2042"  # asterism
_GEAR = "\u2699"       # gear
_FOLDER = "\u25a3"     # square with fill
_BAR_FULL = "\u2588"   # full block
_BAR_EMPTY = "\u2591"  # light shade
_BAR_MED = "\u2593"    # dark shade
_ARROW_R = "\u2192"    # right arrow
_PIPE = "\u2502"       # vertical pipe
_CORNER_TL = "\u250c"  # top-left corner
_CORNER_BL = "\u2514"  # bottom-left corner
_TEE_L = "\u251c"      # left tee


# ── Primitives ───────────────────────────────────────────────────────


def format_divider(label: str = "", width: int = 54) -> Text:
    """Thin floating rule: ╶─ label ──────────────────╴"""
    t = Text()
    if label:
        inner = f"{_RULE} {label} "
        pad = max(2, width - len(inner) - 2)
        t.append(f"{_RULE_L}{inner}", style=DIM)
        t.append(_RULE * pad, style=DIM)
        t.append(_RULE_R, style=DIM)
    else:
        t.append(_RULE_L, style=DIM)
        t.append(_RULE * (width - 2), style=DIM)
        t.append(_RULE_R, style=DIM)
    return t


def format_progress_bar(score: float, width: int = 20) -> Text:
    """Compact bar: ████████░░░░ 82"""
    filled = int(score / 100 * width)
    empty = width - filled
    color = GREEN if score >= 75 else AMBER if score >= 40 else RED
    t = Text()
    t.append(_BAR_FULL * filled, style=color)
    t.append(_BAR_EMPTY * empty, style=DIM)
    t.append(f" {score:.0f}", style=f"bold {color}")
    return t


def _mas(t: Text, mas: float) -> None:
    """Append a bare colored MAS value."""
    color = GREEN if mas >= 0.7 else AMBER if mas >= 0.3 else RED
    t.append(f"{mas:.3f}", style=color)


def _mas_bar(t: Text, mas: float, width: int = 10) -> None:
    """Append an inline mini MAS bar: ██████░░░░ 0.82"""
    filled = int(mas * width)
    empty = width - filled
    color = GREEN if mas >= 0.7 else AMBER if mas >= 0.3 else RED
    t.append(_BAR_FULL * filled, style=color)
    t.append(_BAR_EMPTY * empty, style=f"dim {DIM}")
    t.append(f" {mas:.2f}", style=f"bold {color}")


def _dot(t: Text) -> None:
    """Append dim middle-dot separator."""
    t.append(f"  {_DOT}  ", style=DIM)


def _reason_color(reason: str) -> str:
    """Color for ghost reason badge."""
    return {"low_mas": RED, "duplicate": AMBER, "no_access": GHOST}.get(reason, DIM)


def _reason_icon(reason: str) -> str:
    """Icon for ghost reason."""
    return {"low_mas": _DOWN, "duplicate": _LINK, "no_access": _PENDING}.get(reason, _DOT)


def _age_color(days: int) -> str:
    """Color based on staleness age."""
    if days >= 90:
        return RED
    elif days >= 60:
        return AMBER
    return DIM


def _section(t: Text, icon: str, title: str, count: int | None = None,
             icon_color: str = CYAN) -> None:
    """Append a section header:  ▸ GHOSTS (12)  ──────────╴"""
    t.append(f"\n  {icon} ", style=f"bold {icon_color}")
    t.append(title.upper(), style=f"bold {WHITE}")
    if count is not None:
        t.append(f" ({count})", style=DIM)
    t.append("  ", style="")
    t.append(_RULE * 30, style=DIM)
    t.append("\n", style="")


def _verdict(score: float) -> tuple[str, str, str]:
    """Return (icon, label, color) verdict for a health score."""
    if score >= 75:
        return (_CHECK, "Healthy", GREEN)
    elif score >= 40:
        return (_WARN, "Needs Attention", AMBER)
    return (_CROSS, "Critical", RED)


def _numbered(t: Text, n: int) -> None:
    """Append a numbered prefix like  01 ▸ """
    t.append(f"  {n:>2d} ", style=DIM)
    t.append(f"{_BULLET} ", style=CYAN)


# ── Health ───────────────────────────────────────────────────────────


def format_health_summary(report) -> Text:
    """Health dashboard with verdict, progress bar, and key metrics."""
    t = Text()
    icon, label, color = _verdict(report.health_score)

    # Verdict line
    t.append(f"\n  {icon} ", style=f"bold {color}")
    t.append(label, style=f"bold {color}")
    t.append("  ", style="")
    t.append_text(format_progress_bar(report.health_score))
    t.append("\n\n", style="")

    # Key metrics in a compact grid
    t.append("    ", style="")
    t.append(f"{report.total_memories}", style=f"bold {WHITE}")
    t.append(" memories", style=DIM)
    _dot(t)
    t.append(f"{len(report.ghost_tokens)}", style=GHOST)
    t.append(f" ghosts", style=DIM)
    if report.ghost_pct > 0:
        t.append(f" ({report.ghost_pct:.1f}%)", style=GHOST)
    _dot(t)
    ct = len(report.contradictions)
    t.append(f"{ct}", style=AMBER if ct else GREEN)
    t.append(" conflicts", style=DIM)
    t.append("\n", style="")

    # Second row: MAS + staleness + cost
    t.append("    ", style="")
    t.append("avg mas  ", style=DIM)
    _mas_bar(t, report.mas_avg)
    _dot(t)
    t.append(f"{report.stale_count}", style=WHITE)
    t.append(" stale", style=DIM)
    t.append("\n", style="")

    # Cost row
    waste = report.estimated_token_waste_per_day
    if waste > 0:
        t.append("    ", style="")
        t.append(f"{_WARN} ", style=AMBER)
        t.append(f"~{waste:,} tokens/day wasted", style=RED)
        t.append("\n", style="")
    return t


# ── Audit ────────────────────────────────────────────────────────────


def format_audit_report(report) -> Text:
    """Full sectioned audit with icons, progress bars, and visual hierarchy."""
    t = Text()
    icon, label, color = _verdict(report.health_score)

    # Header: verdict + score bar + summary
    t.append(f"\n  {icon} ", style=f"bold {color}")
    t.append(label, style=f"bold {color}")
    t.append("  ", style="")
    t.append_text(format_progress_bar(report.health_score))
    t.append("\n    ", style="")
    t.append(f"{report.total_memories}", style=f"bold {WHITE}")
    t.append(" memories across ", style=DIM)
    t.append(", ".join(report.collections), style=WHITE)

    # ── Ghosts section ──
    _section(t, _GHOST_ICO, "ghosts", len(report.ghost_tokens), GHOST)
    if not report.ghost_tokens:
        t.append("    None found\n", style=f"italic {DIM}")
    for g in report.ghost_tokens[:10]:
        t.append("    ", style="")
        t.append(f"{_reason_icon(g.reason)} ", style=_reason_color(g.reason))
        t.append(f"{g.reason:<10s}", style=_reason_color(g.reason))
        t.append(f"  {g.memory_id}", style=f"bold {CYAN}")
        t.append("  ", style="")
        _mas_bar(t, g.mas_score, width=8)
        snippet = g.content[:35] + (".." if len(g.content) > 35 else "")
        t.append(f'\n         "{snippet}"\n', style=DIM)
    if len(report.ghost_tokens) > 10:
        t.append(f"    {_DOT}{_DOT}{_DOT} +{len(report.ghost_tokens) - 10} more\n", style=DIM)

    # ── Contradictions section ──
    _section(t, _LINK, "contradictions", len(report.contradictions), AMBER)
    if not report.contradictions:
        t.append("    None found\n", style=f"italic {DIM}")
    for c in report.contradictions:
        t.append("    ", style="")
        t.append(f"{c.memory_a_id}", style=f"bold {CYAN}")
        t.append(f" {_LINK} ", style=AMBER)
        t.append(f"{c.memory_b_id}", style=f"bold {CYAN}")
        t.append(f"\n      {c.explanation}\n", style=WHITE)

    # ── Distribution section ──
    _section(t, _UP, "distribution", icon_color=GREEN)
    t.append("    ", style="")
    t.append(f"{_UP} ", style=GREEN)
    t.append("high ", style=DIM)
    t.append(f"{report.mas_high_count}", style=f"bold {GREEN}")
    t.append("    ", style="")
    t.append(f"{_DOT} ", style=AMBER)
    t.append("mid  ", style=DIM)
    t.append(f"{report.mas_mid_count}", style=f"bold {AMBER}")
    t.append("    ", style="")
    t.append(f"{_DOWN} ", style=RED)
    t.append("low  ", style=DIM)
    t.append(f"{report.mas_low_count}", style=f"bold {RED}")
    t.append("\n    avg mas  ", style=DIM)
    _mas_bar(t, report.mas_avg)
    t.append("\n", style="")

    # ── Staleness section ──
    _section(t, _PENDING, "staleness", icon_color=AMBER)
    t.append("    ", style="")
    t.append(f"stale (>{report.stale_days_threshold}d): ", style=DIM)
    t.append(f"{report.stale_count}", style=f"bold {WHITE}")
    _dot(t)
    t.append("no provenance: ", style=DIM)
    t.append(f"{report.no_provenance_count}", style=f"bold {WHITE}")
    _dot(t)
    t.append("outdated source: ", style=DIM)
    t.append(f"{report.source_outdated_count}", style=f"bold {WHITE}")
    t.append("\n", style="")

    # ── Cost section ──
    _section(t, _WARN, "cost", icon_color=RED)
    waste = report.estimated_token_waste_per_day
    if waste > 0:
        t.append("    ", style="")
        t.append(f"~{waste:,} tokens/day", style=f"bold {RED}")
        _dot(t)
        t.append(f"~${report.estimated_cost_waste_per_day:.2f}/day", style=RED)
    else:
        t.append("    ", style="")
        t.append(f"{_CHECK} no waste detected", style=GREEN)
    t.append("\n", style="")
    return t


# ── Memory Card ──────────────────────────────────────────────────────


def format_memory_card(mem, compact: bool = False) -> Text:
    """Single memory with structured sections and MAS bar."""
    t = Text()

    # Header: ID + collection + MAS bar
    t.append(f"  {_DIAMOND_F} ", style=f"bold {CYAN}")
    t.append(f"{mem.id}", style=f"bold {CYAN}")
    t.append(f"  [{mem.collection}]", style=DIM)
    t.append("  ", style="")
    _mas_bar(t, mem.mas_score or 0)
    t.append("\n", style="")

    if compact:
        t.append(f"    {mem.content[:80]}", style=WHITE)
        return t

    # Content section
    t.append(f"  {_PIPE}\n", style=DIM)
    t.append(f"  {_PIPE}  ", style=DIM)
    # Word-wrap content at ~65 chars per line
    content = mem.content
    while len(content) > 65:
        brk = content[:65].rfind(" ")
        if brk == -1:
            brk = 65
        t.append(f"{content[:brk]}\n", style=WHITE)
        content = content[brk:].lstrip()
        if content:
            t.append(f"  {_PIPE}  ", style=DIM)
    if content:
        t.append(f"{content}\n", style=WHITE)
    t.append(f"  {_PIPE}\n", style=DIM)

    # Metadata section
    t.append(f"  {_CORNER_BL}{_RULE} ", style=DIM)
    t.append("source ", style=DIM)
    t.append(f"{mem.source or 'unknown'}", style=WHITE)
    _dot(t)
    t.append("created ", style=DIM)
    t.append(f"{mem.created_at or 'unknown'}", style=WHITE)
    _dot(t)
    t.append("accessed ", style=DIM)
    t.append(f"{mem.access_count}x", style=f"bold {WHITE}")
    t.append("\n", style="")

    t.append(f"    last ", style=DIM)
    t.append(f"{mem.last_accessed or 'unknown'}", style=WHITE)

    # Flags
    ghost = mem.metadata.get("ghost", False)
    contradiction = mem.metadata.get("contradiction", False)
    if ghost or contradiction:
        t.append("\n    ", style="")
        if ghost:
            t.append(f"{_GHOST_ICO} ghost", style=f"bold {GHOST}")
        if ghost and contradiction:
            t.append("  ", style="")
        if contradiction:
            t.append(f"{_LINK} conflict", style=f"bold {AMBER}")

    # MAS trend
    if mem.mas_history:
        history = mem.mas_history[-5:]
        t.append(f"\n    mas trend  ", style=DIM)
        for i, val in enumerate(history):
            color = GREEN if val >= 0.7 else AMBER if val >= 0.3 else RED
            t.append(f"{val:.2f}", style=color)
            if i < len(history) - 1:
                # Show direction arrow
                nxt = history[i + 1]
                if nxt > val:
                    t.append(f" {_UP} ", style=GREEN)
                elif nxt < val:
                    t.append(f" {_DOWN} ", style=RED)
                else:
                    t.append(f" {_ARROW_R} ", style=DIM)
    return t


# ── Ghost Tokens ─────────────────────────────────────────────────────


def format_ghost_list(ghosts: list) -> Text:
    """Ghost list with inline MAS bars and reason icons."""
    t = Text()

    # Header
    t.append(f"\n  {_GHOST_ICO} ", style=f"bold {GHOST}")
    t.append("ghosts", style=f"bold {WHITE}")
    t.append(f"  {len(ghosts)} found\n", style=DIM)
    t.append(f"  {_RULE * 48}\n", style=DIM)

    # Column header
    t.append("    ", style="")
    t.append(f"{'ID':<12s}", style=f"bold {DIM}")
    t.append(f"{'Reason':<12s}", style=f"bold {DIM}")
    t.append(f"{'MAS':<18s}", style=f"bold {DIM}")
    t.append("Content\n", style=f"bold {DIM}")
    t.append(f"  {_RULE * 48}\n", style=DIM)

    for g in ghosts:
        snippet = g.content[:30] + (".." if len(g.content) > 30 else "")
        t.append("    ", style="")
        t.append(f"{g.memory_id:<12s}", style=f"bold {CYAN}")
        t.append(f"{_reason_icon(g.reason)} ", style=_reason_color(g.reason))
        t.append(f"{g.reason:<10s}", style=_reason_color(g.reason))
        t.append(" ", style="")
        _mas_bar(t, g.mas_score, width=8)
        t.append(f'  "{snippet}"', style=DIM)
        t.append("\n", style="")

    t.append(f"  {_RULE * 48}\n", style=DIM)
    return t


# ── Contradictions ───────────────────────────────────────────────────


def format_contradiction(c: dict) -> Text:
    """Single contradiction pair."""
    t = Text()
    t.append("    ", style="")
    t.append(f"{c['memory_a']['id']}", style=f"bold {CYAN}")
    t.append(f" {_LINK} ", style=AMBER)
    t.append(f"{c['memory_b']['id']}\n", style=f"bold {CYAN}")
    t.append(f"      A: {c['memory_a']['content'][:55]}\n", style=DIM)
    t.append(f"      B: {c['memory_b']['content'][:55]}\n", style=DIM)
    t.append("      ", style="")
    t.append(f"{c['explanation']}", style=AMBER)
    return t


def format_contradictions(contradictions: list) -> Text:
    """Contradiction list with side-by-side conflict display."""
    t = Text()

    # Header
    t.append(f"\n  {_LINK} ", style=f"bold {AMBER}")
    t.append("contradictions", style=f"bold {WHITE}")
    t.append(f"  {len(contradictions)} found\n", style=DIM)
    t.append(f"  {_RULE * 48}\n\n", style=DIM)

    for i, c in enumerate(contradictions):
        t.append(f"  {i + 1:>2d}. ", style=DIM)
        t.append(f"{c['memory_a']['id']}", style=f"bold {CYAN}")
        t.append(f" {_LINK} ", style=AMBER)
        t.append(f"{c['memory_b']['id']}\n", style=f"bold {CYAN}")

        # Show content from both sides
        a_content = c["memory_a"].get("content", "")
        b_content = c["memory_b"].get("content", "")
        if a_content:
            t.append(f"      A: ", style=f"bold {DIM}")
            t.append(f"{a_content[:55]}\n", style=WHITE)
        if b_content:
            t.append(f"      B: ", style=f"bold {DIM}")
            t.append(f"{b_content[:55]}\n", style=WHITE)

        t.append(f"      {_WARN} ", style=AMBER)
        t.append(f"{c['explanation']}\n\n", style=AMBER)

    return t


# ── Search & Trace ───────────────────────────────────────────────────


def format_search_results(results: list, query: str) -> Text:
    """Numbered search results with inline MAS bars."""
    t = Text()

    # Header
    t.append(f"\n  {_SEARCH_ICO} ", style=f"bold {BLUE}")
    t.append("search", style=f"bold {WHITE}")
    t.append(f"  '{query}'", style=CYAN)
    _dot(t)
    t.append(f"{len(results)} found\n", style=WHITE)
    t.append(f"  {_RULE * 48}\n\n", style=DIM)

    for i, m in enumerate(results[:15], 1):
        _numbered(t, i)
        t.append(f"{m.id}", style=f"bold {CYAN}")
        t.append(f"  [{m.collection}]", style=DIM)
        t.append("  ", style="")
        _mas_bar(t, m.mas_score or 0, width=8)
        t.append(f"\n       {m.content[:65]}\n", style=WHITE)

    if len(results) > 15:
        t.append(f"\n    {_DOT}{_DOT}{_DOT} +{len(results) - 15} more", style=DIM)
    return t


def format_trace_results(matches: list, query: str) -> Text:
    """Numbered trace results with source attribution."""
    t = Text()

    # Header
    t.append(f"\n  {_TRACE_ICO} ", style=f"bold {BLUE}")
    t.append("trace", style=f"bold {WHITE}")
    t.append(f"  '{query}'", style=CYAN)
    _dot(t)
    t.append(f"{len(matches)} attributed\n", style=WHITE)
    t.append(f"  {_RULE * 48}\n\n", style=DIM)

    for i, m in enumerate(matches[:10], 1):
        _numbered(t, i)
        t.append(f"{m.id}", style=f"bold {CYAN}")
        t.append(f"  [{m.collection}]", style=DIM)
        t.append("  ", style="")
        _mas_bar(t, m.mas_score or 0, width=8)
        t.append(f"\n       {m.content[:65]}\n", style=WHITE)
        t.append(f"       {_ARROW_R} source ", style=DIM)
        t.append(f"{m.source or 'unknown'}", style=WHITE)
        _dot(t)
        t.append(f"{m.access_count}x accessed\n", style=DIM)

    if len(matches) > 10:
        t.append(f"\n    {_DOT}{_DOT}{_DOT} +{len(matches) - 10} more", style=DIM)
    return t


# ── Watch Events ─────────────────────────────────────────────────────


def format_watch_event(etype: str, mem, ts: str, details: dict | None = None) -> Text:
    """Single-line watch event."""
    t = Text()
    t.append(f"  {ts}  ", style=DIM)

    if etype == "access":
        t.append(f"{_DIAMOND_H} access  ", style=CYAN)
        t.append(f"{mem.id}", style=f"bold {CYAN}")
        snippet = mem.content[:38] + (".." if len(mem.content) > 38 else "")
        t.append(f'  "{snippet}"', style=DIM)

    elif etype == "mas_update":
        delta = details.get("delta", 0) if details else 0
        old_mas = details.get("old_mas", 0) if details else 0
        new_mas = details.get("new_mas", 0) if details else 0
        arrow = _UP if delta > 0 else _DOWN
        color = GREEN if delta > 0 else RED
        t.append(f"{arrow} mas     ", style=color)
        t.append(f"{mem.id}", style=f"bold {CYAN}")
        t.append(f"  {old_mas:.3f} ", style=DIM)
        t.append(_ARROW_R, style=DIM)
        t.append(f" {new_mas:.3f}", style=color)

    elif etype == "query_hit":
        t.append(f"{_DIAMOND_F} query   ", style=BLUE)
        t.append(f"{mem.id}", style=f"bold {CYAN}")
        t.append("  matched", style=DIM)
        t.append("  ", style="")
        _mas_bar(t, mem.mas_score or 0, width=8)

    else:
        t.append(f"{_BULLET} {etype:<8s}", style=WHITE)
        t.append(f"{mem.id}", style=f"bold {CYAN}")

    return t


# ── Help & Config ────────────────────────────────────────────────────


# Command categories for visual grouping
_HELP_CATEGORIES = {
    "Discovery": ["/search", "/trace"],
    "Health": ["/health", "/audit"],
    "Memory": ["/memory", "/ghosts", "/contradictions", "/stale"],
    "Actions": ["/fix", "/export", "/watch"],
    "System": ["/config", "/help", "/clear"],
}


def format_help(commands: dict) -> Text:
    """Categorized command list with section headers."""
    t = Text()
    t.append("\n", style="")

    for category, cmds in _HELP_CATEGORIES.items():
        # Category header
        t.append(f"  {_BULLET} ", style=CYAN)
        t.append(f"{category}\n", style=f"bold {WHITE}")

        for cmd in cmds:
            desc = commands.get(cmd, "")
            if desc:
                t.append(f"      {cmd:<18s}", style=f"bold {CYAN}")
                t.append(f" {desc}\n", style=DIM)

        t.append("\n", style="")

    # Show any uncategorized commands
    categorized = {c for group in _HELP_CATEGORIES.values() for c in group}
    extras = {k: v for k, v in commands.items() if k not in categorized}
    if extras:
        for cmd, desc in extras.items():
            t.append(f"      {cmd:<18s}", style=f"bold {CYAN}")
            t.append(f" {desc}\n", style=DIM)
        t.append("\n", style="")

    t.append(f"    or just type naturally\n", style=f"italic {DIM}")
    return t


def format_config(cfg) -> Text:
    """Configuration display with dotted leaders."""
    t = Text()
    pairs = [
        ("adapter", cfg.adapter),
        ("cortex url", cfg.cortex_url),
        ("ghost threshold", str(cfg.ghost_threshold)),
        ("stale days", str(cfg.stale_days)),
        ("telemetry", str(cfg.telemetry)),
    ]

    t.append(f"\n  {_GEAR} ", style=f"bold {CYAN}")
    t.append("Configuration\n", style=f"bold {WHITE}")
    t.append(f"  {_RULE * 36}\n", style=DIM)

    for label, value in pairs:
        # Dotted leader: label .......... value
        leader_len = max(2, 28 - len(label))
        leader = _DOT * leader_len
        t.append(f"    {label} ", style=DIM)
        t.append(f"{leader} ", style=f"dim {DIM}")
        t.append(f"{value}\n", style=f"bold {WHITE}")

    t.append(f"  {_RULE * 36}\n", style=DIM)
    return t


# ── Action Prompt ────────────────────────────────────────────────────


def format_action_prompt(mem, action: str) -> Text:
    """Confirmation prompt for memory actions with clear layout."""
    t = Text()

    # Action header
    t.append(f"\n  {_WARN} ", style=AMBER)
    t.append(f"{action.upper()}", style=f"bold {AMBER}")
    t.append(f"  {mem.id}", style=f"bold {CYAN}")
    t.append("  ", style="")
    _mas_bar(t, mem.mas_score or 0, width=8)
    t.append("\n", style="")

    # Content preview
    content = mem.content[:65] + (".." if len(mem.content) > 65 else "")
    t.append(f"  {_PIPE}\n", style=DIM)
    t.append(f'  {_PIPE}  "{content}"\n', style=DIM)
    t.append(f"  {_PIPE}\n", style=DIM)

    # Confirm/cancel buttons
    t.append("  ", style="")
    t.append(f"  [{_CHECK}] ", style=f"bold {GREEN}")
    t.append("confirm (y)", style=DIM)
    t.append("    ", style="")
    t.append(f"  [{_CROSS}] ", style=f"bold {RED}")
    t.append("cancel (n)", style=DIM)
    t.append("\n", style="")
    return t


# ── Startup Steps ────────────────────────────────────────────────────


def format_startup_step(label: str, status: str = "pending", detail: str = "") -> Text:
    """Startup step: pending dot or green checkmark."""
    t = Text()
    if status == "pending":
        t.append(f"  {_PENDING} ", style=DIM)
        t.append(label, style=DIM)
    elif status == "done":
        t.append(f"  {_CHECK} ", style=GREEN)
        t.append(label, style=WHITE)
        if detail:
            t.append(f" \u2014 {detail}", style=DIM)
    return t


# ── Stale List ───────────────────────────────────────────────────────


def format_stale_list(stale: list[tuple]) -> Text:
    """Stale memories with age-colored indicators and MAS bars."""
    t = Text()

    # Header
    t.append(f"\n  {_PENDING} ", style=f"bold {AMBER}")
    t.append("Stale", style=f"bold {WHITE}")
    t.append(f"  {len(stale)} found\n", style=DIM)
    t.append(f"  {_RULE * 48}\n\n", style=DIM)

    for i, (m, days) in enumerate(stale[:20], 1):
        age_col = _age_color(days)
        _numbered(t, i)
        t.append(f"{m.id}", style=f"bold {CYAN}")
        t.append(f"  {days:>3d}d", style=f"bold {age_col}")
        t.append("  ", style="")
        _mas_bar(t, m.mas_score or 0, width=8)
        snippet = m.content[:35] + (".." if len(m.content) > 35 else "")
        t.append(f'\n       "{snippet}"\n', style=DIM)

    if len(stale) > 20:
        t.append(f"\n    {_DOT}{_DOT}{_DOT} +{len(stale) - 20} more", style=DIM)
    return t
