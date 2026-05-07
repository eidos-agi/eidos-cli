# Eidos Codex Plugin

Eidos is the gateway plugin for the Eidos AGI Codex plugin family. It tells Codex to use the live `eidos` CLI first for platform orientation, auth status, vault state, and routing into specialist systems.

The architecture is intentionally CLI-first. Codex plugins and MCP shims should be small pointers into CLIs, not giant inventories of tools. The CLIs provide progressive reveal: top-level help, domain subcommands, status/doctor/list/find/ask commands, and deeper specialist affordances only when the task calls for them.

## Eidos AGI Plugin Family

- `eidos@eidos-agi`: CLI-first gateway into the Eidos AGI platform and specialist systems.
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
eidos --help
eidos status
eidos health
```
