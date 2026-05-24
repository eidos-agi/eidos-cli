# CARDINALITY — Solo by default, escalate on triggers

Per THE-POD, every operation runs at Solo (1 model), Pair (2 models), or
Pod (3 models). Never more than 3. Composition for scale.

## Default is Solo

80% of decisions are obvious; Solo handles them. The latency-bounded
prior matters: until LLMs are fast enough for real-time multi-model
deliberation, Solo is the floor that ships work. Pair and Pod are
specializations the orchestrator escalates to when triggers fire.

## Escalation triggers

CARDINALITY escalates Solo → Pair → Pod when any of these fire:

1. **High-stakes** — the task touches contracts that bind future
   operations (telos changes, ADRs, governance, anti-goal additions).
2. **Novel** — no prior praxis turn matches the task class.
3. **Ambiguous** — task body or frontmatter has unresolved pronouns,
   unspecified targets, or multiple defensible interpretations.
4. **Undocumented** — required guardrails or SOPs are missing for the
   operation's owner_forge.
5. **StepProof required** — migrations, production deploys, secret
   rotation, irreversible/regulated workflows, or explicit
   `stepproof`/`ceremony` language require verifier-gated StepProof
   evidence.

## Solo-never-floor list

Per THE-POD, these operations are NEVER allowed to ship under Solo
judgment alone. They escalate to at least Pair regardless of triggers:

- `telos-set` / `telos-supersede`
- `guardrail-create` (and any active-status flip)
- `decision-create` (research → ADR pipeline)
- `ADR-accept`
- `failure_when → close` (closing an eidos because failure_when fired)
- `scope-spawn` (`eidos spawn`)
- `close-reached` (closing an eidos with outcome=reached)

v1.0 records the cardinality contract on the manifest and in `pod.log`.
Real multi-model Pair/Pod convening lands with Rhea integration per
ADR-008. Until then, Solo runs but the contract documents that
high-stakes operations are owed an attestation.

## How CARDINALITY writes its output

The CardinalityDecision is included in the context bundle:

```json
{
  "cardinality": "solo",
  "rationale": "No escalation triggers fired. Solo is the doctrinal default.",
  "triggers_fired": []
}
```

And recorded in the continuation envelope so VERIFY can fail-closed on
Solo-never-floor + Solo + uncertainty per ADR-008.

When `requires_step_proof` is true, the substrate must run ACT under
StepProof ceremony and attach StepProof audit evidence before
`eidos do --continue`. Eidos records the requirement; it does not create
the StepProof run automatically in v1.
