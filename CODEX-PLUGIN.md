# Eidos Codex Plugin

Eidos turns a vague or docketed task into a tracked, evidenced loop.

This Codex plugin teaches the agent when to start that loop, when to close it out, and when to route to a specialist. The live `eidos` CLI is the runtime; the plugin is the reflex.

Eidos should remain the coordinator, not the container. It decides what proof is
needed, when to escalate, which specialist owns the next move, and whether the
evidence is clean enough to close. It should not absorb every specialist
runtime into the engine. StepProof owns ceremony enforcement, Cept owns agent
proprioception, Rhea owns model routing/debate, Felix owns agent-building, and
Eidos routes to those faculties and verifies their proof.

## The Job

Use Eidos when work needs to be accountable:

- take a docket task
- gather context
- decide Solo, Pair, or Pod cardinality
- hand Codex the right working packet
- require evidence before completion
- run closeout before claiming done
- write the learning back into the system
- route specialist work only when needed
- route to Converge when software completion needs target/probe rows, drift checks, regression memory, or row aggregation
- resist Eidos bloat by adding awareness/proof gates before adding ownership

## Three Modes

Orient:

```bash
eidos guide
eidos scope --json
eidos status
eidos health
```

Execute:

```bash
eidos do <task-id>
eidos do --continue <task-id> --evidence <path> --outcome improved --delta "<one-line>"
```

Closeout / Route / Learn:

```bash
eidos closeout
eidos plugin list
eidos plugin show <name>
eidos vault list
```

The first `eidos do` invocation runs PERCEIVE and CARDINALITY, writes a context bundle and continuation envelope, then returns control to the substrate. After Codex acts and writes evidence, the continue invocation verifies evidence, writes the praxis turn, routes the system-of-record update, and can create plugin-learning candidates.

`eidos closeout` is the final cleanup gate. It is read-only and checks for dirty repos, unpushed commits, and dangling Codex marketplace plugin entries before the agent says the mission is closed.

`eidos ship` is a one-shot shipment gate, not a repair loop. It can report what proof failed and what the agent should do next, but it does not spawn reviewers, run subagents, modify code, or recurse. Run any reviewer or repair agent outside `ship`, then rerun `ship` once to verify the result.

## Agentic-First Doctrine

AGENTIC-FIRST SOFTWARE-SKEPTICAL DOCTRINE

Eidos prefers agentic improvement over software production.

Do not write code merely because code is possible. Software is justified only
when it strengthens judgment, evidence, routing, memory, constraints,
measurement, repair, learning, or closeout.

Before coding, justify why instruction, routing, proof, Converge, Felix,
StepProof, or praxis is insufficient. If one of those paths can solve the
problem, prefer it over new software.

## Non-Goal

This plugin does not do the work itself. It starts and closes the loop around the work.

The architecture is intentionally CLI-first. Codex plugins and MCP shims should be small pointers into CLIs, not giant inventories of tools. The CLIs provide progressive reveal: guide pages, status/health checks, domain subcommands, task loops, plugin commands, vault/auth commands, and deeper specialist affordances only when the task calls for them. This is now part of the Eidos Marketplace standard: `/Users/dshanklinbv/repos-eidos-agi/eidos-marketplace/STANDARD.md`.

The bloat test is explicit: if a change improves routing, evidence, escalation,
shipment, closeout, or learning, it may belong in Eidos. If it makes Eidos own
a domain-specific runtime that a specialist CLI already owns, keep that runtime
in the specialist and teach Eidos how to call and verify it.

## Eidos AGI Plugin Family

- `eidos@eidos-agi`: CLI-first gateway into the Eidos AGI platform and specialist systems.
- `felix@eidos-agi`: routing layer for the live Felix agent-builder CLI.
- `rhea@eidos-agi`: sovereign model routing, debate, pairing, and image tools.
- `foreman@eidos-agi`: multi-agent coding delegation and git worktree execution.
- `reeves@eidos-agi`: routing layer for the live Reeves CLI.
- `surfari@eidos-agi`: routing layer for the live Surfari CLI and browser-agent improvement loop.
- `forge-forge@eidos-agi`: routing layer for Eidos forge discovery and forge creation patterns.
- `converge`: measurable completion forge for target rows, adapters, aggregators, drift/regression checks, and repair/re-score loops.

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
eidos scope --json
eidos status
eidos health
eidos do --help
eidos closeout
eidos plugin list
```
