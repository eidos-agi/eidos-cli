# Spawn — `eidos spawn <task-id>`

Promote a docket task to a child eidos when it is too complex to be a
leaf. The child gets its own four-field telos, its own active forge
set, and its own pod.log entry. The parent task moves to
`docket/promoted/` with a frontmatter marker pointing at the child.

## When to spawn

- The task spans ≥2 distinct skill domains.
- The task needs its own governance artifacts (ADRs, SOPs, guardrails)
  that would pollute the parent.
- The task has a `failure_when` meaningfully different from the
  parent's.
- The task will produce its own praxis trail worth keeping separate.

If any one of these is true, spawn. If none, keep it as a leaf docket
task and run `eidos do`.

## The verb

```
eidos spawn <task-id> \
  --statement   "<child north star — refinement of parent>" \
  --success-when "comma,separated" \
  --failure-when "comma,separated" \
  --success-when-not "explicit child anti-goals (optional)" \
  --forges       governor,docket,praxis        # child-specific subset
  --members      repo1,repo2                    # default: inherit parent's
  --no-inherit-anti-goals                       # opt out of parent cascade
```

## What happens on disk

```
<parent_home>/
  .eidos/
    pod.log                               ← "SPAWN parent_task=... child_id=... cardinality=pair-or-pod-required"
    docket/tasks/<task>.md                ← deleted
    docket/promoted/<task>.md             ← moved here with promoted_to_child_eidos: <id>
    children/<child_id>/
      .eidos/
        eidos.json                        ← child manifest with parent_id
        telos.md                          ← four-field child telos
        governor/  docket/  praxis/       ← child's active forges
```

## Cardinality contract

Per THE-POD, `spawn` is in the Solo-never-floor list. v1.0 records the
contract on the child manifest and in `pod.log`. Real Pair/Pod convening
lands with Rhea integration (ADR-008). Until then, the spawn verb works
under Solo but the contract documents that future high-stakes operations
on this child should escalate.

## Recursion

A child eidos can itself spawn. `<parent>/.eidos/children/<a>/.eidos/children/<b>/.eidos/`
is a valid path. Anti-goals cascade through the chain by default
(`--no-inherit-anti-goals` opts out at each level).
