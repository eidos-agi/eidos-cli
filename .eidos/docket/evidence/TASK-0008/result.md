# Evidence: eidos do — the orchestrating engine

Implemented per ADR-008. The engine is structural (walks phases, captures
artifacts, verifies); the intelligence lives in the calling substrate.

## Modules shipped

- eidos_cli/orchestrator/__init__.py — package
- eidos_cli/orchestrator/perceive.py — PERCEIVE phase (loads telos, guardrails, recent praxis turns, task content)
- eidos_cli/orchestrator/cardinality.py — preflight gate; Solo-default; escalation triggers; Solo-never-floor list
- eidos_cli/orchestrator/envelope.py — continuation envelope with hash-based stale-state detection
- eidos_cli/orchestrator/verify.py — fail-closed for Solo-never-floor with uncertain semantic verify
- eidos_cli/orchestrator/learn.py — praxis turn writer + SOR routing + plugin candidate logging
- eidos_cli/cli/do.py — `eidos do <task-id>` and `eidos do --continue <task-id>` verbs

## Phase coverage

PERCEIVE  -> deterministic file loads
CARDINALITY -> heuristic classifier (Solo / Pair / Pod) per the four triggers
DECOMPOSE / SPECIALIZE / ACT / COMPRESS -> delegated to calling substrate
RECONCILE -> implicit pre-VERIFY
VERIFY -> deterministic forge contract checks; semantic check with tuned token-threshold; fail-closed for Solo-never-floor
LEARN -> praxis turn written; outcome classified; failures captured
RETRY -> wired (re-invoke eidos do; envelope rejects stale state)
DOCUMENT -> folded into LEARN via SOR routing
META -> plugin candidate logging gated by pattern_id in frontmatter

## Five durable artifacts produced per invocation

1. Plan         -> .eidos/docket/plans/TASK-NNNN.md
2. Evidence     -> .eidos/docket/evidence/TASK-NNNN/
3. Praxis turn  -> .eidos/praxis/turns/<tick-id>.md
4. Task complete-> .eidos/docket/completed/TASK-NNNN ...
5. SOR routing  -> applied per .eidos/governor/sops/sor_routing.md (or default)

Plus: continuation envelope and context bundle (operational, not core).

## Dogfood: TASK-0010 closed by the engine

The first real eidos do invocation closed TASK-0010 (SOR routing config
spec). Verified end-to-end:
- envelope written
- evidence bundle accepted
- VERIFY passed (with the token-threshold tightened to avoid spurious
  anti-goal matches on common words)
- praxis turn written
- task moved to completed/

Engine ships. Substrate intelligence still required for the agent-side
phases. Rhea integration is the next leap.
