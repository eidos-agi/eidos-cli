# PERCEIVE — load context, no judgment

PERCEIVE is mechanical. It reads. It does not think. The output is a
structured bundle that downstream phases can classify against.

## What it loads

- **Manifest** — `eidos.json` (id, name, members, active_forges).
- **Telos** — `telos.md` parsed into the four-field contract.
- **Task** — frontmatter + body from `docket/tasks/<task>.md`,
  `docket/completed/<task>.md`, or `docket/archive/<task>.md` (whichever
  contains a file matching the task id).
- **Guardrails** — every active guardrail markdown under
  `.eidos/governor/guardrails/`.
- **Recent praxis turns** — up to 5 most recent by mtime (summary,
  outcome, path).
- **Matched plugins** — from both stores (local + user-global), by four
  match paths. See `eidos guide loop perceive plugins-match`.
- **Recommended faculties** — matched plugins that declare `faculty`
  metadata, promoted into explicit subagent/specialist routes.

## The TaskContext

The dataclass passed to every later phase. Shape (Python):

```python
@dataclass
class TaskContext:
    eidos_home: Path
    manifest: EidosManifest
    telos: Telos | None
    task_id: str
    task_path: Path
    task_frontmatter: dict
    task_body: str
    guardrails: list[dict]
    recent_praxis_turns: list[dict]
    matched_plugins: list[dict]
    recommended_faculties: list[dict]
```

Written to disk as `.eidos/docket/contexts/<task-id>/context.json` for
the substrate to read.

## What PERCEIVE does NOT do

- It does not classify cardinality. That is the next phase.
- It does not enforce contracts. Guardrails are surfaced; the substrate
  is expected to read and respect them. The engine does not block ACT.
- It does not match plugins against ambiguous tasks. The token-overlap
  threshold is intentionally conservative (≥3 distinct ≥5-char tokens,
  ≥40% of the when_to_fire entry's tokens). False positives cost more
  than false negatives — a missed plugin can be invoked explicitly via
  `eidos <plugin-alias>`.
- It does not execute faculties. PERCEIVE only recommends which
  specialist/subagent the substrate should invoke and what evidence the
  checker should expect.
