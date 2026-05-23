"""Plugin runner — emit a context bundle, optionally run a plugin's verify.

Per ADR-009 §2, the engine-side of ``eidos plugin run`` is intentionally
small. The substrate (claude/agent SDK) reads the playbook + matched
context, acts, writes evidence; ``eidos plugin run --continue`` then
delegates structural checks to the plugin's ``verify.py`` if present.

The pattern mirrors ``eidos do``: PERCEIVE → emit context → substrate
acts → VERIFY → done. Plugins reuse the same envelope shape.
"""

from __future__ import annotations

import json
import importlib.util
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Optional

from .store import PluginRef


@dataclass
class PluginContext:
    """A single plugin invocation's working dir + emitted artifacts."""

    plugin: PluginRef
    invocation_id: str
    work_dir: Path
    context_json: Path
    playbook_path: Path
    draft_dir: Path  # substrate writes outputs here

    def to_dict(self) -> dict:
        return {
            "plugin": {
                "slug": self.plugin.slug,
                "scope": self.plugin.scope,
                "version": self.plugin.version,
            },
            "invocation_id": self.invocation_id,
            "work_dir": str(self.work_dir),
            "context_json": str(self.context_json),
            "playbook_path": str(self.playbook_path),
            "draft_dir": str(self.draft_dir),
        }


def emit_context_bundle(
    plugin: PluginRef,
    *,
    eidos_home: Optional[Path],
    args: dict[str, Any],
    base_dir: Path,
) -> PluginContext:
    """Materialize a context bundle for the substrate to consume.

    Writes:
      - ``<base>/<invocation>/context.json`` — args + plugin metadata +
        the eidos location (substrate uses this to read praxis turns,
        evidence, docket state itself rather than have the runtime
        pre-bundle).
      - copies playbook.md alongside for the substrate's prompt.
      - creates an empty ``draft/`` for substrate-written outputs.
    """
    invocation_id = _gen_invocation_id(plugin.slug)
    work_dir = base_dir / invocation_id
    work_dir.mkdir(parents=True, exist_ok=True)
    draft_dir = work_dir / "draft"
    draft_dir.mkdir(exist_ok=True)

    playbook_target = work_dir / "playbook.md"
    if plugin.playbook_path.is_file():
        playbook_target.write_text(plugin.playbook_path.read_text())
    else:
        playbook_target.write_text(
            f"# {plugin.slug}\n\n_(this plugin has no playbook.md; substrate must improvise)_\n"
        )

    ctx = {
        "plugin_slug": plugin.slug,
        "plugin_scope": plugin.scope,
        "plugin_version": plugin.version,
        "plugin_path": str(plugin.path),
        "invocation_id": invocation_id,
        "eidos_home": str(eidos_home) if eidos_home else None,
        "args": args,
        "draft_dir": str(draft_dir),
        "started": date.today().isoformat(),
    }
    context_json = work_dir / "context.json"
    context_json.write_text(json.dumps(ctx, indent=2, default=str))

    return PluginContext(
        plugin=plugin,
        invocation_id=invocation_id,
        work_dir=work_dir,
        context_json=context_json,
        playbook_path=playbook_target,
        draft_dir=draft_dir,
    )


@dataclass
class VerifyResult:
    passed: bool
    reasons: list[str]
    detail: dict

    def to_dict(self) -> dict:
        return {"passed": self.passed, "reasons": self.reasons, "detail": self.detail}


def run_verify(plugin: PluginRef, ctx: PluginContext) -> VerifyResult:
    """Invoke the plugin's verify.py if present.

    Contract: the plugin's ``verify.py`` must define
    ``verify(work_dir: Path, draft_dir: Path) -> dict`` returning at
    minimum ``{"passed": bool, "reasons": list[str]}`` and optionally a
    ``"detail"`` mapping. Plugins without ``verify.py`` pass trivially.
    """
    if not plugin.verify_path.is_file():
        return VerifyResult(passed=True, reasons=["no verify.py; passing trivially"], detail={})

    spec = importlib.util.spec_from_file_location(
        f"eidos_plugin_{plugin.slug}_verify", plugin.verify_path
    )
    if spec is None or spec.loader is None:
        return VerifyResult(
            passed=False,
            reasons=[f"could not load verify.py at {plugin.verify_path}"],
            detail={},
        )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:  # noqa: BLE001 — plugin code; surface verbatim
        return VerifyResult(
            passed=False,
            reasons=[f"verify.py raised at import: {type(e).__name__}: {e}"],
            detail={},
        )

    verify_fn = getattr(module, "verify", None)
    if not callable(verify_fn):
        return VerifyResult(
            passed=False,
            reasons=["verify.py does not define a callable verify(work_dir, draft_dir)"],
            detail={},
        )
    try:
        out = verify_fn(ctx.work_dir, ctx.draft_dir)
    except Exception as e:  # noqa: BLE001
        return VerifyResult(
            passed=False,
            reasons=[f"verify.py raised: {type(e).__name__}: {e}"],
            detail={},
        )
    if not isinstance(out, dict):
        return VerifyResult(
            passed=False,
            reasons=[f"verify.py returned non-dict: {type(out).__name__}"],
            detail={},
        )
    return VerifyResult(
        passed=bool(out.get("passed", False)),
        reasons=list(out.get("reasons", [])),
        detail=dict(out.get("detail", {})),
    )


def _gen_invocation_id(slug: str) -> str:
    import time

    return f"{slug}-{int(time.time() * 1000)}"
