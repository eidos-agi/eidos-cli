"""``eidos do`` — the orchestrating engine of the scope architecture.

Implements [THE-LOOP](../../../eidos-philosophy/THE-LOOP.md) at the per-task scope,
per the design in [ADR-008](../../governor.md/.governor/adr/ADR-008-eidos-do-orchestrating-engine.md).

The engine is *structural*, not *cognitive*: it walks the phases, captures
durable artifacts, and verifies against forge contracts. The intelligence
(DECOMPOSE / SPECIALIZE / ACT) lives in the calling substrate (a Claude
Code session, a Codex session, etc.). When Rhea-class substrate ships,
the orchestrator gains the ability to fork its own intelligence per phase
without changing this design.

Modules:

- :mod:`perceive` — load task + telos + guardrails + recent praxis turns
- :mod:`cardinality` — preflight gate: Solo / Pair / Pod for the rest of the loop
- :mod:`compose` — emit the agent's context bundle (DECOMPOSE+SPECIALIZE prompts)
- :mod:`verify` — check evidence against forge contracts; fail-closed on Solo-never-floor
- :mod:`learn` — write praxis turn; LEARN/DOCUMENT/META combined per THE-LOOP
- :mod:`envelope` — continuation envelope: hash + verify on ``--continue``
"""

from .envelope import ContinuationEnvelope, compute_envelope, verify_envelope
from .perceive import perceive

__all__ = [
    "ContinuationEnvelope",
    "compute_envelope",
    "verify_envelope",
    "perceive",
]
