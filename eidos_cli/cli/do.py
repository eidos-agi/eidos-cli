"""``eidos do <task-id>`` — the orchestrating verb.

Per ADR-008, this walks THE-LOOP at the per-task scope. The verb itself is
structural: it loads context, classifies cardinality, emits the agent's
context bundle, waits for the calling substrate to do the work, then on
``--continue`` verifies and learns.

Two invocations:

    eidos do <task-id>                 # PERCEIVE → CARDINALITY → emit context bundle
    eidos do --continue <task-id>      # verify envelope → VERIFY → LEARN

The substrate (calling agent) does DECOMPOSE / SPECIALIZE / ACT / COMPRESS
between the two invocations, writing its outputs to the paths declared in
the context bundle.
"""

from __future__ import annotations

import json as _json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from ..orchestrator.cardinality import classify
from ..orchestrator.envelope import (
    compute_envelope,
    envelope_path,
    load_envelope,
    save_envelope,
    verify_envelope,
)
from ..orchestrator.learn import log_plugin_candidate, route_sor, write_praxis_turn
from ..orchestrator.perceive import perceive
from ..orchestrator.verify import verify as run_verify
from ..scope.manifest import find_eidos_dir, load_manifest, save_manifest
from ..scope.resolver import resolve_from_cwd, resolve_home_from_path


