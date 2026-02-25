"""Entry point for CortexOS CLI.

Usage:
    python -m cortex_cli            → Interactive TUI (Mode A)
    python -m cortex_cli <command>  → Scriptable CLI (Mode B)
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) > 1:
        from cortex_cli.cli import cli_main
        cli_main()
    else:
        from cortex_cli.app import CortexApp
        app = CortexApp()
        app.run()


if __name__ == "__main__":
    main()
