# learn — promote a praxis turn into a plugin

## Goal
Take a learning the eidos has already written (a praxis turn, or an
entry from the plugin-candidate ledger) and refine it into a reusable
plugin. The system is descriptive ("here's what happened"); your job is
to make it prescriptive ("when this situation recurs, do this").

## Inputs
The runtime has placed everything you need under the working
directory. `context.json` names:

- `eidos_home` — the current eidos's home directory. Read praxis turns
  at `<eidos_home>/.eidos/praxis/turns/` and the candidate ledger at
  `<eidos_home>/.eidos/praxis/plugin_candidates.jsonl` (if present).
- `args.from_praxis` — if set, a specific turn id to promote.
- `args.candidate` — if set, a specific candidate slug to promote.
- `args.scope` — `local` (write into the current eidos) or `global`
  (write into `~/.eidos/plugins/`). Default `global` so the learning
  propagates across eidi.

## What to produce
Three files under `draft/`. Do not skip any. The verify step checks for
all three.

### `draft/plugin.yaml`
A complete plugin manifest:
```yaml
slug: <kebab-case>             # required; must not collide with reserved primitives
version: 0.1.0                  # required
alias: <slug-or-shorter>       # optional; only set if a top-level alias is appropriate
description: |                  # required; one paragraph
  <what the plugin does and when to use it>
when_to_fire:                  # required; 2-5 short conditions
  - <condition>
owner_forge: <one of: telos, research, governor, docket, praxis>
required_evidence:             # required; what the verify step checks for
  - <relative path under draft/>
faculty:                       # optional; only for subagent/judgment-mode plugins
  role: <specialist role>
  invoke_as: <short invocation name>
  handoff: <what the substrate should ask this specialist to decide>
```

### `draft/playbook.md`
The substrate-readable procedure. Mirror this playbook's shape: Goal /
Inputs / What to produce / What good looks like. Write it so a future
substrate (or future-you) can execute it cold.

### `draft/provenance.json`
Where this plugin came from. Required fields:
```json
{
  "source_turns": ["<praxis turn filename>", "..."],
  "source_eidos_id": "<the eidos this learning came from>",
  "promoted_by": "learn",
  "promoted_at": "<ISO date>",
  "rationale": "<one sentence: why this is worth promoting>"
}
```

## What good looks like
- **Prescriptive, not narrative.** Don't recount what happened; tell the
  next substrate what to do.
- **Names a clear trigger.** A future PERCEIVE step has to be able to
  decide whether this plugin applies. "When in doubt" is not a trigger.
- **Bounded.** A plugin does one thing. If the learning covers two
  distinct patterns, write two plugins.
- **Self-contained.** The playbook should not rely on facts that only
  exist in the conversation that produced it; capture them in the
  playbook itself.

## After you write the draft
The runtime will run `eidos plugin run --continue learn ...` which
delegates to this plugin's verify step (`verify.py`). If verify passes,
the user runs `eidos plugin install <draft_dir>` to land it in the
chosen store.
