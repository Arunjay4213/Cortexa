"""CLI entry point for CortexOS Monitor."""

import os

import click

_DEFAULT_URL = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")


@click.command()
@click.option(
    "--url",
    default=None,
    envvar="CORTEX_URL",
    help=f"CortexOS Engine base URL (default: {_DEFAULT_URL}).",
)
@click.option(
    "--api-key",
    default=None,
    envvar="CORTEX_API_KEY",
    help="API key (or set CORTEX_API_KEY).",
)
def monitor(url: str | None, api_key: str | None) -> None:
    """Launch the CortexOS real-time verification monitor."""
    from cortexos.tui.app import CortexMonitor

    base_url = url or _DEFAULT_URL
    app = CortexMonitor(base_url=base_url, api_key=api_key)
    app.run()


if __name__ == "__main__":
    monitor()
