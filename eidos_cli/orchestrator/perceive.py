"""PERCEIVE phase — load task + telos + guardrails + relevant praxis turns.

Mechanical. No deliberation. Per THE-LOOP, PERCEIVE is reading, not thinking.
Outputs a structured context bundle the next phase (CARDINALITY preflight)
can classify against.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..scope.manifest import EidosManifest, find_eidos_dir, load_manifest
from ..scope.telos import Telos, load_telos


@dataclass
class TaskContext:
    """The bundle of data PERCEIVE produces for a given task."""

    eidos_home: Path
    manifest: EidosManifest
    telos: Telos | None
    task_id: str
    task_path: Path
    task_frontmatter: dict[str, Any]
    task_body: str
    guardrails: list[dict[str, Any]]
    recent_praxis_turns: list[dict[str, Any]]
    matched_plugins: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eidos_home": str(self.eidos_home),
            "eidos_id": self.manifest.id,
            "eidos_name": self.manifest.name,
            "task_id": self.task_id,
            "task_path": str(self.task_path),
            "task": {
                "frontmatter": self.task_frontmatter,
                "body": self.task_body,
            },
            "telos": self.telos.to_dict() if self.telos else None,
            "guardrails": self.guardrails,
            "recent_praxis_turns": self.recent_praxis_turns,
            "matched_plugins": self.matched_plugins,
        }


def perceive(eidos_home: Path, task_id: str) -> TaskContext:
    """Load everything the orchestrator needs to know about *task_id*.

    Raises FileNotFoundError if the eidos or task is missing.
    """
    eidos_home = Path(eidos_home).expanduser().resolve()
    eidos_dir = find_eidos_dir(eidos_home)
    manifest = load_manifest(eidos_dir)
    if manifest is None:
        raise FileNotFoundError(f"eidos.json missing at {eidos_dir}")

    telos = load_telos(eidos_dir)

    task_path = _find_task(eidos_dir, task_id)
    if task_path is None:
        raise FileNotFoundError(f"task {task_id!r} not found in docket")
    task_frontmatter, task_body = _parse_task(task_path)

    guardrails = _load_guardrails(eidos_dir)
    recent_turns = _recent_praxis_turns(eidos_dir, limit=5)
    matched_plugins = _match_plugins(
        eidos_home=eidos_home,
        task_frontmatter=task_frontmatter,
        task_body=task_body,
    )

    return TaskContext(
        eidos_home=eidos_home,
        manifest=manifest,
        telos=telos,
        task_id=task_id,
        task_path=task_path,
        task_frontmatter=task_frontmatter,
        task_body=task_body,
        guardrails=guardrails,
        recent_praxis_turns=recent_turns,
        matched_plugins=matched_plugins,
    )


def _find_task(eidos_dir: Path, task_id: str) -> Path | None:
    """Look up a task in either active or completed docket dirs by id prefix."""
    for sub in ("tasks", "completed", "archive"):
        d = eidos_dir / "docket" / sub
        if not d.is_dir():
            continue
        for f in d.glob(f"{task_id}*.md"):
            return f
    return None


def _parse_task(path: Path) -> tuple[dict[str, Any], str]:
    """Read a docket task markdown with YAML front matter."""
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    front = text[4:end]
    body = text[end + 4 :].lstrip()
    try:
        fm = yaml.safe_load(front) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def _load_guardrails(eidos_dir: Path) -> list[dict[str, Any]]:
    """Load all governor guardrails (active filter applied)."""
    guard_dir = eidos_dir / "governor" / "guardrails"
    if not guard_dir.is_dir():
        return []
    results = []
    for f in sorted(guard_dir.glob("*.md")):
        fm, body = _parse_task(f)
        if fm.get("status", "active") != "active":
            continue
        results.append(
            {
                "id": fm.get("id", f.stem),
                "title": fm.get("title", ""),
                "body": body.strip(),
            }
        )
    return results


def _recent_praxis_turns(eidos_dir: Path, limit: int = 5) -> list[dict[str, Any]]:
    """Load the most recent praxis turn metadata (filename + timestamp)."""
    turns_dir = eidos_dir / "praxis" / "turns"
    if not turns_dir.is_dir():
        return []
    files = sorted(turns_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    results = []
    for f in files[:limit]:
        fm, _ = _parse_task(f)
        results.append(
            {
                "tick_id": fm.get("tick_id", f.stem),
                "summary": fm.get("summary", ""),
                "outcome": fm.get("outcome", ""),
                "path": str(f),
            }
        )
    return results


def _match_plugins(
    *,
    eidos_home: Path,
    task_frontmatter: dict[str, Any],
    task_body: str,
) -> list[dict[str, Any]]:
    """Match installed plugins against a task and return advisory references.

    Per ADR-009 §"For the loop", PERCEIVE attaches matching playbooks to
    the context bundle. The substrate decides whether to follow them;
    the engine does not enforce unless the task names the plugin in its
    frontmatter via ``required_plugins``.

    Matching rules (any rule fires → match):

    1. Task frontmatter ``required_plugins: [slug, ...]`` — explicit
       opt-in by slug. Always matches; surfaces ``required=True``.
    2. Task frontmatter ``owner_forge`` (or ``forge``) equals the
       plugin's ``owner_forge``.
    3. Task tag overlap: any task tag matches a plugin tag.
    4. Token overlap between the task's title + body and the plugin's
       ``when_to_fire`` entries (≥3 distinct ≥5-char tokens, ≥40% of the
       when_to_fire entry's tokens). Same threshold style as VERIFY's
       anti-goal check; intentionally conservative to keep noise low.
    """
    try:
        from ..plugin_runtime.store import list_plugins
    except Exception:
        return []

    plugins = list_plugins(eidos_home)
    if not plugins:
        return []

    required = {
        str(s).strip()
        for s in (task_frontmatter.get("required_plugins") or [])
        if str(s).strip()
    }
    task_owner_forge = str(
        task_frontmatter.get("owner_forge") or task_frontmatter.get("forge") or ""
    ).strip().lower()
    task_tags = {
        str(t).strip().lower()
        for t in (task_frontmatter.get("tags") or [])
        if str(t).strip()
    }
    haystack = (
        str(task_frontmatter.get("title", "")) + "\n" + (task_body or "")
    ).lower()

    matched: list[dict[str, Any]] = []
    for p in plugins:
        reasons: list[str] = []
        is_required = p.slug in required
        if is_required:
            reasons.append("listed in task.required_plugins")

        plugin_forge = str(p.manifest.get("owner_forge", "")).strip().lower()
        if task_owner_forge and plugin_forge and task_owner_forge == plugin_forge:
            reasons.append(f"owner_forge match ({plugin_forge})")

        plugin_tags = {
            str(t).strip().lower()
            for t in (p.manifest.get("tags") or [])
            if str(t).strip()
        }
        tag_overlap = task_tags & plugin_tags
        if tag_overlap:
            reasons.append(f"tag overlap: {sorted(tag_overlap)}")

        # when_to_fire token overlap
        wtf_hits: list[str] = []
        for wtf in p.manifest.get("when_to_fire", []) or []:
            wtf_str = str(wtf).lower()
            tokens = [t for t in wtf_str.split() if len(t) > 4]
            if len(tokens) < 3:
                continue
            matched_toks = [t for t in tokens if t in haystack]
            if (
                len(matched_toks) >= 3
                and len(matched_toks) / len(tokens) >= 0.4
            ):
                wtf_hits.append(wtf_str)
        if wtf_hits:
            reasons.append(f"when_to_fire token-match ({len(wtf_hits)} entries)")

        if reasons:
            matched.append(
                {
                    "slug": p.slug,
                    "scope": p.scope,
                    "path": str(p.path),
                    "playbook_path": str(p.playbook_path)
                    if p.playbook_path.is_file()
                    else None,
                    "description": p.description,
                    "required": is_required,
                    "match_reasons": reasons,
                }
            )

    # Stable ordering: required first, then by slug.
    matched.sort(key=lambda m: (not m["required"], m["slug"]))
    return matched
