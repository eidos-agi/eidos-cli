---
name: use-eidos-cli
description: Use when the user asks about Eidos, Eidos AGI, platform status, `eidos do`, closeout, cleanup before done, docket-task orchestration, evidence verification, praxis learning, gateway routing, vault/secrets, plugins, or which Eidos AGI specialist system should handle a task. This skill tells Codex to call the installed `eidos` CLI first; MCP and plugins should only point to CLIs, while CLIs provide progressive reveal of the deeper tool graph.
---

# Use Eidos CLI

Use Eidos when work needs to become a tracked, evidenced loop.

The installed `eidos` CLI is the first stop for Eidos AGI platform questions and task loops. Eidos orients Codex, runs docket tasks through `eidos do`, verifies evidence on continuation, captures praxis learning, runs closeout checks before completion claims, handles auth/vault/status checks, and routes to specialist tools only when needed.

## Architecture Principle

Get away from giant MCP tool surfaces. Use MCP and Codex plugins as small signposts that point to local CLIs. The CLIs are the real progressive-reveal interface: `--help`, subcommands, `doctor`, `status`, `list`, `find`, `ask`, and domain-specific commands can expose thousands of tools without loading all of them into Codex at once.

In practice, Eidos has three modes:

1. Orient
   Use `eidos guide`, `eidos status`, and `eidos health` to understand the current eidos before acting.

2. Execute
   Use `eidos do <task-id>` and `eidos do --continue <task-id> --evidence <path>` when the user gives a docket task or asks to operate the Eidos loop.

3. Closeout / Route / Learn
   Use `eidos closeout` before saying a mission is complete. Use `eidos plugin ...`, vault/auth commands, and specialist CLIs after the live Eidos output shows who owns the next step.

Operationally:

- Start with `eidos guide` for broad orientation.
- Use `eidos status` or `eidos health` for current operating state.
- Use `eidos do <task-id>` when the user is asking to work a docket task through the Eidos loop.
- Use `eidos closeout` before claiming the mission is closed.
- Let Eidos identify the relevant domain or specialist.
- Run that specialist CLI's smallest useful command.
- Only use MCP when it is the pointer or bridge to a CLI, not as the primary place to model every capability.

## Primary Rule

When the user asks a broad Eidos AGI question, run the smallest relevant `eidos` command first, then answer from live output and route onward only when needed.

When the user gives a docket task ID or asks to operate the Eidos loop, use `eidos do`:

```bash
eidos do <task-id>
eidos do --continue <task-id> --evidence <path> --outcome improved --delta "<one-line>"
```

The first invocation performs PERCEIVE and CARDINALITY, writes the context bundle, plan/evidence locations, and continuation envelope, then returns control to the substrate. The continue invocation verifies evidence, records the outcome, writes the praxis turn, and routes learning.

Before final completion, run:

```bash
eidos closeout
```

Closeout is read-only. It checks whether relevant git repos are clean and pushed, and whether Codex marketplace entries point at real plugin bundles. If it fails, report the residue and fix it before claiming the loop is closed.

Useful entrypoints:

```bash
eidos --help
eidos guide
eidos guide loop
eidos status
eidos health
eidos do <task-id>
eidos do --continue <task-id> --evidence <path>
eidos closeout
eidos plugin list
eidos plugin show <name>
eidos vault --help
eidos vault list
eidos vault get <path>
eidos vault set <path> <value>
eidos vault keys --help
```

## Gateway Routing

After Eidos gives the operating picture, route to the specialist surface that owns the work:

- Use Rhea for sovereign model routing, model debate, long-lived Rhea sessions, pairing, and image generation.
- Use Felix for agent-building, pre-scaffold interviews, agent standards, maintainer loops, `AGENTS.md` wakeup files, and repo-health checks.
- Use Foreman for parallel coding delegation to AI engineer workers in isolated git worktrees.
- Use Reeves for Daniel's personal operating picture, finance freshness, mail/messages evidence, tasks, memory, and wiki.
- Use Surfari for browser-agent runs, web-surfing evaluations, playbooks, and browser runtime improvement loops.
- Use Forge-Forge for forge discovery, forge patterns, registry lookups, and creating new domain forges.
- Use Eidos Vault for secret paths, API key status, and platform credentials when a task explicitly requires them.

Prefer the specialist CLI after routing. A plugin or MCP shim may help Codex discover or call the CLI, but the CLI should own the domain logic and deeper tool reveal.

## What This Plugin Does Not Do

This plugin does not do the work itself. It starts and closes the loop around the work.

It does not reimplement the Eidos runtime. It does not contain platform state, task data, vault secrets, or specialist business logic. It teaches Codex the reflex: call `eidos`, read the live output, act with evidence, then route, verify, or learn from there.

## Vault And Secrets Boundary

The Eidos CLI can access vault paths. Treat that as sensitive.

- Prefer `eidos vault list` or path-level status before retrieving secret values.
- Do not print secret values into the conversation unless the user explicitly asks and the value is necessary for the task.
- Do not create, revoke, rotate, or expose credentials unless the user explicitly confirms the action.
- Stop cleanly before MFA, legal, money movement, outbound communication, or other human-only boundaries.

## Source-Of-Truth Rules

- Use live `eidos` CLI output before stale memory, repo notes, or guesses.
- If the CLI reports a blocker, report that blocker plainly instead of inferring healthy state.
- If the task belongs to a specialist system, use that system's live surface after Eidos has routed the question.

## Plugin Boundary

This plugin contains no platform data and no secrets. It is only a Codex routing layer for the local Eidos CLI.
