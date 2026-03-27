"""Entry point for the cx command — one app, one command."""

import click

from cx import __version__


@click.command()
@click.version_option(__version__, prog_name="cx")
@click.option("--demo", is_flag=True, help="Use synthetic demo data.")
@click.option("--web", is_flag=True, help="Launch web dashboard.")
@click.option("--serve", is_flag=True, help="Start MCP server.")
@click.option("--port", "-p", default=None, type=int, help="Port for --web or --serve.")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="MCP transport (--serve only).",
)
def cli(demo: bool, web: bool, serve: bool, port: int | None, transport: str) -> None:
    """Cortexa \u2014 Memory intelligence for AI agents."""
    if web:
        _launch_web(demo, port or 7700)
    elif serve:
        _launch_serve(demo, transport, port or 8000)
    else:
        from cx.app import CortexaApp

        app = CortexaApp(demo=demo)
        app.run()


def _launch_web(demo: bool, port: int) -> None:
    try:
        from cx.dashboard.server import app, set_adapter
        import uvicorn
    except ImportError:
        click.echo("Missing dependency: pip install 'cortexa[dashboard]'")
        raise SystemExit(1)

    if demo:
        from cx.adapters.demo import DemoAdapter

        set_adapter(DemoAdapter())
    else:
        from cx.adapters import get_adapter
        from cx.config import CortexaConfig

        cfg = CortexaConfig.load()
        set_adapter(get_adapter(cfg.adapter, cfg.adapter_options))

    click.echo(f"Cortexa Dashboard starting at http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def _launch_serve(demo: bool, transport: str, port: int) -> None:
    try:
        from cx.mcp.server import mcp, set_adapter
    except ImportError:
        click.echo("Missing dependency: pip install 'cortexa[mcp]'")
        raise SystemExit(1)

    if demo:
        from cx.adapters.demo import DemoAdapter

        set_adapter(DemoAdapter())
    else:
        from cx.adapters import get_adapter
        from cx.config import CortexaConfig

        cfg = CortexaConfig.load()
        set_adapter(get_adapter(cfg.adapter, cfg.adapter_options))

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=port)
