"""CLI entry point for CortexOS."""

import os

import click

_DEFAULT_URL = os.environ.get("CORTEX_URL", "https://api.cortexa.ink")


@click.group()
def main():
    """CortexOS CLI — hallucination detection for LLM agents."""
    pass


@main.command()
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
    """Launch the real-time live monitor."""
    from cortexos.tui.live import RichMonitor

    RichMonitor(base_url=url, api_key=api_key).run()


@main.command()
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
@click.option("--port", "-p", default=3000, type=int, help="Local server port.")
@click.option("--no-open", is_flag=True, help="Don't auto-open browser.")
def dashboard(api_key: str, url: str, port: int, no_open: bool) -> None:
    """Launch the web dashboard in your browser."""
    from cortexos.dashboard.server import serve

    serve(engine_url=url, api_key=api_key, port=port, open_browser=not no_open)


if __name__ == "__main__":
    main()
