# Evidence — TASK-0004

## Artifacts created
- `eidos_cli/cli/spawn.py` (324 lines) — Typer command implementing
  promote-task-to-child-eidos. PERCEIVES the parent task, validates the
  child four-field telos contract, cascades parent anti-goals (unless
  `--no-inherit-anti-goals`), scaffolds child forges, moves parent task
  into `docket/promoted/` with frontmatter marker, records spawn on
  parent `pod.log` with `cardinality=pair-or-pod-required`.
- `eidos_cli/cli/_app.py::_wire()` — added `from . import spawn as
  _spawn_cmd` and `_spawn_cmd.register(app)`.
- `eidos_cli/eidos_cli/cli/_app.py` root help string already lists
  `spawn` in the SCOPE row.

## Smoke results (happy path)
Parent eidos at `/tmp/eidos-spawn-smoke-1`:
```
parent:        parent  (b00b0d15...)
child id:      b0303dc0-048e-4321-a06b-0acade6da718
child name:    child-complex-thing
child home:    /private/tmp/eidos-spawn-smoke-1/.eidos/children/b0303dc0-048e-4321-a06b-0acade6da718
forges:        docket, governor, praxis
child telos:
  statement:        Solve the complex thing as its own scope
  success_when:     1 entries
  failure_when:     1 entries
  success_when_not: 1 entries (1 inherited from parent)
cardinality contract: Pair/Pod required for high-stakes ops on this child.
```

## Structural verification
- `pod.log` line: `2026-05-14 SPAWN parent_task=TASK-0001 child_id=b0303dc0... name=child-complex-thing cardinality=pair-or-pod-required`
- Parent task moved from `docket/tasks/` to `docket/promoted/` with
  frontmatter additions: `promoted_to_child_eidos:
  b0303dc0-048e-4321-a06b-0acade6da718`, `promoted_at: 2026-05-14`.
- Child `eidos.json` carries `parent_id` matching parent's id.

## Negative gates
- `eidos spawn TASK-9999 ...` → `error: task 'TASK-9999' not found in docket`
- `eidos spawn TASK-0001 --success-when y --failure-when z` (no
  statement) → `error: --statement is required ...`

## Regression
Smoke suite still 20/20 green after the wire-up.

## Cardinality contract
Spawn is in THE-POD's Solo-never-floor list. v1.0 records the contract
on the child manifest and in the pod.log; real Pair/Pod convening lands
with Rhea integration per ADR-008.
