"""Color palette, styles, and branding for the Cortexa CLI.

Single source of truth for all colors. Values match theme.tcss exactly.
"""

from rich.style import Style
from rich.theme import Theme

# ── Brand colors (synced with theme.tcss) ─────────────────────────────
CYAN = "#00D4E8"       # Primary accent — brand, interactive
AMBER = "#E8A800"      # Warning — attention, contradictions
GREEN = "#00E87A"      # Success — healthy state, confirmations
RED = "#E83050"        # Error — failures, critical
GHOST = "#4A4A6A"      # Ghost tokens — muted chrome
DIM = "#555570"        # De-emphasized text
WHITE = "#E4E4EF"      # Primary text
BLUE = "#57C7FF"       # Info / links
SURFACE = "#12121A"    # Surface background
BG = "#0A0A0F"         # Deep background

# ── Named styles ──────────────────────────────────────────────────────
STYLES = {
    "cx.primary": Style(color=CYAN, bold=True),
    "cx.secondary": Style(color=AMBER),
    "cx.success": Style(color=GREEN),
    "cx.error": Style(color=RED, bold=True),
    "cx.ghost": Style(color=GHOST, italic=True),
    "cx.dim": Style(color=DIM),
    "cx.info": Style(color=BLUE),
    "cx.score.high": Style(color=GREEN, bold=True),
    "cx.score.mid": Style(color=AMBER, bold=True),
    "cx.score.low": Style(color=RED, bold=True),
    "cx.label": Style(color=WHITE, bold=True),
    "cx.value": Style(color=WHITE),
    "cx.panel.border": Style(color=CYAN),
}

CX_THEME = Theme(STYLES)


# ── ASCII banner ──────────────────────────────────────────────────────
BANNER = f"""[{CYAN}]
   ██████╗ ██╗  ██╗
  ██╔════╝ ╚██╗██╔╝
  ██║       ╚███╔╝    [bold]Cortexa[/bold] v{{ver}}
  ██║       ██╔██╗    Memory intelligence for AI agents
   ██████╗ ██╔╝ ██╗
   ╚═════╝ ╚═╝  ╚═╝[/]
"""


def get_banner() -> str:
    from cx import __version__
    return BANNER.format(ver=__version__)


def score_style(score: float) -> str:
    """Return the style name for a 0-1 score."""
    if score >= 0.75:
        return "cx.score.high"
    elif score >= 0.25:
        return "cx.score.mid"
    return "cx.score.low"


def score_bar(score: float, width: int = 30) -> str:
    """Render a colored progress bar string for a 0-100 score."""
    filled = int(score / 100 * width)
    empty = width - filled
    if score >= 75:
        color = GREEN
    elif score >= 25:
        color = AMBER
    else:
        color = RED
    return f"[{color}]{'█' * filled}[/][{DIM}]{'░' * empty}[/]"


def mas_badge(mas: float) -> str:
    """Render a colored MAS score badge."""
    style = score_style(mas)
    return f"[{style}][MAS: {mas:.2f}][/{style}]"
