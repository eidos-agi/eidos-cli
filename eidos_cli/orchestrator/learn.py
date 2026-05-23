"""LEARN phase — write praxis turn; route SOR update; log plugin candidate.

Per ADR-008, the previously-named LEARN, DOCUMENT, and META steps are
consolidated here: LEARN is THE-LOOP's name and writing structured
artifacts (DOCUMENT) plus plugin-candidate logging (META) are kinds of
learning. Promotion of a candidate to an actual plugin is a separate
verb gated by frequency thresholds.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .perceive import TaskContext


def write_praxis_turn(
    ctx: TaskContext,
    tick_id: str,
    outcome: str,
    delta: str | None,
    evidence_bundle: Path | None,
    cardinality: str,
    failures: list[str] | None = None,
) -> Path:
    """Write a praxis turn artifact recording what happened on this task."""
    assert outcome in {"improved", "no-op", "reverted", "blocked"}, outcome

    turns_dir = ctx.eidos_home / ".eidos" / "praxis" / "turns"
    turns_dir.mkdir(parents=True, exist_ok=True)
    turn_path = turns_dir / f"{tick_id}.md"

    front = {
        "tick_id": tick_id,
        "task_id": ctx.task_id,
        "outcome": outcome,
        "cardinality": cardinality,
        "timestamp": datetime.now().isoformat(),
        "summary": ctx.task_frontmatter.get("title", ""),
    }
    if delta:
        front["delta_proposed"] = delta
    if evidence_bundle:
        front["evidence_bundle"] = str(evidence_bundle)
    if failures:
        front["verify_failures"] = failures

    body_lines = [
        f"# Praxis turn — {tick_id}",
        "",
        f"## Task `{ctx.task_id}`",
        f"{ctx.task_frontmatter.get('title', '')}",
        "",
        f"## Outcome",
        outcome,
        "",
    ]
    if delta:
        body_lines += ["## Delta", delta, ""]
    if failures:
        body_lines += ["## Verify failures"]
        body_lines += [f"- {f}" for f in failures]
        body_lines += [""]

    turn_path.write_text(
        f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n\n" + "\n".join(body_lines)
    )
    return turn_path


def route_sor(
    ctx: TaskContext,
    artifact_class: str | None,
    evidence_bundle: Path | None,
) -> dict[str, Any]:
    """Apply SOR routing per .eidos/governor/sops/sor_routing.md.

    Returns the routing decision (which forge/path the SOR update lands in)
    so the calling substrate can apply it.

    For v1.0, this is *routing only* — it doesn't auto-write the SOR. The
    calling substrate reads this decision and acts on it. (Auto-write is
    a v1.1 task once we have substrate-class trust to route content.)
    """
    sop_path = ctx.eidos_home / ".eidos" / "governor" / "sops" / "sor_routing.md"
    if not sop_path.is_file():
        return {
            "decision": "docket_completed_only",
            "reason": "no SOR routing SOP found; default applied",
        }
    try:
        rules = _parse_sor_rules(sop_path)
    except Exception as e:
        return {
            "decision": "docket_completed_only",
            "reason": f"SOR SOP parse failed: {type(e).__name__}: {e}",
        }
    tags = ctx.task_frontmatter.get("tags", []) or []
    selectors = rules.get("selectors", {})
    cls = artifact_class
    if cls is None:
        for t in tags:
            if t in selectors:
                cls = selectors[t]
                break
    cls = cls or rules.get("default_artifact_class", "docket_completion_only")
    matching = [r for r in rules.get("rules", []) if r.get("artifact_class") == cls]
    if not matching:
        return {
            "decision": "docket_completed_only",
            "reason": f"no rule for artifact_class={cls!r}; default applied",
        }
    rule = matching[0]
    return {
        "decision": "route",
        "artifact_class": cls,
        "owner_forge": rule.get("owner_forge"),
        "target": rule.get("target"),
        "required_evidence": rule.get("required_evidence", []),
        "fallback": rule.get("fallback"),
    }


def _parse_sor_rules(path: Path) -> dict[str, Any]:
    text = path.read_text()
    if not text.startswith("---\n"):
        return yaml.safe_load(text) or {}
    end = text.find("\n---", 4)
    if end < 0:
        return yaml.safe_load(text[4:]) or {}
    return yaml.safe_load(text[4:end]) or {}


def log_plugin_candidate(
    ctx: TaskContext,
    pattern_id: str,
    task_class: str,
    proposed_plugin: str,
    outcome: str,
) -> Path:
    """Append an observation to a plugin-candidate file, creating it if new."""
    cand_dir = ctx.eidos_home / ".eidos" / "praxis" / "patterns" / "candidates"
    cand_dir.mkdir(parents=True, exist_ok=True)
    cand_path = cand_dir / f"{pattern_id}.md"

    if cand_path.is_file():
        text = cand_path.read_text()
        existing = _parse_candidate_front(text)
        existing.setdefault("observations", []).append(
            {
                "task_id": ctx.task_id,
                "date": datetime.now().isoformat(),
                "outcome": outcome,
            }
        )
        existing["last_seen"] = datetime.now().isoformat()
        cand_path.write_text(_render_candidate(existing, task_class, proposed_plugin))
    else:
        front = {
            "pattern_id": pattern_id,
            "observations": [
                {
                    "task_id": ctx.task_id,
                    "date": datetime.now().isoformat(),
                    "outcome": outcome,
                }
            ],
            "first_seen": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "task_class": task_class,
            "proposed_plugin": proposed_plugin,
            "promotion_status": "candidate",
        }
        cand_path.write_text(_render_candidate(front, task_class, proposed_plugin))
    return cand_path


def _parse_candidate_front(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    return yaml.safe_load(text[4:end]) or {}


def _render_candidate(
    front: dict[str, Any], task_class: str, proposed: str
) -> str:
    return (
        f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n\n"
        f"# Plugin candidate — `{front['pattern_id']}`\n\n"
        f"**Task class:** {task_class}\n\n"
        f"**Proposed plugin:** {proposed}\n\n"
        "Promotion gate per `.eidos/governor/sops/plugin_promotion.md` "
        "(default: ≥3 observations + ≥2 verified successes + ≥1 failure analysis).\n"
    )
