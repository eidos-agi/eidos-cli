# Promotion — turning a praxis turn into a plugin

A praxis turn is descriptive ("here's what happened and what we
figured out"). A plugin is prescriptive ("when this situation recurs,
do this"). Promotion is the transformation.

## Active vs. passive promotion

Two paths, same destination:

**Active** — user-invoked when they recognize a pattern worth keeping:
```
eidos learn --arg from_praxis=<tick-id>
eidos learn --arg candidate=<slug>
```

**Passive** — the plugin-candidate ledger crosses its threshold
(≥3 obs + ≥2 verified + ≥1 failure analysis) and surfaces in
`eidos plugin list --candidates` as ready-to-promote.

Both feed `~/.eidos/plugins/`, the cross-eidos compounding layer.

## The `learn` plugin

`learn` is itself a plugin, bundled in the eidos-cli wheel and copied
to `~/.eidos/plugins/learn/` on first run. Its `playbook.md` tells the
substrate:

1. Read recent praxis turns (or a specific one named in args).
2. Synthesize a draft plugin manifest into `<work_dir>/draft/`.
3. Required draft artifacts:
   - `draft/plugin.yaml` — full manifest with slug/version/description/
     alias?/when_to_fire/owner_forge/required_evidence.
   - `draft/playbook.md` — substrate-readable procedure (Goal / Inputs
     / What to produce / What good looks like).
   - `draft/provenance.json` — source_turns, source_eidos_id,
     promoted_by, promoted_at, rationale.

The plugin's `verify.py` enforces all three files exist, the manifest
has required fields, the slug is kebab-case, the owner_forge is one of
the five forges, the playbook is non-trivially short, and provenance
has the required fields with a non-empty source_turns list.

## After verify passes

```
eidos plugin install <work_dir>/draft --scope global
```

The destination dir is named from the manifest's `slug`, not `draft`.
If the plugin declares an `alias`, it appears as a top-level command
on the *next* `eidos` invocation.

## What good promotion looks like

- **Prescriptive, not narrative.** "When X, do Y." Not "we did X and
  it worked."
- **Trigger is sharp.** PERCEIVE has to be able to decide whether the
  plugin applies. "When in doubt" is not a trigger.
- **Bounded.** One plugin does one thing. If the learning covers two
  distinct patterns, two plugins.
- **Self-contained.** The playbook does not rely on facts that only
  exist in the conversation that produced it.
