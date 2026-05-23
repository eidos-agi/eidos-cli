# Eidos Codex Plugin

Eidos turns a vague or docketed task into a tracked, evidenced loop.

This Codex plugin teaches the agent when to start that loop, when to close it, and when to route to a specialist. The live `eidos` CLI is the runtime; the plugin is the reflex.

## The Job

Use Eidos when work needs to be accountable:

- take a docket task
- gather context
- decide Solo, Pair, or Pod cardinality
- hand Codex the right working packet
- require evidence before completion
- write the learning back into the system
- route specialist work only when needed

## Three Modes

Orient:

```bash
eidos guide
eidos status
eidos health
```

Execute:

```bash
eidos do <task-id>
eidos do --continue <task-id> --evidence <path> --outcome improved --delta "<one-line>"
```

Route / Learn:

```bash
eidos plugin list
eidos plugin show <name>
eidos vault list
```

The first `eidos do` invocation runs PERCEIVE and CARDINALITY, writes a context bundle and continuation envelope, then returns control to the substrate. After Codex acts and writes evidence, the continue invocation verifies evidence, writes the praxis turn, routes the system-of-record update, and can create plugin-learning candidates.

## Non-Goal

This plugin does not do the work itself. It starts and closes the loop around the work.

The architecture is intentionally CLI-first. Codex plugins and MCP shims should be small pointers into CLIs, not giant inventories of tools. The CLIs provide progressive reveal: guide pages, status/health checks, domain subcommands, task loops, plugin commands, vault/auth commands, and deeper specialist affordances only when the task calls for them. This is now part of the Eidos Marketplace standard: `/Users/dshanklinbv/repos-eidos-agi/eidos-marketplace/STANDARD.md`.

## Eidos AGI Plugin Family

- `eidos@eidos-agi`: CLI-first gateway into the Eidos AGI platform and specialist systems.
- `felix@eidos-agi`: routing layer for the live Felix agent-builder CLI.
- `rhea@eidos-agi`: sovereign model routing, debate, pairing, and image tools.
- `foreman@eidos-agi`: multi-agent coding delegation and git worktree execution.
- `reeves@eidos-agi`: routing layer for the live Reeves CLI.
- `surfari@eidos-agi`: routing layer for the live Surfari CLI and browser-agent improvement loop.
- `forge-forge@eidos-agi`: routing layer for Eidos forge discovery and forge creation patterns.

## Install In Codex

Clone the repo:

```bash
mkdir -p /Users/dshanklinbv/repos-eidos-agi
git clone git@github.com:eidos-agi/eidos-cli.git /Users/dshanklinbv/repos-eidos-agi/eidos-cli
```

Install or refresh the Eidos AGI Codex plugin cache:

```bash
mkdir -p /Users/dshanklinbv/.codex/plugins/cache/eidos-agi/eidos/0.1.0
rsync -a --delete --exclude '.git' --exclude '__pycache__' --exclude '.mcp.json' \
  /Users/dshanklinbv/repos-eidos-agi/eidos-cli/ \
  /Users/dshanklinbv/.codex/plugins/cache/eidos-agi/eidos/0.1.0/
```

Add Eidos to `~/.agents/plugins/marketplace.json`:

```json
{
  "name": "eidos",
  "source": {
    "source": "local",
    "path": "./plugins/eidos"
  },
  "policy": {
    "installation": "AVAILABLE",
    "authentication": "ON_INSTALL"
  },
  "category": "Productivity"
}
```

Enable the plugin in `~/.codex/config.toml`:

```toml
[plugins."eidos@eidos-agi"]
enabled = true
```

Restart Codex after editing config.

## Smoke Test

```bash
eidos guide
eidos --help
eidos status
eidos health
eidos do --help
eidos plugin list
```
