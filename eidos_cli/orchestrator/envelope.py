"""Continuation envelope per ADR-008.

When ``eidos do <task-id>`` returns control to the calling substrate for ACT,
and the substrate later invokes ``eidos do --continue <task-id>``, the
envelope is the proof-of-continuity. It captures the state at PLAN time;
on resume it's re-verified against current state. Any drift refuses with
an explicit stale-state error rather than silently resuming.

The envelope binds:

- eidos id (which scope this work belongs to)
- task id + task version (the docket entry at PLAN time)
- plan hash (the .eidos/docket/plans/TASK-NNNN.md content at PLAN time)
- SOR routing hash (governor.sops/sor_routing.md at PLAN time)
- member repo HEAD SHAs (per eidos.json.members)
- substrate label (which agent ran PLAN — Claude Code, Codex, ...)
- evidence bundle reference (where ACT's outputs will land)

If any hash mismatches at ``--continue`` time, we refuse with a specific
reason: the user must re-run from DECOMPOSE/SPECIALIZE rather than
silently picking up a stale plan against changed state.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ContinuationEnvelope:
    eidos_id: str
    task_id: str
    task_version: str  # task file's last-modified ISO timestamp
    plan_hash: str
    sor_routing_hash: str
    member_repo_heads: dict[str, str]  # repo_path → HEAD sha
    substrate_label: str
    evidence_bundle_path: str
    created_at: str
    cardinality: str
    cardinality_rationale: str
    cardinality_triggers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContinuationEnvelope":
        return cls(**data)


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _file_sha(path: Path) -> str:
    if not path.is_file():
        return "missing"
    return _sha(path.read_text())


def _git_head(repo: Path) -> str:
    """Return the HEAD sha for a repo, or 'no-git' if not a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:12]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "no-git"


def compute_envelope(
    eidos_home: Path,
    manifest_id: str,
    members: list[dict],
    task_id: str,
    task_path: Path,
    plan_path: Path,
    sor_routing_path: Path,
    evidence_bundle_path: Path,
    substrate_label: str,
    cardinality: str,
    cardinality_rationale: str,
    cardinality_triggers: list[str],
) -> ContinuationEnvelope:
    """Compute the envelope at PLAN time."""
    eidos_home = Path(eidos_home).resolve()
    repo_heads: dict[str, str] = {}
    for m in members:
        repo = m.get("repo") if isinstance(m, dict) else getattr(m, "repo", None)
        if repo:
            repo_heads[repo] = _git_head(Path(repo))

    task_version = (
        datetime.fromtimestamp(task_path.stat().st_mtime).isoformat()
        if task_path.is_file()
        else "missing"
    )

    return ContinuationEnvelope(
        eidos_id=manifest_id,
        task_id=task_id,
        task_version=task_version,
        plan_hash=_file_sha(plan_path),
        sor_routing_hash=_file_sha(sor_routing_path),
        member_repo_heads=repo_heads,
        substrate_label=substrate_label,
        evidence_bundle_path=str(evidence_bundle_path),
        created_at=datetime.now().isoformat(),
        cardinality=cardinality,
        cardinality_rationale=cardinality_rationale,
        cardinality_triggers=cardinality_triggers,
    )


def envelope_path(eidos_dir: Path, task_id: str) -> Path:
    return eidos_dir / "docket" / "envelopes" / f"{task_id}.json"


def save_envelope(eidos_dir: Path, env: ContinuationEnvelope) -> Path:
    path = envelope_path(eidos_dir, env.task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(env.to_dict(), indent=2) + "\n")
    return path


def load_envelope(eidos_dir: Path, task_id: str) -> ContinuationEnvelope | None:
    path = envelope_path(eidos_dir, task_id)
    if not path.is_file():
        return None
    return ContinuationEnvelope.from_dict(json.loads(path.read_text()))


def verify_envelope(
    eidos_home: Path,
    saved: ContinuationEnvelope,
    task_path: Path,
    plan_path: Path,
    sor_routing_path: Path,
    members: list[dict],
) -> list[str]:
    """Compare *saved* envelope against current state; return list of drifts.

    Empty list = no drift, safe to resume. Non-empty = stale state, must
    refuse.
    """
    drifts: list[str] = []

    now_task_version = (
        datetime.fromtimestamp(task_path.stat().st_mtime).isoformat()
        if task_path.is_file()
        else "missing"
    )
    if saved.task_version != now_task_version:
        drifts.append(
            f"task version changed (was {saved.task_version}, now {now_task_version})"
        )

    now_plan = _file_sha(plan_path)
    if saved.plan_hash != now_plan:
        drifts.append(f"plan hash changed (was {saved.plan_hash}, now {now_plan})")

    now_sor = _file_sha(sor_routing_path)
    if saved.sor_routing_hash != now_sor:
        drifts.append(
            f"SOR routing hash changed (was {saved.sor_routing_hash}, now {now_sor})"
        )

    for m in members:
        repo = m.get("repo") if isinstance(m, dict) else getattr(m, "repo", None)
        if not repo:
            continue
        was = saved.member_repo_heads.get(repo)
        now = _git_head(Path(repo))
        if was and was != now:
            drifts.append(f"member repo {repo} HEAD changed (was {was}, now {now})")

    return drifts
