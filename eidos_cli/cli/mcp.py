"""``eidos mcp serve`` — boots the razor-thin MCP server."""

from __future__ import annotations

import typer

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


@app.command("serve")
def cmd_serve() -> None:
    """Run the eidos MCP server over stdio (entry point for MCP hosts)."""
    from ..mcp_server import run

    run()
