"""``eidos migrate`` — consolidate legacy forge state directories into ``.eidos/``.

When the trilogy + telos + hone shipped as separate packages, each wrote to
its own top-level state dir (``.telos/``, ``.research/``, ``.governor/``,
``.docket/``, ``.hone/``) per repo. The scope architecture in ADR-007
unifies these under ``<eidos_home>/.eidos/<forge>/`` for a single per-eidos
home.

``eidos migrate`` is the consumer migration verb. Run inside an existing
eidos to move legacy directories into the unified layout. Idempotent:
re-running after a successful migrate is a no-op.

For projects not yet defined as eidi, the verb prints guidance instead of
auto-defining — multi-repo handling is the user's call.

Dry-run by default; pass ``--apply`` to actually move files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

# Map legacy state-dir name → unified forge name. ``.hone`` migrates to the
# ``praxis`` forge per ADR-007's hone → praxis-md rename.
_LEGACY_DIRS: dict[str, str] = {
    ".telos": "telos",
    ".research": "research",
    ".governor": "governor",
    ".docket": "docket",
    ".hone": "praxis",
    ".praxis": "praxis",
}


def register(app: typer.Typer) -> None:
    @app.command("migrate")
    def cmd_migrate(
        path: Annotated[
            Optional[str],
            typer.Argument(
                help="Path to migrate. Defaults to walking up from CWD to find an eidos."
            ),
        ] = None,
        apply: Annotated[
            bool,
            typer.Option(
                "--apply",
                help="Actually move files. Without this, dry-run prints the plan.",
            ),
        ] = False,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """Consolidate legacy ``.telos / .research / .governor / .docket / .hone``
        directories into ``<eidos_home>/.eidos/<forge>/``.

        Must be run inside an existing eidos (one defined via ``eidos define``).
        If you're not yet in an eidos, run ``eidos define <path>`` first, then
        ``eidos migrate``.
        """
        from ._app import emit
        from ..scope.layout import EIDOS_DIR, activate_forge
        from ..scope.manifest import (
            EidosManifest,
            find_eidos_dir,
            load_manifest,
            save_manifest,
        )
        from ..scope.resolver import resolve_from_cwd, resolve_home_from_path
        from ..scope.forge_paths import init_forge_project

        # Resolve the eidos home.
        if path:
            home = resolve_home_from_path(Path(path))
        else:
            home = resolve_from_cwd()
        if home is None:
            typer.echo(
                "error: no eidos found at or above the given path.\n"
                "       Run `eidos define <path>` to create one, then re-run migrate.",
                err=True,
            )
            raise typer.Exit(code=1)

        eidos_dir = find_eidos_dir(home)
        manifest = load_manifest(eidos_dir)
        if manifest is None:
            typer.echo(f"error: eidos.json missing at {eidos_dir}", err=True)
            raise typer.Exit(code=1)

        # Build the plan: for each legacy dir at home, what to do.
        plan: list[dict] = []
        for legacy_name, forge_name in _LEGACY_DIRS.items():
            legacy_dir = home / legacy_name
            if not legacy_dir.is_dir():
                continue
            target_forge_dir = eidos_dir / forge_name
            existing_files = (
                [p.name for p in target_forge_dir.iterdir()]
                if target_forge_dir.is_dir()
                else []
            )
            # Files we'd move: top-level entries in legacy_dir.
            entries = sorted(p.name for p in legacy_dir.iterdir())
            plan.append(
                {
                    "legacy_dir": str(legacy_dir),
                    "forge": forge_name,
                    "target": str(target_forge_dir),
                    "entries_to_move": entries,
                    "target_already_has": existing_files,
                    "forge_in_manifest": forge_name in manifest.active_forges,
                }
            )

        if not plan:
            result = {
                "ok": True,
                "applied": False,
                "message": "nothing to migrate; no legacy dirs found at eidos home",
                "home": str(home),
            }
            emit(result, json_mode=json_)
            return

        if not apply:
            result = {
                "ok": True,
                "applied": False,
                "home": str(home),
                "plan": plan,
                "hint": "rerun with --apply to actually move files",
            }
            if json_:
                emit(result, json_mode=True)
                return
            lines = [f"=== eidos migrate (dry-run) @ {home} ==="]
            for item in plan:
                lines.append(f"\n{item['legacy_dir']} → {item['target']}")
                lines.append(f"  forge:                 {item['forge']}")
                lines.append(
                    f"  active in manifest:    {'yes' if item['forge_in_manifest'] else 'no (will activate)'}"
                )
                lines.append(f"  entries to move:       {item['entries_to_move']}")
                if item["target_already_has"]:
                    lines.append(
                        f"  target already has:    {item['target_already_has']} "
                        "(entries will be merged; conflicts skipped)"
                    )
            lines.append("\n(rerun with --apply to execute)")
            emit("\n".join(lines), json_mode=False)
            return

        # Apply the plan.
        applied: list[dict] = []
        for item in plan:
            legacy = Path(item["legacy_dir"])
            target = Path(item["target"])
            target.mkdir(parents=True, exist_ok=True)

            moved, skipped_conflicts = _merge_dir(legacy, target)
            # Activate the forge in the manifest if not already.
            if item["forge"] not in manifest.active_forges and item["forge"] in (
                "telos",
                "research",
                "governor",
                "docket",
                "praxis",
            ):
                # Scaffold and seed the forge config if missing.
                activate_forge(eidos_dir, item["forge"])
                init_forge_project(home, item["forge"], manifest.id, manifest.name)
                manifest.active_forges = sorted(
                    set(manifest.active_forges) | {item["forge"]}
                )

            # If the legacy dir is now empty (or only ghost subdirs), remove it.
            try:
                if not any(legacy.rglob("*")):
                    shutil.rmtree(legacy)
                    legacy_removed = True
                else:
                    legacy_removed = False
            except Exception:
                legacy_removed = False

            applied.append(
                {
                    "forge": item["forge"],
                    "moved": moved,
                    "skipped_conflicts": skipped_conflicts,
                    "legacy_removed": legacy_removed,
                }
            )

        # Persist any manifest changes.
        save_manifest(eidos_dir, manifest)

        emit(
            {"ok": True, "applied": True, "home": str(home), "results": applied},
            json_mode=json_,
        )


def _merge_dir(src: Path, dst: Path) -> tuple[int, list[str]]:
    """Move src's contents into dst recursively.

    Behavior:
      - File exists in dst: skipped (counted as conflict).
      - Dir exists in dst (e.g. an empty placeholder scaffolded at activate
        time): recurse into it, merging src's children into dst's same-name dir.
      - Otherwise: move.

    Returns (moved_count, conflict_paths).
    """
    moved = 0
    conflicts: list[str] = []

    def _walk(s: Path, d: Path, rel: str = "") -> None:
        nonlocal moved
        d.mkdir(parents=True, exist_ok=True)
        for item in s.iterdir():
            target = d / item.name
            sub_rel = f"{rel}/{item.name}" if rel else item.name
            if target.exists():
                if target.is_dir() and item.is_dir():
                    _walk(item, target, sub_rel)
                else:
                    conflicts.append(sub_rel)
                continue
            shutil.move(str(item), str(target))
            moved += 1

    _walk(src, dst)
    return moved, conflicts
