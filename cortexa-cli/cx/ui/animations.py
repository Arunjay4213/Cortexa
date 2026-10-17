"""Spinners, progress bars, and transitions for the Cortexa CLI."""

from __future__ import annotations

import time

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from cx.ui.theme import CX_THEME, CYAN


console = Console(theme=CX_THEME)


def scan_progress(total: int, description: str = "Scanning") -> Progress:
    """Create a branded scan progress bar."""
    return Progress(
        SpinnerColumn("dots", style=CYAN),
        TextColumn(f"[cx.primary]{description}[/]"),
        BarColumn(bar_width=40, complete_style=CYAN, finished_style=CYAN),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def step_delay(seconds: float = 0.15) -> None:
    """Small delay between sequential panel renders for visual effect."""
    time.sleep(seconds)
