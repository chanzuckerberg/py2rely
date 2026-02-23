"""CLI entry point for relion-ui."""

from __future__ import annotations

import sys

import rich_click as click

from py2rely import cli_context


@click.command(name="ui", context_settings=cli_context)
@click.option("--port", type=int, default=3000, show_default=True, help="Port to serve on.")
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help="Host to bind to. Use 0.0.0.0 to expose on all interfaces.",
)
@click.option("--no-browser", is_flag=True, default=False, help="Do not automatically open the browser on startup.")
@click.option(
    "--poll-interval",
    type=int,
    default=5,
    show_default=True,
    metavar="SECONDS",
    help="Seconds between status polls when filesystem watching is unavailable.",
)
def ui(port: int, host: str, no_browser: bool, poll_interval: int) -> None:
    """Browser-based pipeline visualizer and job monitor for RELION projects."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import watchdog  # noqa: F401
    except ImportError:
        click.echo(
            "\n[relion-ui] Required dependencies are not installed.\n"
            "Install them with:\n\n"
            "    pip install py2rely[relionui]\n"
            "    # or\n"
            "    uv add py2rely[relionui]\n"
        )
        sys.exit(1)

    from py2rely.relionui.server import launch

    launch(host=host, port=port, open_browser=not no_browser, poll_interval=poll_interval)
