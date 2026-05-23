# LEARN — write the praxis turn, route artifacts, log plugin candidates

LEARN runs after VERIFY passes (or fails non-closed). It is what makes
each loop leave the system smarter than it found it.

## What LEARN writes

1. **Praxis turn** at `.eidos/praxis/turns/<task-id>.<HHMMSS>.md` —
   frontmatter (tick_id, outcome, cardinality, evidence_path, failures)
   plus a one-paragraph delta.
2. **SOR routing decision** — based on the artifact's `artifact_class`
   (frontmatter), routes the verified artifact to its system of record
   (governor adr/, research decisions/, etc.). v1.0 default:
   `docket_completed_only` when no artifact_class is declared.
3. **Plugin candidate** (when applicable) — if the task frontmatter
   declares a `pattern_id`, LEARN appends to
   `.eidos/praxis/plugin_candidates.jsonl` with:
   - pattern_id, task_class, proposed_plugin, outcome, evidence_path.

## The candidate threshold

Per ADR-008, a candidate becomes ready-to-promote at:

```
≥3 observations  AND  ≥2 verified  AND  ≥1 failure analysis
```

`eidos plugin list --candidates` surfaces the ledger. The bundled
`learn` plugin reads it and produces a draft plugin manifest for the
user to review and install. See `eidos guide plugins promotion`.

## Why LEARN matters

The whole compounding-layer story rests on this phase. Without LEARN,
each loop is a one-off — code changes, but the system gets no smarter.
With LEARN writing praxis turns and `learn` promoting them into plugins
landing in `~/.eidos/plugins/`, **the next session's PERCEIVE reads
what this session learned.** That is the recursive payoff.

## Failure semantics

If VERIFY failed (non-closed), LEARN still writes a praxis turn — with
outcome=`blocked` and `failures` populated. Blocked turns are first-class
training data; the plugin-candidate ledger's "≥1 failure analysis"
threshold depends on them being written.
