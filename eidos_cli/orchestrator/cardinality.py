"""CARDINALITY phase — preflight gate per ADR-008.

Decides Solo / Pair / Pod for the remainder of the loop. Runs after PERCEIVE
and before DECOMPOSE/SPECIALIZE. Per THE-POD, Solo is the default; escalation
requires one of the four triggers (high stakes, novel, ambiguous, undocumented)
to fire, OR the operation must hit the Solo-never-floor list.

The classifier is heuristic for v1.0 — no LLM call, just rule-based against
the task description and context. When Rhea-class substrate is wired, this
phase can become a real cheap-Solo classifier (one model call).

ADR-008 says: phases may locally override *upward* (escalate Solo → Pair
or Pair → Pod) when work surprises. Never downward.
"""

from __future__ import annotations

from dataclasses import dataclass

from .perceive import TaskContext


# Operations that THE-POD says are Solo-never-floor (Pair-or-Pod minimum).
SOLO_NEVER_FLOOR_OPS = {
    "telos-set",
    "telos-supersede",
    "guardrail-create",
    "decision-create",
    "adr-create",
    "failure-when-fire",
    "scope-spawn",
    "close-reached",
}


@dataclass
class CardinalityDecision:
    cardinality: str  # "solo" | "pair" | "pod"
    rationale: str
    triggers_fired: list[str]

    def to_dict(self) -> dict:
        return {
            "cardinality": self.cardinality,
            "rationale": self.rationale,
            "triggers_fired": self.triggers_fired,
        }


def classify(ctx: TaskContext) -> CardinalityDecision:
    """Heuristic cardinality classifier.

    Rules (in priority order):

    1. If the task's tags include a Solo-never-floor op (e.g. ``telos-set``),
       escalate to Pair minimum.
    2. If the task body/title contains ``novel|unprecedented|first time``,
       escalate to Pair (novelty trigger).
    3. If the task body/title contains ``irreversible|production|migration``,
       escalate to Pair (high stakes trigger).
    4. If the task body contains explicit ``??`` or ``ambiguous`` markers
       or has no acceptance criteria + no clear DoD, escalate to Pair
       (ambiguity trigger).
    5. Default: Solo.

    Each rule contributes a trigger to ``triggers_fired``. If multiple fire,
    the cardinality is the highest reached (Pair > Solo). Pod is reached
    only when ≥ 2 triggers fire OR the never-floor op is high-stakes
    (``telos-set``, ``scope-spawn``, ``close-reached``).
    """
    triggers: list[str] = []
    title = (ctx.task_frontmatter.get("title") or "").lower()
    body = ctx.task_body.lower()
    tags = [t.lower() for t in ctx.task_frontmatter.get("tags", [])]

    # Rule 1: Solo-never-floor by tag.
    floor_hit = SOLO_NEVER_FLOOR_OPS.intersection(tags)
    if floor_hit:
        triggers.append(f"solo-never-floor:{','.join(sorted(floor_hit))}")

    # Rule 2: novelty.
    novelty_markers = ("novel", "unprecedented", "first time", "never done")
    if any(m in body or m in title for m in novelty_markers):
        triggers.append("novelty")

    # Rule 3: high-stakes.
    stakes_markers = (
        "irreversible",
        "production",
        "migration",
        "delete",
        "destroy",
        "data loss",
    )
    if any(m in body or m in title for m in stakes_markers):
        triggers.append("high-stakes")

    # Rule 4: ambiguity.
    ambig_markers = ("??", "ambiguous", "unclear", "tbd")
    has_acceptance = bool(
        ctx.task_frontmatter.get("acceptance-criteria")
        or ctx.task_frontmatter.get("definition-of-done")
    )
    if any(m in body or m in title for m in ambig_markers) and not has_acceptance:
        triggers.append("ambiguity")

    # Rule 5: undocumented territory — proxy: task tags include domains
    # not appearing in any recent praxis turn.
    if not ctx.recent_praxis_turns and len(tags) > 0:
        triggers.append("no-prior-experience")

    # Decision.
    if not triggers:
        return CardinalityDecision(
            cardinality="solo",
            rationale="No escalation triggers fired. Solo is the doctrinal default.",
            triggers_fired=[],
        )

    high_stakes_floors = {"scope-spawn", "telos-set", "telos-supersede", "close-reached"}
    if floor_hit and floor_hit.intersection(high_stakes_floors):
        return CardinalityDecision(
            cardinality="pod",
            rationale=(
                "Solo-never-floor operation with high stakes; THE-POD mandates Pod for "
                "operations that bind the eidos's identity or future."
            ),
            triggers_fired=triggers,
        )

    if len(triggers) >= 2:
        return CardinalityDecision(
            cardinality="pod",
            rationale=(
                f"Multiple escalation triggers fired ({len(triggers)}). "
                "Pod is the appropriate cardinality for compound risk."
            ),
            triggers_fired=triggers,
        )

    return CardinalityDecision(
        cardinality="pair",
        rationale=f"One escalation trigger fired ({triggers[0]}). Pair (proposer + critic) sufficient.",
        triggers_fired=triggers,
    )
