"""Reusable Rich panel/card components for the Cortexa CLI."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from cx.ui.theme import CX_THEME, CYAN, score_bar


console = Console(theme=CX_THEME)


def header_panel(title: str, subtitle: str = "") -> Panel:
    """Render a branded header panel."""
    content = Text()
    content.append(title, style="cx.primary")
    if subtitle:
        content.append(f"\n{subtitle}", style="cx.dim")
    return Panel(content, border_style=CYAN, padding=(1, 2))


def score_panel(label: str, score: float, detail: str = "") -> Panel:
    """Render a health score panel with a colored bar."""
    content = Text()
    content.append(f"          {score:.0f} / 100", style="bold")
    if score >= 75:
        content.append("  ✓ Healthy\n", style="cx.success")
    elif score >= 50:
        content.append("  ⚠ Needs Attention\n", style="cx.secondary")
    else:
        content.append("  ✗ Unhealthy\n", style="cx.error")
    content.append(f"  {score_bar(score)}\n")
    if detail:
        content.append(f"\n  {detail}", style="cx.dim")
    return Panel(content, title=f"[cx.primary]{label}[/]", border_style=CYAN, padding=(1, 2))


def stat_panel(title: str, lines: list[str]) -> Panel:
    """Render a stats panel with multiple lines."""
    content = Text()
    for i, line in enumerate(lines):
        if i > 0:
            content.append("\n")
        content.append(f"  {line}")
    return Panel(content, title=f"[cx.primary]{title}[/]", border_style=CYAN, padding=(1, 2))


def memory_tree(memories: list[dict], title: str = "Memories") -> Tree:
    """Render a tree of memories with MAS badges and flags."""
    from cx.ui.theme import mas_badge, GHOST, GREEN, RED
    tree = Tree(f"[cx.primary]{title}[/]")
    for mem in memories:
        mid = mem.get("id", "???")
        content = mem.get("content", "")
        mas = mem.get("mas", 0.0)
        is_ghost = mem.get("ghost", False)
        is_contradiction = mem.get("contradiction", False)

        badge = mas_badge(mas)
        if is_ghost:
            prefix = f"[{GHOST}]👻[/]"
            style = GHOST
        elif is_contradiction:
            prefix = f"[{RED}]⚠️[/]"
            style = RED
        else:
            prefix = f"[{GREEN}]✓[/]"
            style = GREEN

        label = f"{prefix} {mid}  {badge}  [{style}]\"{content}\"[/]"
        tree.add(label)
    return tree
