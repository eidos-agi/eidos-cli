---
id: TASK-0002
title: Build eidos mcp serve (razor-thin help-only MCP)
status: Done
created: '2026-05-14'
updated: '2026-05-14'
---
New eidos_cli/mcp_server.py per ADR-007: single mcp__eidos__help tool with optional subcommand arg for drill-down. eidos mcp serve subcommand boots it. Mirrors the pattern from telos-md/research-md/governor/docket-md mcp_server.py files (which become legacy MCP entry points after this lands).

**Completion notes:** eidos mcp serve landed. New eidos_cli/mcp_server.py: razor-thin Server('eidos') with one help tool. Drill-down via subcommand='<name>' supports both top-level verbs ('define') and nested forge paths ('docket task-create'). Verified via stdio JSON-RPC: handshake, tools/list returns one tool named 'help', help() returns the eidos command tree, help(subcommand='define') returns Typer --help text, help(subcommand='docket task-create') drills through the forge namespace. This is the unified MCP surface promised by ADR-007 — five forge-specific mcp__*__help servers can now retire in favor of mcp__eidos__help.
