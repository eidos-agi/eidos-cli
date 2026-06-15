"""Foreman-ready Pod packet generation for ``eidos do``.

Eidos owns routing metadata and guardrails; Foreman owns worker execution.
This module only writes packets that a caller can hand to Foreman.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cardinality import CardinalityDecision
from .perceive import TaskContext


WATCH_TERMS = {
    "emux",
    "headed",
    "interactive",
    "interrupt",
    "interruptible",
    "tmux",
    "watch",
    "watchable",
}

DEFAULT_HARD_STOPS = [
    "do not enter MFA, passkeys, passwords, or other secrets",
    "do not approve payments, legal agreements, profile installs, final submissions, deploys, or public publishes",
    "do not run destructive git commands or mutate files outside the packet scope",
    "stop and report if acceptance criteria or file scope are ambiguous",
]


def build_pod_packet_bundle(
    ctx: TaskContext,
    decision: CardinalityDecision,
    *,
    context_dir: Path,
    evidence_dir: Path,
) -> dict[str, Any] | None:
    """Return and persist a Pod packet bundle when cardinality is Pod."""
    if decision.cardinality != "pod":
        return None

    packet_dir = context_dir / "pod"
    packet_dir.mkdir(parents=True, exist_ok=True)
    packets = [_build_packet(ctx, decision, evidence_dir)]
    bundle = {
        "kind": "eidos.pod-packets",
        "version": 1,
        "task_id": ctx.task_id,
        "cardinality": decision.to_dict(),
        "handoff": {
            "owner": "foreman",
            "boundary": "Foreman may dispatch scoped worker packets; Eidos remains responsible for acceptance, evidence, and closeout.",
            "command_template": "foreman delegate --engine {recommended_engine} --packet <packet-json>",
        },
        "packets": packets,
    }
    path = packet_dir / "foreman-packets.json"
    path.write_text(json.dumps(bundle, indent=2, default=str) + "\n")
    bundle["path"] = str(path)
    return bundle


def _build_packet(
    ctx: TaskContext,
    decision: CardinalityDecision,
    evidence_dir: Path,
) -> dict[str, Any]:
    title = str(ctx.task_frontmatter.get("title") or ctx.task_id)
    verification_command = _first_string(
        ctx.task_frontmatter,
        ("verification_command", "verification", "test_command", "smoke_command"),
    )
    if not verification_command:
        verification_command = "run the task-specific verification command, then attach output under the evidence bundle"

    engine = _recommended_engine(ctx)
    route_stack = ["eidos", "foreman"]
    if engine == "claude-emux":
        route_stack.append("emux")
    if decision.requires_step_proof:
        route_stack.append("stepproof")
    route_stack.append("converge")

    proof_artifacts = [
        "worker id and run id",
        "worktree path",
        "diff summary",
        "verification command output",
        f"evidence bundle update under {evidence_dir}",
    ]
    if engine == "claude-emux":
        proof_artifacts.extend(
            [
                "emux head command",
                "emux capture command",
                "emux interrupt command",
            ]
        )
    if decision.requires_step_proof:
        proof_artifacts.extend(["StepProof run id", "stepproof audit verify output"])
    proof_artifacts.append("Converge target/probe/score summary when measurable rows exist")

    return {
        "id": f"{ctx.task_id.lower()}-implementation",
        "goal": title,
        "acceptance_criteria": _acceptance_criteria(ctx),
        "files_in_scope": _list_frontmatter(
            ctx.task_frontmatter,
            ("files_in_scope", "files", "paths", "touched_files"),
            default=[str(ctx.task_path)],
        ),
        "files_out_of_scope": _list_frontmatter(
            ctx.task_frontmatter,
            ("files_out_of_scope", "out_of_scope", "excluded_files"),
            default=[],
        )
        + [".env", ".env.*", "**/*secret*", "**/*credential*", "**/*private-key*"],
        "verification_command": verification_command,
        "allowed_actions": [
            "inspect files listed in files_in_scope",
            "make minimal edits needed for this packet",
            "run verification_command and capture output",
            "write evidence artifacts into the evidence bundle",
        ],
        "hard_stop_actions": _hard_stops(ctx, decision),
        "proof_artifacts_expected": proof_artifacts,
        "recommended_engine": engine,
        "specialist_stack": route_stack,
        "foreman_command": f"foreman delegate --engine {engine} --packet {ctx.task_id.lower()}-implementation.json",
    }


def _recommended_engine(ctx: TaskContext) -> str:
    haystack = (
        str(ctx.task_frontmatter.get("title", ""))
        + "\n"
        + " ".join(str(tag) for tag in ctx.task_frontmatter.get("tags") or [])
        + "\n"
        + ctx.task_body
    ).lower()
    return "claude-emux" if any(term in haystack for term in WATCH_TERMS) else "claude-code"


def _acceptance_criteria(ctx: TaskContext) -> list[str]:
    for key in ("acceptance_criteria", "acceptance-criteria", "definition_of_done", "definition-of-done"):
        values = _coerce_string_list(ctx.task_frontmatter.get(key))
        if values:
            return values
    return ["task goal is satisfied and evidence is attached before `eidos do --continue`"]


def _hard_stops(ctx: TaskContext, decision: CardinalityDecision) -> list[str]:
    stops = list(DEFAULT_HARD_STOPS)
    for guardrail in ctx.guardrails:
        title = str(guardrail.get("title") or guardrail.get("id") or "").strip()
        if title:
            stops.append(f"respect active guardrail: {title}")
    if decision.requires_step_proof:
        stops.append("do not continue without StepProof audit evidence")
    return _unique(stops)


def _first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _list_frontmatter(
    data: dict[str, Any],
    keys: tuple[str, ...],
    *,
    default: list[str],
) -> list[str]:
    for key in keys:
        values = _coerce_string_list(data.get(key))
        if values:
            return values
    return list(default)


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
