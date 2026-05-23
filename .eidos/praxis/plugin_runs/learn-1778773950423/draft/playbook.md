# promote-task-to-child-eidos

## Goal
Promote a docket task that is too complex to be a leaf into a child
eidos with its own four-field telos, forge set, and pod.log entry — so
the work has its own scope, its own governance, its own praxis trail,
and the parent stays uncluttered.

## Inputs
- `args.task_id` — the docket task to promote.
- `args.statement` — one sentence; the child's north star (a refinement
  of the parent's scoped to this work).
- `args.success_when` — comma-separated; what arrival looks like.
- `args.failure_when` — comma-separated; what triggers closing as
  unreached.
- `args.success_when_not` — optional explicit child anti-goals. Parent's
  anti-goals cascade by default unless `args.no_inherit_anti_goals` is
  true.
- `args.forges` — child's active forge set. Default
  `governor,docket,praxis`. A leaf-becoming-branch often needs less
  than the parent.

## What to produce
The runtime command `eidos spawn <task_id> --statement ... --success-when
... --failure-when ...` does the work. After invocation, capture the
following under `evidence/`:

- `evidence/child_id.txt` — single line: the child eidos id printed by
  spawn.
- `evidence/pod_log_excerpt.md` — the line written to the parent's
  `pod.log` (must contain `SPAWN parent_task=... child_id=... cardinality=pair-or-pod-required`).
- `evidence/promoted_task_path.txt` — the path the parent task was moved
  to under `docket/promoted/`, confirming it carries
  `promoted_to_child_eidos: <child_id>` in its frontmatter.

## What good looks like
- **The child telos is a refinement, not a copy.** If the child's
  statement is identical to the parent's, the child does not need to
  exist as a separate eidos.
- **The forge set is chosen, not defaulted.** A child eidos often needs
  fewer forges than the parent. Reach for the narrowest active set that
  covers the work.
- **Anti-goal cascade is on by default.** Parent's `success_when_not`
  inherits into the child unless you have a specific reason to suppress.
- **The promotion is irreversible from inside the eidos.** Confirm the
  task warrants its own scope before invoking. A wrongly-promoted task
  pollutes `docket/promoted/` and orphans a child eidos.

## After you write the evidence
The runtime's verify step checks the three files under `evidence/` exist
and have non-empty content. If verify passes, the user runs
`eidos plugin install <draft_dir>` to land the plugin in
`~/.eidos/plugins/promote-task-to-child-eidos/`.
