"""Shared formatting helpers for the CortexOS TUI."""

from __future__ import annotations


def hi_color(hi: float) -> str:
    """Return a Rich color string for an HI value."""
    if hi < 0.2:
        return "#00FF88"
    elif hi < 0.4:
        return "#AAFF00"
    elif hi < 0.6:
        return "#F5A623"
    elif hi < 0.8:
        return "#FF6600"
    return "#FF3366"


def hi_bar(hi: float) -> str:
    """6-char HI bar with color gradient based on value."""
    filled = round(hi * 6)
    empty = 6 - filled
    color = hi_color(hi)
    return f"[{color}]{'\u2588' * filled}[/{color}][dim]{'\u2591' * empty}[/dim]"


def sparkline(values: list[float]) -> str:
    """Block-char sparkline colored by HI value, last 30 values."""
    bars = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"
    result = ""
    for v in values[-30:]:
        idx = min(7, int(v * 8))
        color = hi_color(v)
        result += f"[{color}]{bars[idx]}[/{color}]"
    return result


def conf_color(conf: float) -> str:
    """Return a Rich color string for a confidence value."""
    if conf >= 0.8:
        return "#00FF88"
    elif conf >= 0.6:
        return "#F5A623"
    return "#FF3366"


def verdict_icon(verdict: str) -> tuple[str, str]:
    """Return (icon, color) for a claim verdict string."""
    v = verdict.upper()
    if v == "GROUNDED":
        return ("\u2726", "#00FF88")
    elif v == "NUM_MISMATCH":
        return ("\u25cf", "#FF3366")
    elif v == "UNSUPPORTED":
        return ("\u25cf", "#FF6600")
    elif v == "OPINION":
        return ("\u25cc", "#555555")
    return ("?", "#555555")
