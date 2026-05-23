"""Razor-thin MCP server for eidos.

Exposes ONE tool: ``help``. Every other operation happens via the CLI
(``eidos define``, ``eidos enter``, ``eidos research finding-create``, etc.).
This is the CLI-first / razor-thin-MCP shape per ADR-006 and ADR-007 — and
it consolidates the five forge-specific ``mcp__*__help`` servers shipped
this week into a single ``mcp__eidos__help`` for the entire scope
architecture.

Discovery flow:
  1. Agent calls ``mcp__eidos__help()`` — gets the full eidos command tree.
  2. Agent calls ``mcp__eidos__help(subcommand="define")`` — gets the
     ``eidos define --help`` text.
  3. Agent calls ``mcp__eidos__help(subcommand="docket task-create")``
     — drills into the docket forge namespace.
  4. Agent invokes the actual work via Bash: ``eidos <subcommand> [opts]``.
"""

from __future__ import annotations

import asyncio
import io
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("eidos")


HELP_DESCRIPTION = (
    "REQUIRED at session start for any Eidos scope work: returns the full "
    "eidos command tree. Call with no args for the top-level surface, or "
    "with subcommand='<name>' for that subcommand's full --help. All real "
    "work happens via Bash: `eidos <subcommand> [--json] [opts]`. eidos is "
    "the unified agent surface for the scope architecture — see THE-EIDOS "
    "in eidos-philosophy/ for the full doctrine. This MCP server is "
    "razor-thin by design."
)


HELP_TOOL = Tool(
    name="help",
    description=HELP_DESCRIPTION,
    inputSchema={
        "type": "object",
        "properties": {
            "subcommand": {
                "type": "string",
                "description": (
                    "Optional subcommand name. Top-level verbs: define, enter, "
                    "status, activate, tick, close, mcp. Forge namespaces: "
                    "'telos <verb>', 'research <verb>', 'governor <verb>', "
                    "'docket <verb>', 'praxis <verb>'. Platform: 'auth <verb>', "
                    "'vault <verb>', 'health'. Use spaces to drill into nested "
                    "subcommand groups (e.g. 'docket task-create')."
                ),
            },
        },
    },
)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [HELP_TOOL]


def _capture_help(argv: list[str]) -> str:
    """Run the Typer app with the given argv, capturing --help stdout."""
    from .cli import app

    buf = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = buf
    try:
        try:
            app(argv, standalone_mode=False)
        except SystemExit:
            pass
        except Exception as e:
            return f"error rendering help: {type(e).__name__}: {e}"
    finally:
        sys.stdout = real_stdout
    return buf.getvalue()


def _build_top_level_help() -> str:
    return "\n".join(
        [
            "eidos — Unified agent surface for the Eidos scope architecture.",
            "",
            "USAGE:  eidos <subcommand> [--json] [options]",
            "",
            "SCOPE LIFECYCLE (the eidos = a unit of purpose defined by its telos):",
            "  eidos define <path>           # bring an eidos into being",
            "                                  (deliberates the four-field telos contract +",
            "                                   active forge set + member repos)",
            "  eidos enter [<path>]          # open session inside existing eidos; boot briefing",
            "  eidos status [<path>]         # snapshot of current eidos state",
            "  eidos activate <forge>        # scaffold a previously-dormant forge",
            "  eidos tick                    # praxis tick: emit steering snapshot",
            "  eidos close <outcome>         # reached | abandoned | superseded",
            "",
            "FORGE NAMESPACES (direct forge access; eidos-aware path resolution):",
            "  eidos telos     ...           # the unwavering north star (Telos forge)",
            "  eidos research  ...           # evidence-graded decisions",
            "  eidos governor  ...           # vision, goals, guardrails, SOPs, ADRs",
            "  eidos docket    ...           # tasks, milestones, documents",
            "  eidos praxis    ...           # steering ticks, write-turn, notebook, status",
            "",
            "PLATFORM:",
            "  eidos auth      login | logout | status",
            "  eidos vault     get | set | list | rm | keys ...",
            "  eidos health",
            "",
            "MCP:",
            "  eidos mcp serve               # boots this MCP server (you're talking to it now)",
            "",
            "DRILL IN:    eidos <subcommand> --help    "
            "OR    mcp__eidos__help(subcommand='<name>')",
            "JSON MODE:   add --json to any subcommand for machine-readable output",
            "",
            "DOCTRINE:    Solo is the default cardinality. Spawn only when the work needs",
            "             its own governance scope. See THE-POD's escalation triggers and",
            "             THE-EIDOS's spawn criteria.",
        ]
    )


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "help":
        return [TextContent(type="text", text=f"unknown tool: {name!r}")]
    sub = (arguments or {}).get("subcommand")
    if sub:
        # Subcommand may be a single verb ("define") or a nested path
        # ("docket task-create"). Split on whitespace and append --help.
        argv = sub.split() + ["--help"]
        text = _capture_help(argv)
        if not text.strip():
            text = f"no help available for subcommand {sub!r}"
        return [TextContent(type="text", text=text)]
    return [TextContent(type="text", text=_build_top_level_help())]


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def run() -> None:
    """Entry point used by ``eidos mcp serve``."""
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        sys.exit(0)
