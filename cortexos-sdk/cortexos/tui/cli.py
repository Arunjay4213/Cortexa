"""CLI entry point for CortexOS Monitor."""

import os

import click

_DEFAULT_URL = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")


@click.command()
@click.option(
    "--api-key", "-k",
    envvar="CORTEX_API_KEY",
    required=True,
    help="API key (or set CORTEX_API_KEY).",
)
@click.option(
    "--url", "-u",
    envvar="CORTEX_URL",
    default=_DEFAULT_URL,
    help=f"CortexOS Engine base URL (default: {_DEFAULT_URL}).",
)
def monitor(api_key: str, url: str) -> None:
    """Launch the Cortexa real-time verification monitor."""
    from cortexos.tui.app import CortexMonitor

    app = CortexMonitor(base_url=url, api_key=api_key)
    app.run()


def main():
    """Entry point for the cortexos CLI."""
    monitor()


if __name__ == "__main__":
    main()