def register(app: typer.Typer) -> None:
    @app.command("do")
    def cmd_do(
        task_id: Annotated[
            str,
            typer.Argument(
                help="Docket task ID (e.g. TASK-0042). Looked up via the active eidos's docket."
            ),
        ],
        continue_: Annotated[
            bool,
            typer.Option(
                "--continue",
                help=(
                    "Resume after the substrate has completed ACT. Verifies the "
                    "continuation envelope; refuses on stale state."
                ),
            ),
        ] = False,
        evidence: Annotated[
            Optional[str],
            typer.Option(
                "--evidence",
                help="Path to the ACT evidence bundle (dir or file). Required for --continue.",
            ),
        ] = None,
        outcome: Annotated[
            str,
            typer.Option(
                "--outcome",
                help="improved | no-op | reverted | blocked — for --continue only.",
            ),
        ] = "improved",
        delta: Annotated[
            Optional[str],
            typer.Option(help="One-line description of what changed — for --continue only."),
        ] = None,
        substrate: Annotated[
            str,
            typer.Option(
                help="Substrate label (claude-code|codex|other). For initial invocation."
            ),
        ] = "claude-code",
        path: Annotated[
            Optional[str], typer.Option(help="Eidos home. Default: walk up from CWD.")
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="JSON output.")
        ] = False,
    ) -> None:
        """Orchestrate the loop for a docket task. See ADR-008.

        First invocation: ``eidos do TASK-NNNN``
            → loads context, classifies cardinality, writes a context bundle
              to ``.eidos/docket/contexts/TASK-NNNN/``, saves the continuation
              envelope, returns control to the substrate.

        Second invocation: ``eidos do --continue TASK-NNNN --evidence <path>``
            → verifies envelope (refuses on stale state), runs VERIFY against
              the evidence bundle, writes the praxis turn (LEARN), routes the
              SOR update, optionally logs a plugin candidate.
        """
        from ._app import emit

        # Resolve eidos.
        home = resolve_home_from_path(Path(path)) if path else resolve_from_cwd()
        if home is None:
            typer.echo(
                "error: no eidos found at or above current directory. "
                "Run `eidos define <path>` first.",
                err=True,
            )
            raise typer.Exit(code=1)
        eidos_dir = find_eidos_dir(home)

        if continue_:
            _run_continue(
                home, eidos_dir, task_id, evidence, outcome, delta, json_, emit
            )
            return

        # First invocation: PERCEIVE → CARDINALITY → emit context bundle.
        try:
            ctx = perceive(home, task_id)
        except FileNotFoundError as e:
            typer.echo(f"error: {e}", err=True)
            raise typer.Exit(code=1)

        decision = classify(ctx)

        # Write the context bundle the substrate will read.
        ctx_dir = eidos_dir / "docket" / "contexts" / task_id
        ctx_dir.mkdir(parents=True, exist_ok=True)
        ctx_file = ctx_dir / "context.json"
        ctx_file.write_text(_json.dumps(ctx.to_dict(), indent=2, default=str))

        # Per ADR-009 §"For the loop", copy matched plugin playbooks into
        # the context bundle so the substrate has them inline. Plugins are
        # advisory unless the task names them in required_plugins.
        plugins_dir = ctx_dir / "plugins"
        if ctx.matched_plugins:
            plugins_dir.mkdir(parents=True, exist_ok=True)
            for pm in ctx.matched_plugins:
                pb_src = pm.get("playbook_path")
                if not pb_src:
                    continue
                pb_src_path = Path(pb_src)
                if not pb_src_path.is_file():
                    continue
                marker = "REQUIRED" if pm.get("required") else "advisory"
                header = (
                    f"<!-- plugin: {pm['slug']} ({marker}) -->\n"
                    f"<!-- match_reasons: {pm.get('match_reasons', [])} -->\n\n"
                )
                (plugins_dir / f"{pm['slug']}.md").write_text(
                    header + pb_src_path.read_text()
                )

        # Scaffold the plan path the substrate is expected to write.
        plan_path = eidos_dir / "docket" / "plans" / f"{task_id}.md"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        if not plan_path.exists():
            plan_path.write_text(
                f"# Plan — {task_id}\n\n"
                f"<the substrate writes the DECOMPOSE/SPECIALIZE output here>\n"
            )

        # Scaffold the evidence bundle dir.
        evidence_dir = eidos_dir / "docket" / "evidence" / task_id
        evidence_dir.mkdir(parents=True, exist_ok=True)

        # Compute and save the continuation envelope.
        sor_path = eidos_dir / "governor" / "sops" / "sor_routing.md"
        env = compute_envelope(
            eidos_home=home,
            manifest_id=ctx.manifest.id,
            members=[
                {"repo": m.repo, "role": m.role} for m in ctx.manifest.members
            ],
            task_id=task_id,
            task_path=ctx.task_path,
            plan_path=plan_path,
            sor_routing_path=sor_path,
            evidence_bundle_path=evidence_dir,
            substrate_label=substrate,
            cardinality=decision.cardinality,
            cardinality_rationale=decision.rationale,
            cardinality_triggers=decision.triggers_fired,
        )
        env_path = save_envelope(eidos_dir, env)

        result = {
            "ok": True,
            "phase": "perceive+cardinality",
            "task_id": task_id,
            "cardinality": decision.to_dict(),
            "context_bundle": str(ctx_file),
            "plan_path": str(plan_path),
            "evidence_bundle": str(evidence_dir),
            "continuation_envelope": str(env_path),
            "matched_plugins": [
                {
                    "slug": pm["slug"],
                    "required": pm.get("required", False),
                    "reasons": pm.get("match_reasons", []),
                }
                for pm in ctx.matched_plugins
            ],
            "next_step": (
                f"Substrate reads context_bundle, writes plan to {plan_path}, "
                f"performs ACT writing evidence into {evidence_dir}, then runs "
                f"`eidos do --continue {task_id} --evidence {evidence_dir}`."
            ),
        }

        if json_:
            emit(result, json_mode=True)
            return

        lines = [
            f"=== eidos do {task_id} ===",
            f"eidos:        {ctx.manifest.name}  ({ctx.manifest.id[:8]}...)",
            f"task:         {ctx.task_frontmatter.get('title', '')}",
            f"cardinality:  {decision.cardinality}",
            f"  rationale:  {decision.rationale}",
        ]
        if decision.triggers_fired:
            lines.append(f"  triggers:   {', '.join(decision.triggers_fired)}")
        lines += [
            "",
            "context bundle:    " + str(ctx_file),
            "plan path:         " + str(plan_path),
            "evidence bundle:   " + str(evidence_dir),
            "continuation:      " + str(env_path),
        ]
        if ctx.matched_plugins:
            lines.append("")
            lines.append(f"matched plugins ({len(ctx.matched_plugins)}):")
            for pm in ctx.matched_plugins:
                marker = "REQUIRED" if pm.get("required") else "advisory"
                lines.append(f"  - {pm['slug']:<32}  [{marker}]")
                for r in pm.get("match_reasons", []):
                    lines.append(f"      · {r}")
            lines.append(f"  playbooks copied to: {ctx_dir / 'plugins'}")
        lines += [
            "",
            "next: substrate reads the context bundle (+ matched plugins),",
            "      decomposes, plans, acts, writes the plan and evidence, then invokes:",
            f"      eidos do --continue {task_id} --evidence {evidence_dir}",
        ]
        emit("\n".join(lines), json_mode=False)


