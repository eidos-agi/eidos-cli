# VERIFY — check evidence; fail closed for high-stakes

VERIFY runs at `eidos do --continue`. It is the gate between substrate
work and praxis-turn write.

When CARDINALITY marks `requires_step_proof=true`, StepProof audit output is
the stronger evidence form: the substrate should attach the relevant
`.stepproof/runs/<run_id>/events.jsonl`, `stepproof audit verify` output, or a
shipment report containing the `stepproof-audit` gate.

## Two layers of check

1. **Structural** — deterministic. Evidence bundle exists and is
   non-empty. Each Definition-of-Done item in the task's frontmatter is
   evidenced by token-overlap against the evidence bundle's contents.
2. **Semantic** — heuristic. Task body checked against telos
   `success_when_not` (anti-goals) via token-overlap (≥3 distinct ≥5-char
   tokens AND ≥60% of the anti-goal's tokens). False-positive prone; the
   real classifier waits for Rhea integration.

## Fail-closed for Solo-never-floor + Solo + uncertainty

If the task is in the Solo-never-floor set (see
`eidos guide loop cardinality`) and cardinality was Solo and VERIFY
found any uncertainty, the result is:

```json
{
  "passed": false,
  "failed_closed": true,
  "block_reason": "Solo-never-floor + Solo + uncertainty; Pair review required"
}
```

The task does NOT move to `completed/`. To resume, obtain a Pair or
human review attestation, attach it to the evidence bundle, and re-run
`eidos do --continue`.

## Outcome enum

`--outcome` must be one of:

- `improved` — verify passed; task moves to `completed/`.
- `no-op` — verify passed but nothing changed (intentional skip).
- `reverted` — substrate undid a change in flight.
- `blocked` — VERIFY failed or fail-closed gate hit.

VERIFY overrides `--outcome` when it fails: outcome is forced to
`blocked` regardless of what was passed.

## Plugin verify

When a task names a plugin in `required_plugins`, that plugin's
`verify.py` (if present) can be invoked. The engine does not yet
delegate to plugin-side verify automatically; substrate is responsible
for running `eidos plugin run --continue <slug> --work-dir <path>` and
attaching the result to the evidence bundle. Future versions will chain
this automatically.
