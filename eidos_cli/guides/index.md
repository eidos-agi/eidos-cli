# eidos — the AI's guide

You are reading the **eidos-cli guide**. This is the manual written for
AI substrates (Claude Code, Codex, agent SDKs) operating eidos at the
terminal. Read what you need, drill where it matters, skip the rest.

## What eidos is

**An eidos is a unit of purpose defined by its telos.** Greek roots:
*eidos* = form, *telos* = end. The thing that gives an eidos its form
is the four-field telos contract:

- `statement`         — the north star (one sentence)
- `success_when`      — what arrival looks like (multiple entries)
- `failure_when`      — what triggers closing-as-unreached
- `success_when_not`  — anti-goals; what arrival must NOT look like

Every operation in eidos-cli is scoped to an eidos. An eidos has a home
directory containing a `.eidos/` folder with its manifest, telos, and
per-forge state. Member repos (the code repos the eidos works in) carry
a one-line `.eidos-pointer` file back to the home.

## The verbs

```
SCOPE:        eidos define <path>    — bring an eidos into being
              eidos enter            — open a session, emit briefing
              eidos status           — one-line health snapshot
              eidos activate <forge> — scaffold a dormant forge
              eidos tick             — drift-against-telos snapshot
              eidos closeout         — prove repos/plugins are clean before closing
              eidos ship             — prove build/install/plugin/live shipment facets
              eidos close            — terminally close with outcome

LOOP:         eidos do <task-id>     — run THE-LOOP for a docket task
              eidos spawn <task-id>  — promote task to child eidos

FORGES:       eidos telos / research / governor / docket / praxis ...

PLUGINS:      eidos plugin list/install/run/show
              eidos <plugin-alias>   — top-level alias for an installed plugin
              eidos learn            — praxis-turn → plugin; status/verify/finish

GUIDE:        eidos guide [topic]    — this manual, recursive drill-down
```

## The reflex

When given a task, the AI substrate's reflex is **`eidos do <task-id>`**.
That single verb walks THE-LOOP: PERCEIVE → CARDINALITY → emit context
bundle → (substrate acts) → `eidos do --continue` → VERIFY → LEARN.
The engine handles the structure; you handle the substance.

## The compounding layer

Every `eidos do` loop writes a praxis turn — what changed, why. The
first-class `learn` command promotes a praxis turn into a reusable plugin,
landing it in `~/.eidos/plugins/`. The *next* eidos's PERCEIVE phase
matches that plugin against its task and attaches the playbook to the
context bundle. **One eidos's learning becomes every eidos's reflex.**

## On-disk shape

```
<eidos_home>/
  .eidos/
    eidos.json           ← manifest (id, name, members, active_forges)
    telos.md             ← four-field contract
    governor/            ← guardrails, SOPs, ADRs (if active)
    docket/              ← tasks, plans, evidence, contexts, envelopes
    praxis/              ← turns, plugin_runs, plugin_candidates.jsonl
    research/            ← findings, decisions (if active)
    plugins/             ← eidos-local plugins (override user-global)
    children/<id>/.eidos/  ← child eidi (recursive)
  .eidos-pointer         ← (in member repos) one line → eidos_home

~/.eidos/plugins/        ← user-global plugin store; cross-eidos
```

## The doctrine

The architectural source is in `eidos-philosophy/`:

- `THE-EIDOS.md`          — what an eidos is (this guide condenses it)
- `THE-LOOP.md`           — PERCEIVE → … → LEARN at every scale
- `THE-POD.md`            — Solo/Pair/Pod cardinality, never more than 3
- `THE-FORGE.md`          — each operational layer is a forge with contracts
- `THE-FRACTAL.md`        — the pattern repeats at every scale
- `THE-ACCOUNTABILITY-CHAIN.md` — contracts gate; pod synthesizes

Implementation ADRs live in `governor.md/.governor/adr/`:

- `ADR-006` — CLI-first, razor-thin MCP
- `ADR-007` — eidos-cli as unified agent surface
- `ADR-008` — `eidos do` as orchestrating engine
- `ADR-009` — plugins as the recursive layer (this is what gives the system its compounding property)
