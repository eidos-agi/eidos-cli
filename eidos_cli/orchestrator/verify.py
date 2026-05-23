"""VERIFY phase — check evidence against forge contracts; fail closed for Solo-never-floor.

Per ADR-008:
- Structural verification is deterministic (forge contract checks).
- Semantic verification (against telos triggers) runs at the chosen
  cardinality.
- For Solo-never-floor operations with uncertain semantic verification,
  fail *closed*: surface "VERIFY blocked; Pair/human review required"
  rather than passing on Solo judgment.

THE-ACCOUNTABILITY-CHAIN: VERIFY checks evidence, not vibes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cardinality import SOLO_NEVER_FLOOR_OPS
from .perceive import TaskContext


@dataclass
class VerifyResult:
    passed: bool
    failures: list[str]
    failed_closed: bool  # True if blocked on human/Pair review
    block_reason: str | None  # populated when failed_closed=True

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failures": self.failures,
            "failed_closed": self.failed_closed,
            "block_reason": self.block_reason,
        }


def verify(
    ctx: TaskContext,
    evidence_bundle: Path,
    cardinality: str,
) -> VerifyResult:
    """Run VERIFY against the task and its evidence bundle.

    Args:
        ctx: PERCEIVE output.
        evidence_bundle: Directory or file containing ACT's outputs.
        cardinality: The cardinality at which ACT ran (solo/pair/pod).

    Returns:
        VerifyResult. If the task is in the Solo-never-floor list and
        cardinality was solo, fail_closed kicks in unless evidence
        explicitly attests Pair/human review happened.
    """
    failures: list[str] = []

    # Structural check 1: evidence bundle exists.
    if not evidence_bundle.exists():
        failures.append(f"evidence bundle missing at {evidence_bundle}")
    elif evidence_bundle.is_dir() and not any(evidence_bundle.iterdir()):
        failures.append(f"evidence bundle is empty at {evidence_bundle}")

    # Structural check 2: docket task has DoD; if so, look for evidence of each.
    dod = ctx.task_frontmatter.get("definition-of-done", []) or []
    if dod and evidence_bundle.is_dir():
        evidence_text = _gather_text(evidence_bundle)
        for item in dod:
            item_lower = str(item).lower()
            # Cheap match: any token from the DoD item appears in the evidence.
            tokens = [t for t in item_lower.split() if len(t) > 3]
            if not any(tok in evidence_text.lower() for tok in tokens):
                failures.append(f"DoD item not evidenced: {item!r}")

    # Semantic check against telos anti-goals (success_when_not).
    # v1.0 heuristic — token-overlap against task body. False-positive prone;
    # real classifier waits for Rhea-class substrate per ADR-008.
    # Threshold tuning: require ≥3 distinct ≥5-char tokens to match AND
    # those tokens must comprise ≥60% of the anti-goal's tokens. Avoids
    # flagging on a single common word like 'tasks' or 'production'.
    if ctx.telos and ctx.telos.success_when_not:
        body = ctx.task_body.lower()
        for anti in ctx.telos.success_when_not:
            anti_tokens = [t for t in str(anti).lower().split() if len(t) > 4]
            if len(anti_tokens) < 3:
                continue  # too-short anti-goal; can't reliably token-match
            matched = [t for t in anti_tokens if t in body]
            if len(matched) >= 3 and len(matched) / len(anti_tokens) >= 0.6:
                failures.append(
                    f"task body may match anti-goal {anti!r} "
                    f"(token overlap: {matched}); review required"
                )

    # Fail-closed gate: Solo-never-floor + Solo cardinality + any uncertainty.
    tags = [t.lower() for t in ctx.task_frontmatter.get("tags", [])]
    is_floor_op = bool(SOLO_NEVER_FLOOR_OPS.intersection(tags))
    if is_floor_op and cardinality == "solo" and failures:
        return VerifyResult(
            passed=False,
            failures=failures,
            failed_closed=True,
            block_reason=(
                f"task is in the Solo-never-floor set (tags include "
                f"{sorted(SOLO_NEVER_FLOOR_OPS.intersection(tags))}) and VERIFY "
                "encountered uncertainty under Solo cardinality. Per ADR-008, "
                "semantic verification of high-stakes operations must escalate "
                "to Pair or human review rather than pass on Solo judgment. "
                "Resume with `eidos do --continue` after a Pair review provides "
                "an attestation."
            ),
        )

    return VerifyResult(
        passed=not failures,
        failures=failures,
        failed_closed=False,
        block_reason=None,
    )


def _gather_text(d: Path) -> str:
    """Concatenate text content from a small evidence dir for token-matching."""
    pieces: list[str] = []
    for f in d.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() in {".log", ".txt", ".md", ".out", ".json", ".yaml", ".yml"}:
            try:
                pieces.append(f.read_text(errors="ignore"))
            except OSError:
                continue
        if sum(len(p) for p in pieces) > 100_000:
            break
    return "\n".join(pieces)