def _run_continue(
    home: Path,
    eidos_dir: Path,
    task_id: str,
    evidence: Optional[str],
    outcome: str,
    delta: Optional[str],
    json_: bool,
    emit,
) -> None:
    """The --continue arm of eidos do."""
    if not evidence:
        typer.echo("error: --continue requires --evidence <path>", err=True)
        raise typer.Exit(code=2)

    if outcome not in ("improved", "no-op", "reverted", "blocked"):
        typer.echo(
            f"error: --outcome must be improved|no-op|reverted|blocked (got {outcome!r})",
            err=True,
        )
        raise typer.Exit(code=2)

    # Load the saved envelope.
    saved = load_envelope(eidos_dir, task_id)
    if saved is None:
        typer.echo(
            f"error: no continuation envelope for {task_id}. "
            f"Did you call `eidos do {task_id}` first?",
            err=True,
        )
        raise typer.Exit(code=1)

    # Re-load PERCEIVE context so we have the current state for verification.
    try:
        ctx = perceive(home, task_id)
    except FileNotFoundError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1)

    # Verify the envelope hasn't drifted.
    plan_path = eidos_dir / "docket" / "plans" / f"{task_id}.md"
    sor_path = eidos_dir / "governor" / "sops" / "sor_routing.md"
    drifts = verify_envelope(
        eidos_home=home,
        saved=saved,
        task_path=ctx.task_path,
        plan_path=plan_path,
        sor_routing_path=sor_path,
        members=[{"repo": m.repo, "role": m.role} for m in ctx.manifest.members],
    )
    if drifts:
        result = {
            "ok": False,
            "stale_envelope": True,
            "drifts": drifts,
            "advice": (
                "Continuation refused: state has drifted since PLAN. "
                "Re-run `eidos do <task-id>` to start a fresh loop."
            ),
        }
        if json_:
            emit(result, json_mode=True)
        else:
            lines = ["error: continuation envelope is stale; refusing."]
            for d in drifts:
                lines.append(f"  - {d}")
            lines.append("")
            lines.append(
                "  Run `eidos do " + task_id + "` again to start a fresh loop."
            )
            emit("\n".join(lines), json_mode=False)
        raise typer.Exit(code=1)

    # VERIFY against the evidence bundle.
    ev_path = Path(evidence).expanduser().resolve()
    vresult = run_verify(ctx, ev_path, saved.cardinality)

    if vresult.failed_closed:
        # High-stakes verification can't pass on Solo judgment; surface block.
        result = {
            "ok": False,
            "failed_closed": True,
            "block_reason": vresult.block_reason,
            "failures": vresult.failures,
            "advice": (
                "VERIFY blocked: high-stakes operation requires Pair or human review. "
                "Obtain an attestation, attach it to the evidence bundle, and re-run "
                "`eidos do --continue` with the augmented evidence."
            ),
        }
        emit(result, json_mode=json_)
        raise typer.Exit(code=1)

    # LEARN: write praxis turn.
    tick_id = f"{task_id}.{datetime.now().strftime('%H%M%S')}"
    failures = vresult.failures if not vresult.passed else None
    final_outcome = outcome if vresult.passed else "blocked"
    turn_path = write_praxis_turn(
        ctx,
        tick_id=tick_id,
        outcome=final_outcome,
        delta=delta,
        evidence_bundle=ev_path,
        cardinality=saved.cardinality,
        failures=failures,
    )

    # SOR routing decision.
    artifact_class = ctx.task_frontmatter.get("artifact_class")
    sor_decision = route_sor(ctx, artifact_class, ev_path)

    # Plugin META: log a candidate if the task has a stable pattern tag.
    pattern_id = ctx.task_frontmatter.get("pattern_id")
    candidate_path = None
    if pattern_id:
        candidate_path = log_plugin_candidate(
            ctx,
            pattern_id=pattern_id,
            task_class=ctx.task_frontmatter.get("title", ""),
            proposed_plugin=ctx.task_frontmatter.get("proposed_plugin", ""),
            outcome=final_outcome,
        )

    # If verify passed, move the task into completed.
    if vresult.passed:
        from docket_md import config as _dcfg
        # Trigger the eidos-aware patching used by the rest of the CLI.
        from ..scope.forge_paths import activate_for_eidos
        activate_for_eidos(home, ctx.manifest.active_forges)
        # Move task file via shutil; mirror docket-md's complete behavior.
        import shutil
        completed_dir = eidos_dir / "docket" / "completed"
        completed_dir.mkdir(parents=True, exist_ok=True)
        target = completed_dir / ctx.task_path.name
        if not target.exists():
            shutil.move(str(ctx.task_path), str(target))

    result = {
        "ok": vresult.passed,
        "phase": "verify+learn",
        "task_id": task_id,
        "outcome": final_outcome,
        "verify": vresult.to_dict(),
        "praxis_turn": str(turn_path),
        "sor_routing": sor_decision,
    }
    if candidate_path:
        result["plugin_candidate"] = str(candidate_path)

    if json_:
        emit(result, json_mode=True)
        return

    lines = [
        f"=== eidos do --continue {task_id} ===",
        f"verify:        {'PASS' if vresult.passed else 'FAIL'}",
        f"outcome:       {final_outcome}",
        f"praxis turn:   {turn_path}",
        f"sor decision:  {sor_decision.get('decision')}",
    ]
    if sor_decision.get("decision") == "route":
        lines.append(
            f"  → owner_forge: {sor_decision.get('owner_forge')}, "
            f"target: {sor_decision.get('target')}"
        )
    if candidate_path:
        lines.append(f"plugin cand.:  {candidate_path}")
    if vresult.failures:
        lines.append("failures:")
        for f in vresult.failures:
            lines.append(f"  - {f}")
    emit("\n".join(lines), json_mode=False)
