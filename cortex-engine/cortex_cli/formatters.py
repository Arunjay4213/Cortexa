"""Shared formatting utilities for CortexOS CLI — score bars, colors, truncation."""

from __future__ import annotations

import sys

# ── ANSI detection ───────────────────────────────────────────────

USE_COLOR = sys.stdout.isatty()

# ── Color codes ──────────────────────────────────────────────────

RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
CYAN    = "\033[36m"
MAGENTA = "\033[35m"
DIM     = "\033[2m"
BOLD    = "\033[1m"
RESET   = "\033[0m"


def c(text: str, code: str) -> str:
    """Wrap text in ANSI color if colors are enabled."""
    if not USE_COLOR:
        return str(text)
    return f"{code}{text}{RESET}"


def short_id(mid: str) -> str:
    """Truncate a UUID to 12 chars."""
    return mid[:12] if mid else "?"


def trunc(text: str, n: int = 60) -> str:
    """Truncate text, replacing newlines with spaces."""
    text = (text or "").replace("\n", " ").strip()
    return text[:n] + "..." if len(text) > n else text


def score_bar(score: float, width: int = 20) -> str:
    """Render a colored bar: green > 0.7, yellow 0.3-0.7, red < 0.3."""
    filled = max(0, min(width, int(score * width)))
    empty = width - filled
    if score >= 0.7:
        color = GREEN
    elif score >= 0.3:
        color = YELLOW
    else:
        color = RED
    return c("\u2588" * filled, color) + c("\u2591" * empty, DIM)


def halluc_bar(rate: float, width: int = 15) -> str:
    """Render hallucination rate bar: red fill on dim background."""
    filled = max(0, min(width, int(rate * width)))
    empty = width - filled
    return c("\u2588" * filled, RED) + c("\u2591" * empty, DIM)


def halluc_color(rate: float) -> str:
    """Return color code for hallucination rate."""
    if rate > 0.30:
        return RED
    elif rate > 0.0:
        return YELLOW
    return GREEN


def categorize_hallucination(claim: str) -> str:
    """Categorize a hallucinated claim by keyword matching."""
    cl = claim.lower()
    if any(w in cl for w in ("$", "dollar", "revenue", "cost", "capex", "lease", "irr", "lcoe")):
        return "Financial"
    if any(w in cl for w in ("welcome", "opportunity", "discuss", "looking forward", "call", "regards")):
        return "Conversational"
    if any(w in cl for w in ("week", "month", "day", "timeline", "deadline", "schedule")):
        return "Timeline"
    if any(w in cl for w in ("%", "percent", "average", "approximately", "estimated")):
        return "Statistical"
    return "Other"


def reason_label(reason: str) -> str:
    """Human-readable label for hallucination reason."""
    return {
        "numerical_ungrounded": "NUM_UNGROUNDED",
        "nli_empty": "NLI_EMPTY",
        "nli_low": "NLI_LOW",
    }.get(reason, reason.upper() if reason else "NLI_EMPTY")
