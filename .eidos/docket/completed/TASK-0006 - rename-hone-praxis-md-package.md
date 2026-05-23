---
id: TASK-0006
title: Rename hone → praxis-md package
status: Done
created: '2026-05-14'
updated: '2026-05-14'
---
Hone is the steering forge. Per ADR-007, rename the PyPI package, CLI binary, MCP server, state directory (.hone/ → .praxis/), library imports (hone → praxis_md). Migration script in praxis-md handles in-place rename for existing consumers. Wire praxis-md's CLI as 'eidos praxis' namespace replacing the placeholder.

**Completion notes:** hone → praxis-md renamed in place. Module hone → praxis_md. State dir .hone/ → .praxis/. Config file hone.yaml → praxis.yaml. Tool names hone_tick/hone_write_turn/hone_notebook/hone_status → tick/write_turn/notebook/status. MCP server name 'hone' → 'praxis-md'. Env var HONE_HOME → PRAXIS_HOME. CLI script hone → praxis-md. Added minimal Typer CLI (cli/_app.py) wrapping the four primitives. eidos praxis namespace mounts praxis-md's Typer app (replacing the previous placeholder). 9/9 praxis-md tests pass. Migration script praxis-md-migrate handles consumer config sweep. Full CLI-first razor-thin MCP restructure (one help tool, mcp serve subcommand, _logic/ modules) deferred as follow-on.
