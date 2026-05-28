import rich_click as click
from py2rely import cli_context


@click.command(context_settings=cli_context, name="mcp")
@click.option("--transport", type=click.Choice(["stdio", "sse"]), default="stdio", show_default=True, help="MCP transport")
@click.option("--port", type=int, default=8000, show_default=True, help="Port for SSE transport")
def mcp_cli(transport: str, port: int) -> None:
    """Start the py2rely MCP server for Claude Code integration."""
    from py2rely.mcp.server import mcp

    if transport == "sse":
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")
