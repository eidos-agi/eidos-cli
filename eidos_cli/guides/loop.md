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

## Closeout

Before saying a mission is finished, run:

```
eidos closeout
```

Closeout is read-only. It checks git cleanliness and upstream sync for the
current eidos/repo plus Codex marketplace plugin pointers. It is the final
residue scan: dirty repos, unpushed commits, dangling plugin entries, and
other cleanup work should be resolved before the loop is treated as closed.

For release-shaped work, run shipment before closeout:

```
eidos ship <repo> --marketplace <marketplace-repo> --live-plugin <slug>
```

Shipment is facet-aware. It proves the source tree, Python package build,
clean wheel install, CLI entrypoints, plugin validators, marketplace drift,
installed Eidos plugin surface, and post-clean artifact state where those
facets exist. Closeout then remains the final residue gate.

Each repo can teach Eidos its own shipment style with:

```
.eidos/ship/manifest.toml
```

The manifest selects built-in gates, adds repo-specific command gates, sets
marketplace/live-plugin defaults, records artifact cleanup policy, and keeps
durable `yes` / `do_not` learning so future shipments remember what worked and
what must not be repeated. Shipment evidence belongs under
`.eidos/ship/shipments/`.

Repos that use StepProof can require shipment to prove the StepProof audit
stream too:

```
[gates]
builtin = ["git-clean-pushed", "stepproof-audit", "post-clean-artifact-scan"]

[stepproof]
required = true
audit = true
metrics = true
```

StepProof remains a specialist enforcement layer, not a default dependency.
Use it for ceremony-bound, high-stakes, or regulated work where each step
must advance only after independent verifier evidence.

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
