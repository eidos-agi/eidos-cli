"""``eidos spawn <docket-id>`` — promote a docket task to a child eidos.

Per ADR-007 and THE-EIDOS, promotion creates a new eidos at
``<parent_home>/.eidos/children/<child-id>/.eidos/`` with its own four-field
telos, its own active forge set, and its own optional member-repo
subset. The child inherits the parent's anti-goals (the parent's
``success_when_not`` cascade into the child by default).

Per THE-POD's Solo-never-floor list, ``spawn`` is one of the operations
where Solo is not the floor — it binds future governance scope, so
escalation to at least Pair is mandatory. v1.0 emits this requirement
as a contract; the actual Pod/Pair convening waits for Rhea-class
substrate.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Annotated, Optional

import typer

from ..scope.layout import EIDOS_DIR, activate_forge, create_eidos_home
from ..scope.manifest import (
    EidosManifest,
    EidosMember,
    find_eidos_dir,
    load_manifest,
    save_manifest,
)
from ..scope.resolver import resolve_from_cwd, resolve_home_from_path
from ..scope.telos import Telos, load_telos, save_telos
from ..scope.forge_paths import init_forge_project
from ..scope.manifest import telos_hash
from ..scope.telos import telos_text
from ..orchestrator.perceive import perceive


def register(app: typer.Typer) -> None:
    @app.command("spawn")
    def cmd_spawn(
        task_id: Annotated[
            str,
            typer.Argument(
                help="Docket task ID to promote to a child eidos (e.g. TASK-0042)."
            ),
        ],
        statement: Annotated[
            str,
            typer.Option(
                "--statement",
                help=(
                    "Child telos statement. One sentence; what the child eidos "
                    "is for. Required."
                ),
            ),
        ] = "",
        success_when: Annotated[
            str,
            typer.Option(
                "--success-when",
                help="Comma-separated success_when entries for the child. Required.",
            ),
        ] = "",
        failure_when: Annotated[
            str,
            typer.Option(
                "--failure-when",
                help="Comma-separated failure_when entries for the child. Required.",
            ),
        ] = "",
        success_when_not: Annotated[
            str,
            typer.Option(
                "--success-when-not",
                help=(
                    "Comma-separated anti-goals for the child. Optional — "
                    "parent anti-goals are inherited automatically; this list "
                    "ADDS to them. Pass --no-inherit-anti-goals to skip cascade."
                ),
            ),
        ] = "",
        no_inherit_anti_goals: Annotated[
            bool,
            typer.Option(
                "--no-inherit-anti-goals",
                help="Do not cascade parent's anti-goals into the child.",
            ),
        ] = False,
        forges: Annotated[
            str,
            typer.Option(
                "--forges",
                help=(
                    "Active forge set for the child. Default: governor,docket,praxis. "
                    "A leaf-promoted-to-branch often needs less than the parent."
                ),
            ),
        ] = "governor,docket,praxis",
        members: Annotated[
            str,
            typer.Option(
                "--members",
                help=(
                    "Comma-separated member repo paths for the child. "
                    "Default: inherit parent's members."
                ),
            ),
        ] = "",
        name: Annotated[
            Optional[str],
            typer.Option(help="Child eidos name. Defaults to TASK-NNNN-<slug>."),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="JSON output.")
        ] = False,
    ) -> None:
        """Promote a docket task to a child eidos.

        Creates ``<parent_home>/.eidos/children/<child-id>/.eidos/`` with
        the child's own four-field telos contract, active forges, and
        membership. The parent task is moved into the docket's
        ``promoted/`` directory and marked with the child's id.

        **Cardinality**: per THE-POD, promotion is in the Solo-never-floor
        set. v1.0 records the cardinality contract on the child manifest
        for downstream verification; real Pair/Pod convening waits for
        Rhea-class substrate per ADR-008.
        """
        import shutil
        from ._app import emit

        parent_home = resolve_from_cwd()
        if parent_home is None:
            typer.echo(
                "error: no eidos found at or above current directory. "
                "Run `eidos define <path>` first.",
                err=True,
            )
            raise typer.Exit(code=1)
        parent_dir = find_eidos_dir(parent_home)
        parent_manifest = load_manifest(parent_dir)
        if parent_manifest is None:
            typer.echo(f"error: eidos.json missing at {parent_dir}", err=True)
            raise typer.Exit(code=1)

        # PERCEIVE the parent task to validate it exists and grab its content.
        try:
            ctx = perceive(parent_home, task_id)
        except FileNotFoundError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=1)

        # Build the child telos. Statement/success/failure must be provided.
        # success_when_not = inherited parent anti-goals (unless --no-inherit-anti-goals)
        #                  ∪ explicitly-provided child anti-goals.
        if not statement.strip():
            typer.echo(
                "error: --statement is required. The child eidos needs its own "
                "north star statement (a refinement of the parent's, scoped to "
                "this work).",
                err=True,
            )
            raise typer.Exit(code=2)

        success = [s.strip() for s in success_when.split(",") if s.strip()]
        failure = [s.strip() for s in failure_when.split(",") if s.strip()]
        explicit_anti = [s.strip() for s in success_when_not.split(",") if s.strip()]

        parent_telos = load_telos(parent_dir)
        inherited_anti: list[str] = []
        if parent_telos and not no_inherit_anti_goals:
            inherited_anti = list(parent_telos.success_when_not)

        # De-dup while preserving order: parent's anti-goals first, then child's.
        anti_goals = []
        seen = set()
        for a in inherited_anti + explicit_anti:
            if a not in seen:
                anti_goals.append(a)
                seen.add(a)

        child_telos = Telos(
            statement=statement.strip(),
            success_when=success,
            failure_when=failure,
            success_when_not=anti_goals,
        )
        errors = child_telos.validate()
        if errors:
            for e in errors:
                typer.echo(f"error: {e}", err=True)
            typer.echo(
                "\nspawn requires a fully-formed child telos. "
                "fill in the missing fields and retry.",
                err=True,
            )
            raise typer.Exit(code=2)

        # Resolve forge set.
        active_forges = [f.strip() for f in forges.split(",") if f.strip()]

        # Resolve members.
        if members.strip():
            member_paths = [m.strip() for m in members.split(",") if m.strip()]
            child_members = [EidosMember(repo=str(Path(m).resolve())) for m in member_paths]
        else:
            child_members = [
                EidosMember(repo=m.repo, role=m.role) for m in parent_manifest.members
            ]

        # Compute child id by generating a fresh uuid via manifest.new.
        import uuid

        child_id = str(uuid.uuid4())
        child_name = name or f"{task_id}-{_slug(ctx.task_frontmatter.get('title', ''))[:40]}"
        child_root = parent_dir / "children" / child_id
        child_root.mkdir(parents=True, exist_ok=True)
        child_eidos_dir = create_eidos_home(child_root)

        # Scaffold + seed forges.
        for f in active_forges:
            activate_forge(child_eidos_dir, f)
            init_forge_project(child_root, f, child_id, child_name)

        save_telos(child_eidos_dir, child_telos)

        child_manifest = EidosManifest(
            id=child_id,
            name=child_name,
            home=str(child_root),
            parent_id=parent_manifest.id,
            members=child_members,
            telos_hash=telos_hash(telos_text(child_telos)),
            active_forges=sorted(active_forges),
            created=ctx.task_frontmatter.get("created", _today()),
        )
        save_manifest(child_eidos_dir, child_manifest)

        # Mark the parent task as promoted: move into a 'promoted/' subdir of
        # the parent's docket, retaining the task content but marking it.
        promoted_dir = parent_dir / "docket" / "promoted"
        promoted_dir.mkdir(parents=True, exist_ok=True)
        promoted_target = promoted_dir / ctx.task_path.name
        if not promoted_target.exists():
            # Prepend a promotion marker into the frontmatter.
            text = ctx.task_path.read_text()
            marker = f"\npromoted_to_child_eidos: {child_id}\npromoted_at: {_today()}\n"
            if text.startswith("---\n"):
                end = text.find("\n---", 4)
                if end > 0:
                    text = text[:end] + marker + text[end:]
            promoted_target.write_text(text)
            ctx.task_path.unlink()

        # Record the spawn on the parent's pod.log.
        log = parent_dir / "pod.log"
        with log.open("a") as fh:
            fh.write(
                f"{_today()} SPAWN parent_task={task_id} child_id={child_id} "
                f"name={child_name} cardinality=pair-or-pod-required\n"
            )

        result = {
            "ok": True,
            "parent_id": parent_manifest.id,
            "promoted_task": task_id,
            "child": {
                "id": child_id,
                "name": child_name,
                "home": str(child_root),
                "active_forges": child_manifest.active_forges,
                "telos_statement": child_telos.statement,
                "inherited_anti_goals_count": len(inherited_anti),
            },
            "cardinality_contract": (
                "spawn is in THE-POD's Solo-never-floor list. The child eidos "
                "is recorded with parent_id; subsequent operations on the child "
                "should convene at least Pair when high-stakes. v1.0 records "
                "the contract; real Pair/Pod convening lands with Rhea integration."
            ),
            "next": (
                f"`eidos enter {child_root}` to open the child eidos."
            ),
        }

        if json_:
            emit(result, json_mode=True)
            return

        lines = [
            f"=== eidos spawn {task_id} ===",
            f"parent:        {parent_manifest.name}  ({parent_manifest.id[:8]}...)",
            f"child id:      {child_id}",
            f"child name:    {child_name}",
            f"child home:    {child_root}",
            f"forges:        {', '.join(child_manifest.active_forges)}",
            "",
            "child telos:",
            f"  statement:        {child_telos.statement}",
            f"  success_when:     {len(child_telos.success_when)} entries",
            f"  failure_when:     {len(child_telos.failure_when)} entries",
            f"  success_when_not: {len(child_telos.success_when_not)} entries "
            f"({len(inherited_anti)} inherited from parent)",
            "",
            "cardinality contract: Pair/Pod required for high-stakes ops on this child.",
            "",
            f"next: eidos enter {child_root}",
        ]
        emit("\n".join(lines), json_mode=False)


def _slug(s: str) -> str:
    import re

    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")


def _today() -> str:
    from datetime import date

    return date.today().isoformat()
