---
name: use-eidos-cli
description: Use when the user asks about Eidos, Eidos AGI, platform status, gateway routing, vault/secrets, or which Eidos AGI specialist system should handle a task. This skill tells Codex to call the installed `eidos` CLI first and then route to the appropriate Eidos AGI plugin or CLI.
---

# Use Eidos CLI

Use the installed `eidos` CLI as the first stop for Eidos AGI platform questions. Eidos is the gateway layer: it should orient Codex before Codex reaches for specialist tools.

## Primary Rule

When the user asks a broad Eidos AGI question, run the smallest relevant `eidos` command first, then answer from live output and route onward only when needed.

Useful entrypoints:

```bash
eidos --help
eidos status
eidos health
eidos vault --help
eidos vault list
eidos vault get <path>
eidos vault set <path> <value>
eidos vault keys --help
```

## Gateway Routing

After Eidos gives the operating picture, route to the specialist surface that owns the work:

- Use Rhea for sovereign model routing, model debate, long-lived Rhea sessions, pairing, and image generation.
- Use Foreman for parallel coding delegation to AI engineer workers in isolated git worktrees.
- Use Reeves for Daniel's personal operating picture, finance freshness, mail/messages evidence, tasks, memory, and wiki.
- Use Surfari for browser-agent runs, web-surfing evaluations, playbooks, and browser runtime improvement loops.
- Use Forge-Forge for forge discovery, forge patterns, registry lookups, and creating new domain forges.
- Use Eidos Vault for secret paths, API key status, and platform credentials when a task explicitly requires them.

Prefer the specialist CLI or plugin after routing. Do not duplicate its domain logic inside Codex.

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
