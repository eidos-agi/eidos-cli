"""Scope verbs: ``eidos define | enter | status | activate | close``.

These verbs operate on the eidos as a unit — bringing one into being, opening
a session inside one, reporting its state, activating dormant forges, and
closing it terminally.

Per the doctrine, *eidos is opt-in*: the user signals "I want the full
ceremony" by calling these verbs. The forge namespaces (``eidos research``,
``eidos governor``, etc.) are direct work surfaces that bypass this layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from ..scope import (
    EIDOS_DIR,
    FORGE_NAMES,
    EidosManifest,
    Telos,
    activate_forge,
    create_eidos_home,
    forge_is_active,
    load_manifest,
    load_telos,
    resolve_from_cwd,
    resolve_home_from_path,
    save_manifest,
    save_telos,
)
from ..scope.manifest import EidosMember, find_eidos_dir, telos_hash
from ..scope.telos import telos_text


def _parse_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _resolve_or_error(path: Optional[str]) -> Path:
    if path:
        home = resolve_home_from_path(Path(path))
        if home is None:
            typer.echo(
                f"error: no eidos found at or above {path}", err=True
            )
            raise typer.Exit(code=1)
        return home
    home = resolve_from_cwd()
    if home is None:
        typer.echo(
            "error: no eidos found at or above current directory. "
            "Run `eidos define <path>` to create one.",
            err=True,
        )
        raise typer.Exit(code=1)
    return home


def _find_git_root(start: Path) -> Path | None:
    cur = Path(start).expanduser().resolve()
    while True:
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def _scope_report(start: Path) -> dict:
    start = Path(start).expanduser().resolve()
    home = resolve_home_from_path(start)
    if home is not None:
        eidos_dir = find_eidos_dir(home)
        manifest = load_manifest(eidos_dir)
        telos = load_telos(eidos_dir)
        return {
            "resolved": True,
            "start": str(start),
            "home": str(home),
            "id": manifest.id if manifest else None,
            "name": manifest.name if manifest else None,
            "telos_statement": telos.statement if telos else None,
            "active_forges": manifest.active_forges if manifest else [],
            "member_count": len(manifest.members) if manifest else 0,
            "reason": "resolved from .eidos or .eidos-pointer",
            "candidates": [],
            "actions": [
                f"eidos enter {home}",
                f"eidos status {home}",
            ],
        }

    candidates: list[dict[str, str]] = []
    git_root = _find_git_root(start)
    if git_root is not None:
        candidates.append(
            {
                "path": str(git_root),
                "kind": "git_root",
                "action": f"eidos define {git_root}",
            }
        )

    define_target = git_root or start
    return {
        "resolved": False,
        "start": str(start),
        "home": None,
        "id": None,
        "name": None,
        "telos_statement": None,
        "active_forges": [],
        "member_count": 0,
        "reason": f"no .eidos or .eidos-pointer found at or above {start}",
        "candidates": candidates,
        "actions": [
            f"eidos define {define_target}",
            "eidos enter <existing-eidos-home>",
        ],
    }


def register(app: typer.Typer) -> None:
    @app.command("scope")
    def cmd_scope(
        path: Annotated[
            Optional[str],
            typer.Argument(help="Path to inspect. Defaults to CWD."),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """Inspect Eidos scope resolution without requiring one to exist."""
        from ._app import emit

        report = _scope_report(Path(path) if path else Path.cwd())
        if json_:
            emit(report, json_mode=True)
            return

        if report["resolved"]:
            lines = [
                "scope: resolved",
                f"home: {report['home']}",
                f"name: {report['name']}",
                f"id: {report['id']}",
                f"telos: {report['telos_statement'] or '(missing)'}",
                "actions:",
            ]
        else:
            lines = [
                "scope: unresolved",
                f"start: {report['start']}",
                f"reason: {report['reason']}",
                "actions:",
            ]
        lines.extend(f"  - {action}" for action in report["actions"])
        emit("\n".join(lines), json_mode=False)

    @app.command("define")
    def cmd_define(
        path: Annotated[
            str,
            typer.Argument(
                help=(
                    "Directory that will become the eidos home. "
                    "May or may not exist; will be created. Often a dedicated "
                    "dir like ~/projects/<name>/, separate from code repos."
                )
            ),
        ],
        name: Annotated[
            Optional[str],
            typer.Option(help="Eidos name. Defaults to the home directory's basename."),
        ] = None,
        statement: Annotated[
            str,
            typer.Option(
                "--statement",
                help="The telos statement: one sentence; what this eidos is for.",
            ),
        ] = "",
        success_when: Annotated[
            str,
            typer.Option(
                "--success-when",
                help="Comma-separated observable conditions of arrival.",
            ),
        ] = "",
        failure_when: Annotated[
            str,
            typer.Option(
                "--failure-when",
                help="Comma-separated observable conditions of real death.",
            ),
        ] = "",
        success_when_not: Annotated[
            str,
            typer.Option(
                "--success-when-not",
                help=(
                    "Comma-separated anti-goals: what this eidos refuses to become."
                ),
            ),
        ] = "",
        forges: Annotated[
            str,
            typer.Option(
                "--forges",
                help=(
                    "Comma-separated forges to activate. Default: governor,docket,praxis. "
                    "Valid: governor, research, docket, praxis."
                ),
            ),
        ] = "governor,docket,praxis",
        members: Annotated[
            str,
            typer.Option(
                "--members",
                help=(
                    "Comma-separated paths of member code repos. Each gets an "
                    ".eidos-pointer file pointing back to this eidos home."
                ),
            ),
        ] = "",
        parent_id: Annotated[
            Optional[str],
            typer.Option(
                "--parent-id",
                help="If this is a child eidos, the parent eidos's UUID.",
            ),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """Bring an eidos into being at *path*.

        Writes the four-field telos contract, the eidos.json manifest, and
        scaffolds the selected forges. Member repos receive .eidos-pointer
        files so an agent working in any of them can resolve back to this
        eidos home.

        This is the canonical ``eidos define`` per THE-EIDOS. The flags
        provide the telos fields and forge set directly (no Pod deliberation
        wired in this cut — see THE-POD's cardinality section for the
        eventual integration; the architecture supports it but substrate
        latency defers it).
        """
        from ._app import emit
        from ..scope.layout import write_pointer

        # Validate forge set first; cheap error before any disk write.
        active_forges = _parse_csv(forges)
        for f in active_forges:
            if f not in FORGE_NAMES:
                typer.echo(
                    f"error: unknown forge {f!r}; valid: {', '.join(FORGE_NAMES)}",
                    err=True,
                )
                raise typer.Exit(code=2)

        # Build and validate the telos contract.
        telos = Telos(
            statement=statement.strip(),
            success_when=_parse_csv(success_when),
            failure_when=_parse_csv(failure_when),
            success_when_not=_parse_csv(success_when_not),
        )
        errors = telos.validate()
        if errors:
            for e in errors:
                typer.echo(f"error: {e}", err=True)
            typer.echo(
                "\nthe telos contract gates eidos creation. fill in the missing fields.",
                err=True,
            )
            raise typer.Exit(code=2)

        home = Path(path).expanduser().resolve()
        if (home / EIDOS_DIR).is_dir():
            typer.echo(
                f"error: an eidos already exists at {home}. "
                "use `eidos enter` to open it, or `eidos status` to inspect.",
                err=True,
            )
            raise typer.Exit(code=1)

        eidos_dir = create_eidos_home(home)

        member_objs: list[EidosMember] = []
        for repo_path in _parse_csv(members):
            repo = Path(repo_path).expanduser().resolve()
            if not repo.is_dir():
                typer.echo(
                    f"warning: member repo {repo} is not a directory; skipping",
                    err=True,
                )
                continue
            member_objs.append(EidosMember(repo=str(repo), role="primary"))
            write_pointer(repo, home)

        for f in active_forges:
            activate_forge(eidos_dir, f)

        save_telos(eidos_dir, telos)
        manifest = EidosManifest.new(
            name=name or home.name,
            home=home,
            telos_text=telos_text(telos),
            active_forges=active_forges,
            members=member_objs,
            parent_id=parent_id,
        )
        save_manifest(eidos_dir, manifest)

        # Seed each activated forge's project config inside .eidos/<forge>/.
        # This is what makes `eidos <forge>` commands able to register and
        # operate against the eidos's storage rather than legacy locations.
        from ..scope.forge_paths import init_forge_project

        for f in active_forges:
            init_forge_project(home, f, manifest.id, manifest.name)

        result = {
            "ok": True,
            "id": manifest.id,
            "name": manifest.name,
            "home": manifest.home,
            "active_forges": manifest.active_forges,
            "members": [m.repo for m in manifest.members],
            "telos_hash": manifest.telos_hash,
        }
        emit(result, json_mode=json_)

    @app.command("enter")
    def cmd_enter(
        path: Annotated[
            Optional[str],
            typer.Argument(
                help="Path inside or naming an eidos. Defaults to walking up from CWD."
            ),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """Open a session inside an existing eidos; emit the boot briefing."""
        from ._app import emit

        home = _resolve_or_error(path)
        eidos_dir = find_eidos_dir(home)
        manifest = load_manifest(eidos_dir)
        telos = load_telos(eidos_dir)

        if manifest is None:
            typer.echo(f"error: eidos.json missing at {eidos_dir}", err=True)
            raise typer.Exit(code=1)

        if json_:
            emit(
                {
                    "id": manifest.id,
                    "name": manifest.name,
                    "home": manifest.home,
                    "active_forges": manifest.active_forges,
                    "members": [m.repo for m in manifest.members],
                    "telos": telos.to_dict() if telos else None,
                },
                json_mode=True,
            )
            return

        lines = [
            f"** {manifest.name} **",
            f"id:       {manifest.id}",
            f"home:     {manifest.home}",
        ]
        if manifest.parent_id:
            lines.append(f"parent:   {manifest.parent_id}")
        if manifest.members:
            lines.append("members:")
            for m in manifest.members:
                lines.append(f"  - {m.repo} ({m.role})")
        lines.append(f"forges:   {', '.join(manifest.active_forges) or '(none)'}")
        lines.append("")
        if telos:
            lines.append(f"telos:    {telos.statement}")
            if telos.success_when:
                lines.append("  success_when:")
                for s in telos.success_when:
                    lines.append(f"    - {s}")
            if telos.failure_when:
                lines.append("  failure_when:")
                for s in telos.failure_when:
                    lines.append(f"    - {s}")
            if telos.success_when_not:
                lines.append("  success_when_not:")
                for s in telos.success_when_not:
                    lines.append(f"    - {s}")
        else:
            lines.append("telos:    (missing)")
        emit("\n".join(lines), json_mode=False)

    @app.command("status")
    def cmd_status(
        path: Annotated[
            Optional[str],
            typer.Argument(help="Eidos home or path inside one. Defaults to CWD."),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """One-line health snapshot of the current eidos across active forges."""
        from ._app import emit

        home = _resolve_or_error(path)
        eidos_dir = find_eidos_dir(home)
        manifest = load_manifest(eidos_dir)
        telos = load_telos(eidos_dir)

        if manifest is None:
            typer.echo(f"error: eidos.json missing at {eidos_dir}", err=True)
            raise typer.Exit(code=1)

        forge_states = {
            f: "active" if forge_is_active(eidos_dir, f) else "dormant"
            for f in FORGE_NAMES
        }

        result = {
            "id": manifest.id,
            "name": manifest.name,
            "home": manifest.home,
            "telos_present": telos is not None,
            "telos_statement": telos.statement if telos else None,
            "forge_states": forge_states,
            "member_count": len(manifest.members),
        }

        if json_:
            emit(result, json_mode=True)
            return

        statement = telos.statement if telos else "(missing)"
        forges_str = " | ".join(
            f"{name}:{state}" for name, state in forge_states.items()
        )
        emit(
            f"{manifest.name}  ({manifest.id[:8]}...)\n"
            f"telos:  {statement}\n"
            f"forges: {forges_str}\n"
            f"members: {len(manifest.members)}",
            json_mode=False,
        )

    @app.command("activate")
    def cmd_activate(
        forge: Annotated[
            str,
            typer.Argument(
                help=f"Forge to activate. Valid: {', '.join(FORGE_NAMES)}."
            ),
        ],
        path: Annotated[
            Optional[str], typer.Argument(help="Eidos home. Defaults to CWD.")
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """Scaffold a previously-dormant forge for the current eidos.

        Updates the manifest's ``active_forges`` list and creates the forge
        directory under ``.eidos/<forge>/``. Idempotent.
        """
        from ._app import emit

        if forge not in FORGE_NAMES:
            typer.echo(
                f"error: unknown forge {forge!r}; valid: {', '.join(FORGE_NAMES)}",
                err=True,
            )
            raise typer.Exit(code=2)

        home = _resolve_or_error(path)
        eidos_dir = find_eidos_dir(home)
        manifest = load_manifest(eidos_dir)
        if manifest is None:
            typer.echo(f"error: eidos.json missing at {eidos_dir}", err=True)
            raise typer.Exit(code=1)

        already = forge in manifest.active_forges
        activate_forge(eidos_dir, forge)
        if not already:
            manifest.active_forges = sorted(set(manifest.active_forges) | {forge})
            save_manifest(eidos_dir, manifest)
            # Seed the forge's project config so library operations can register.
            from ..scope.forge_paths import init_forge_project

            init_forge_project(home, forge, manifest.id, manifest.name)

        emit(
            {"forge": forge, "already_active": already, "active_forges": manifest.active_forges},
            json_mode=json_,
        )

    @app.command("tick")
    def cmd_tick(
        path: Annotated[
            Optional[str], typer.Argument(help="Eidos home. Defaults to CWD.")
        ] = None,
        record: Annotated[
            bool,
            typer.Option(
                "--record",
                help="Record this tick as a praxis turn (requires praxis forge active).",
            ),
        ] = False,
        observation: Annotated[
            Optional[str],
            typer.Option(
                "--observation",
                help="One-line observation about current state (recorded with --record).",
            ),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """Praxis tick: emit a steering snapshot of the current eidos.

        Reads the telos's three trigger conditions, the docket task counts,
        and the most recent praxis turns. Emits a snapshot the agent (or
        human) can use to classify drift / arrival / failure against the
        telos.

        This is the *structural* tick — it surfaces the data needed for
        classification. The *cognitive* tick (a Pod auto-classifying
        against the triggers) is a follow-on; per the doctrine, that
        ships when substrate latency makes it affordable.
        """
        import os
        from datetime import datetime
        from ._app import emit

        home = _resolve_or_error(path)
        eidos_dir = find_eidos_dir(home)
        manifest = load_manifest(eidos_dir)
        telos = load_telos(eidos_dir)

        if manifest is None:
            typer.echo(f"error: eidos.json missing at {eidos_dir}", err=True)
            raise typer.Exit(code=1)

        # Snapshot the docket: count tasks by status.
        docket_counts: dict[str, int] = {}
        tasks_dir = eidos_dir / "docket" / "tasks"
        completed_dir = eidos_dir / "docket" / "completed"
        if tasks_dir.is_dir():
            for f in tasks_dir.glob("*.md"):
                # Cheap status read — first 5 lines should contain frontmatter.
                head = f.read_text()[:512]
                status_match = "To Do"
                if "status: In Progress" in head:
                    status_match = "In Progress"
                elif "status: Done" in head:
                    status_match = "Done"
                elif "status: blocked" in head.lower():
                    status_match = "blocked"
                docket_counts[status_match] = docket_counts.get(status_match, 0) + 1
        if completed_dir.is_dir():
            done_count = sum(1 for _ in completed_dir.glob("*.md"))
            if done_count:
                docket_counts["Done"] = docket_counts.get("Done", 0) + done_count

        # Snapshot recent praxis turns (last 3, if praxis forge active).
        recent_turns: list[dict] = []
        praxis_turns_dir = eidos_dir / "praxis" / "turns"
        if praxis_turns_dir.is_dir():
            files = sorted(praxis_turns_dir.glob("*.md"), reverse=True)[:3]
            for f in files:
                recent_turns.append(
                    {
                        "tick_id": f.stem,
                        "mtime": datetime.fromtimestamp(
                            f.stat().st_mtime
                        ).isoformat(),
                    }
                )

        snapshot = {
            "eidos": {
                "id": manifest.id,
                "name": manifest.name,
                "active_forges": manifest.active_forges,
            },
            "telos": {
                "statement": telos.statement if telos else None,
                "success_when": telos.success_when if telos else [],
                "failure_when": telos.failure_when if telos else [],
                "success_when_not": telos.success_when_not if telos else [],
            },
            "docket": docket_counts or {"(no tasks)": 0},
            "recent_praxis_turns": recent_turns,
            "advice": (
                "Compare docket + observations against the three _when conditions:\n"
                "  - matches success_when → close with outcome=reached\n"
                "  - matches failure_when → close with outcome=abandoned\n"
                "  - matches success_when_not → propose counter-action; do not celebrate\n"
                "  - matches none → on-course; continue"
            ),
            "timestamp": datetime.now().isoformat(),
        }

        if record:
            if "praxis" not in manifest.active_forges:
                typer.echo(
                    "error: --record requires the praxis forge to be active. "
                    "Run `eidos activate praxis` first.",
                    err=True,
                )
                raise typer.Exit(code=2)
            # Append a turn marker to praxis notebook.
            notebook = eidos_dir / "praxis" / "notebook.md"
            obs_line = f"\n_{observation}_" if observation else ""
            entry = (
                f"\n## tick {snapshot['timestamp']}\n"
                f"docket: {docket_counts}\n"
                f"telos: {snapshot['telos']['statement']}{obs_line}\n"
            )
            with notebook.open("a") as fh:
                fh.write(entry)
            snapshot["recorded_to"] = str(notebook)

        if json_:
            emit(snapshot, json_mode=True)
            return

        # Human-readable rendering.
        lines = [
            f"=== tick @ {snapshot['timestamp']} ===",
            f"eidos: {manifest.name}  ({manifest.id[:8]}...)",
            f"telos: {snapshot['telos']['statement'] or '(missing)'}",
            "",
            "docket:",
        ]
        for status, count in docket_counts.items():
            lines.append(f"  {status:14s}: {count}")
        lines.append("")
        lines.append("success_when:")
        for s in snapshot["telos"]["success_when"]:
            lines.append(f"  - {s}")
        lines.append("failure_when:")
        for s in snapshot["telos"]["failure_when"]:
            lines.append(f"  - {s}")
        lines.append("success_when_not:")
        for s in snapshot["telos"]["success_when_not"]:
            lines.append(f"  - {s}")
        if recent_turns:
            lines.append("")
            lines.append("recent praxis turns:")
            for t in recent_turns:
                lines.append(f"  - {t['tick_id']}  ({t['mtime']})")
        lines.append("")
        lines.append(snapshot["advice"])
        if record:
            lines.append(f"\n[recorded to {snapshot['recorded_to']}]")
        emit("\n".join(lines), json_mode=False)

    @app.command("close")
    def cmd_close(
        outcome: Annotated[
            str,
            typer.Argument(
                help="reached | abandoned | superseded — the terminal outcome."
            ),
        ],
        path: Annotated[
            Optional[str], typer.Argument(help="Eidos home. Defaults to CWD.")
        ] = None,
        notes: Annotated[
            Optional[str], typer.Option(help="Closing notes.")
        ] = None,
        superseded_by: Annotated[
            Optional[str],
            typer.Option(
                "--superseded-by",
                help="If outcome=superseded: the new telos statement or eidos id replacing this.",
            ),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="Compact JSON output.")
        ] = False,
    ) -> None:
        """Terminally close the eidos with an outcome.

        Records the close in pod.log; if superseded, marks the telos with
        a ``superseded_by`` pointer. The eidos's artifacts remain durable;
        the eidos itself is no longer active.
        """
        from ._app import emit

        valid = {"reached", "abandoned", "superseded"}
        if outcome not in valid:
            typer.echo(
                f"error: outcome must be one of {sorted(valid)}; got {outcome!r}",
                err=True,
            )
            raise typer.Exit(code=2)
        if outcome == "superseded" and not superseded_by:
            typer.echo(
                "error: outcome=superseded requires --superseded-by",
                err=True,
            )
            raise typer.Exit(code=2)

        home = _resolve_or_error(path)
        eidos_dir = find_eidos_dir(home)
        manifest = load_manifest(eidos_dir)
        telos = load_telos(eidos_dir)
        if manifest is None:
            typer.echo(f"error: eidos.json missing at {eidos_dir}", err=True)
            raise typer.Exit(code=1)

        from datetime import datetime

        log = eidos_dir / "pod.log"
        with log.open("a") as f:
            f.write(
                f"{datetime.now().isoformat()} CLOSE outcome={outcome}"
                + (f" superseded_by={superseded_by}" if superseded_by else "")
                + (f" notes={notes!r}" if notes else "")
                + "\n"
            )

        if outcome == "superseded" and telos and superseded_by:
            telos.superseded_by = superseded_by
            save_telos(eidos_dir, telos)
            # Re-hash since telos artifact changed.
            manifest.telos_hash = telos_hash(telos_text(telos))
            save_manifest(eidos_dir, manifest)

        emit(
            {
                "ok": True,
                "outcome": outcome,
                "superseded_by": superseded_by,
                "id": manifest.id,
            },
            json_mode=json_,
        )
