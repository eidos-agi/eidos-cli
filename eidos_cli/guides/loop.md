# The loop — `eidos do <task-id>`

`eidos do` is the orchestrating verb. It walks THE-LOOP at the per-task
scope per ADR-008. The verb is structural; the substance is the
substrate's work between two invocations.

## Two invocations

```
eidos do <task-id>                          # PERCEIVE → CARDINALITY → context bundle
# (substrate decomposes, plans, acts, writes evidence)
eidos do --continue <task-id> --evidence <path> --outcome improved --delta "<one-line>"
```

## What the engine emits at PERCEIVE

```
.eidos/docket/contexts/<task-id>/
  context.json            ← task + telos + guardrails + recent praxis + matched plugins
  plugins/<slug>.md       ← copy of every matched plugin's playbook
.eidos/docket/plans/<task-id>.md
.eidos/docket/evidence/<task-id>/   ← write your outputs here
.eidos/docket/envelopes/<task-id>.json   ← continuation envelope; staleness gate
```

## The phases

1. **PERCEIVE** — load task, telos, guardrails, recent praxis turns,
   matched plugins. Mechanical; no judgment.
2. **CARDINALITY** — Solo by default; escalate to Pair/Pod on triggers
   (high-stakes, novel, ambiguous, undocumented, plus the
   Solo-never-floor list per THE-POD).
3. **(substrate ACTS)** — decompose, specialize, act, compress. The
   engine has handed off; the substrate writes the plan and evidence.
4. **VERIFY** — structural checks against the evidence + semantic
   check against telos anti-goals. High-stakes ops fail closed on
   uncertainty; they must escalate to Pair or human review.
5. **LEARN** — write the praxis turn. Route the artifact to its system
   of record. Log a plugin candidate if a stable pattern_id is present.

## The continuation envelope

A hash of the per-task state (eidos id, task version, plan hash, SOR
routing config, member repo HEADs, substrate label) is captured at
PERCEIVE and checked at `--continue`. If anything that should be
immutable across the loop has changed, the continuation is refused.
Re-run `eidos do <task-id>` to start a fresh loop.

Known friction: the plan hash is currently in the staleness gate, but
the substrate is *expected* to write the plan between PERCEIVE and
`--continue` — so the first `--continue` always trips and a re-do is
required. Tracked; will be fixed by splitting the envelope into
immutable-across-loop vs. substrate-mutates groups.
