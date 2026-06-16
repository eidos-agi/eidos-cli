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

import json
from dataclasses import dataclass, field
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
    proof_gates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failures": self.failures,
            "failed_closed": self.failed_closed,
            "block_reason": self.block_reason,
            "proof_gates": self.proof_gates,
        }


def verify(
    ctx: TaskContext,
    evidence_bundle: Path,
    cardinality: str,
    *,
    requires_step_proof: bool = False,
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
    proof_gates: list[dict[str, Any]] = []
    evidence_text = ""

    # Structural check 1: evidence bundle exists.
    if not evidence_bundle.exists():
        failures.append(f"evidence bundle missing at {evidence_bundle}")
    elif evidence_bundle.is_dir() and not any(evidence_bundle.iterdir()):
        failures.append(f"evidence bundle is empty at {evidence_bundle}")
    elif evidence_bundle.is_dir():
        evidence_text = _gather_text(evidence_bundle)
    elif evidence_bundle.is_file():
        try:
            evidence_text = evidence_bundle.read_text(errors="ignore")
        except OSError:
            evidence_text = ""

    # Structural check 2: docket task has DoD; if so, look for evidence of each.
    dod = ctx.task_frontmatter.get("definition-of-done", []) or []
    if dod and evidence_bundle.is_dir():
        for item in dod:
            item_lower = str(item).lower()
            # Cheap match: any token from the DoD item appears in the evidence.
            tokens = [t for t in item_lower.split() if len(t) > 3]
            if not any(tok in evidence_text.lower() for tok in tokens):
                failures.append(f"DoD item not evidenced: {item!r}")

    step_gate = _step_proof_gate(ctx, evidence_bundle, evidence_text, required=requires_step_proof)
    proof_gates.append(step_gate)
    if step_gate["required"] and not step_gate["ok"]:
        failures.append(step_gate["detail"])

    converge_gate = _converge_gate(ctx, evidence_bundle, evidence_text)
    proof_gates.append(converge_gate)
    if converge_gate["required"] and not converge_gate["ok"]:
        failures.append(converge_gate["detail"])

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
            proof_gates=proof_gates,
        )

    return VerifyResult(
        passed=not failures,
        failures=failures,
        failed_closed=False,
        block_reason=None,
        proof_gates=proof_gates,
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


def _step_proof_gate(
    ctx: TaskContext,
    evidence_bundle: Path,
    evidence_text: str,
    *,
    required: bool,
) -> dict[str, Any]:
    if not required and not _task_mentions(ctx, {"stepproof", "step proof", "ceremony", "audit"}):
        return {
            "id": "stepproof",
            "required": False,
            "ok": True,
            "status": "not-required",
            "detail": "StepProof evidence was not required for this task.",
        }

    ok = _evidence_mentions(
        evidence_bundle,
        evidence_text,
        ("stepproof", "step proof", "audit verify", "events.jsonl"),
        ("ok", "pass", "passed", "valid", "verified", "success"),
    ) or _json_marker_ok(evidence_bundle, ("stepproof", "step_proof"), ("ok", "passed", "valid", "verified"))
    return {
        "id": "stepproof",
        "required": required,
        "ok": ok,
        "status": "pass" if ok else "missing",
        "detail": (
            "StepProof audit evidence present."
            if ok
            else "StepProof audit evidence required but not found; attach `stepproof audit verify` output or a StepProof audit JSON artifact."
        ),
    }


def _converge_gate(ctx: TaskContext, evidence_bundle: Path, evidence_text: str) -> dict[str, Any]:
    required = _task_mentions(
        ctx,
        {"converge", "target row", "target rows", "probe", "scoreboard", "drift", "repair status"},
    )
    if not required:
        return {
            "id": "converge",
            "required": False,
            "ok": True,
            "status": "not-required",
            "detail": "Converge evidence was not required for this task.",
        }

    ok = _evidence_mentions(
        evidence_bundle,
        evidence_text,
        ("converge", "target row", "target rows", "probe", "scoreboard", "drift", "repair status"),
        ("ok", "pass", "passed", "green", "complete", "score"),
    ) or _json_marker_ok(evidence_bundle, ("converge",), ("ok", "passed", "complete"))
    return {
        "id": "converge",
        "required": True,
        "ok": ok,
        "status": "pass" if ok else "missing",
        "detail": (
            "Converge score/target evidence present."
            if ok
            else "Converge evidence required but not found; attach target/probe rows, drift report, or scoreboard output."
        ),
    }


def _task_mentions(ctx: TaskContext, markers: set[str]) -> bool:
    haystack = (
        str(ctx.task_frontmatter.get("title", ""))
        + "\n"
        + " ".join(str(tag) for tag in ctx.task_frontmatter.get("tags") or [])
        + "\n"
        + ctx.task_body
    ).lower()
    return any(marker in haystack for marker in markers)


def _evidence_mentions(
    evidence_bundle: Path,
    evidence_text: str,
    identity_terms: tuple[str, ...],
    success_terms: tuple[str, ...],
) -> bool:
    text = evidence_text.lower()
    path_text = str(evidence_bundle).lower()
    has_identity = any(term in text or term in path_text for term in identity_terms)
    has_success = any(term in text for term in success_terms)
    return has_identity and has_success


def _json_marker_ok(
    evidence_bundle: Path,
    object_keys: tuple[str, ...],
    success_keys: tuple[str, ...],
) -> bool:
    files = [evidence_bundle] if evidence_bundle.is_file() else list(evidence_bundle.rglob("*.json")) if evidence_bundle.is_dir() else []
    for path in files:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if _json_contains_success(data, object_keys, success_keys):
            return True
    return False


def _json_contains_success(value: Any, object_keys: tuple[str, ...], success_keys: tuple[str, ...]) -> bool:
    if isinstance(value, dict):
        lowered = {str(key).lower(): child for key, child in value.items()}
        if any(key in lowered for key in object_keys):
            scoped = [lowered[key] for key in object_keys if key in lowered]
            if any(_json_contains_success(child, (), success_keys) for child in scoped):
                return True
        for key, child in lowered.items():
            if key in success_keys and child in (True, "true", "pass", "passed", "valid", "verified", "complete", "ok"):
                return True
            if _json_contains_success(child, object_keys, success_keys):
                return True
    elif isinstance(value, list):
        return any(_json_contains_success(child, object_keys, success_keys) for child in value)
    return False
