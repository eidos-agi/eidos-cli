"""First-class wrapper for the bundled ``learn`` plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from ..plugin_runtime.runner import PluginContext, emit_context_bundle, run_verify
from ..plugin_runtime.store import find_plugin
from ..scope.resolver import resolve_from_cwd
from .plugin import _invocation_base, _parse_kvs, install_plugin_dir


def _learn_plugin(eidos_home: Optional[Path]):
    plugin = find_plugin("learn", eidos_home)
    if plugin is None:
        typer.echo(
            "error: bundled learn plugin not found. Run `eidos plugin list` to inspect stores.",
            err=True,
        )
        raise typer.Exit(code=1)
    return plugin


def _ctx(plugin, work_dir: Path) -> PluginContext:
    return PluginContext(
        plugin=plugin,
        invocation_id=work_dir.name,
        work_dir=work_dir,
        context_json=work_dir / "context.json",
        playbook_path=work_dir / "playbook.md",
        draft_dir=work_dir / "draft",
    )


def _draft_files(draft_dir: Path) -> list[Path]:
    if not draft_dir.is_dir():
        return []
    return sorted(p for p in draft_dir.rglob("*") if p.is_file())


def _classify_run(run_dir: Path) -> dict:
    draft_dir = run_dir / "draft"
    draft_files = _draft_files(draft_dir)
    if not draft_files:
        status = "needs-draft"
    else:
        status = "ready-to-verify"
    return {
        "path": str(run_dir),
        "status": status,
        "draft_dir": str(draft_dir),
        "draft_file_count": len(draft_files),
        "suggestions": [
            f"eidos learn --status --work-dir {run_dir}",
            f"eidos learn --continue --work-dir {run_dir}",
            f"eidos learn --finish --work-dir {run_dir} --scope global",
            f"manual discard: remove {run_dir} only if the draft is intentionally abandoned",
        ],
    }


def _run_dirs(eidos_home: Optional[Path]) -> list[Path]:
    base = (
        eidos_home / ".eidos" / "praxis" / "plugin_runs"
        if eidos_home is not None
        else Path.home() / ".eidos" / "plugin_runs"
    )
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and p.name.startswith("learn-"))


def _status_payload(work_dir: Optional[str], eidos_home: Optional[Path]) -> dict:
    if work_dir:
        run_dirs = [Path(work_dir).expanduser().resolve()]
    else:
        run_dirs = _run_dirs(eidos_home)
    return {"ok": True, "runs": [_classify_run(p) for p in run_dirs]}


def _continue(work_dir: str, *, json_mode: bool) -> None:
    from ._app import emit

    eidos_home = resolve_from_cwd()
    plugin = _learn_plugin(eidos_home)
    wd = Path(work_dir).expanduser().resolve()
    if not (wd / "context.json").is_file():
        typer.echo(f"error: {wd}/context.json not found; not a learn invocation", err=True)
        raise typer.Exit(code=1)
    ctx = _ctx(plugin, wd)
    vr = run_verify(plugin, ctx)
    result = {"ok": vr.passed, "verify": vr.to_dict(), "work_dir": str(wd)}
    if json_mode:
        emit(result, json_mode=True)
        raise typer.Exit(code=0 if vr.passed else 2)
    typer.echo("=== eidos learn --continue ===")
    typer.echo(f"verify:  {'PASS' if vr.passed else 'FAIL'}")
    for reason in vr.reasons:
        typer.echo(f"  - {reason}")
    if vr.passed:
        typer.echo("")
        typer.echo("next: finish/install the draft:")
        typer.echo(f"      eidos learn --finish --work-dir {wd} --scope global")
    raise typer.Exit(code=0 if vr.passed else 2)


def _finish(work_dir: str, *, scope: str, force: bool, json_mode: bool) -> None:
    from ._app import emit

    eidos_home = resolve_from_cwd()
    plugin = _learn_plugin(eidos_home)
    wd = Path(work_dir).expanduser().resolve()
    ctx = _ctx(plugin, wd)
    vr = run_verify(plugin, ctx)
    if not vr.passed:
        result = {"ok": False, "verify": vr.to_dict(), "work_dir": str(wd)}
        if json_mode:
            emit(result, json_mode=True)
        else:
            typer.echo("=== eidos learn --finish ===")
            typer.echo("verify:  FAIL")
            for reason in vr.reasons:
                typer.echo(f"  - {reason}")
        raise typer.Exit(code=2)

    try:
        installed = install_plugin_dir(
            ctx.draft_dir, scope=scope, force=force, eidos_home=eidos_home
        )
    except (ValueError, FileExistsError) as e:
        if json_mode:
            emit({"ok": False, "error": str(e), "work_dir": str(wd)}, json_mode=True)
        else:
            typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1)

    result = {"ok": True, "verify": vr.to_dict(), "work_dir": str(wd), "install": installed}
    if json_mode:
        emit(result, json_mode=True)
        return
    typer.echo("=== eidos learn --finish ===")
    typer.echo("verify:  PASS")
    typer.echo(f"installed {installed['slug']} ({scope}) -> {installed['installed_at']}")


def register(app: typer.Typer) -> None:
    @app.command("learn")
    def cmd_learn(
        continue_: Annotated[
            bool,
            typer.Option("--continue", help="Verify an in-flight learn invocation."),
        ] = False,
        status: Annotated[
            bool,
            typer.Option("--status", help="Inspect learn invocation workspaces."),
        ] = False,
        finish: Annotated[
            bool,
            typer.Option("--finish", help="Verify and install a learn draft."),
        ] = False,
        work_dir: Annotated[
            Optional[str],
            typer.Option("--work-dir", help="Learn invocation work directory."),
        ] = None,
        scope: Annotated[
            str,
            typer.Option("--scope", help="Install scope for --finish: global or local."),
        ] = "global",
        force: Annotated[
            bool,
            typer.Option("--force", help="Overwrite an existing plugin during --finish."),
        ] = False,
        arg: Annotated[
            list[str],
            typer.Option("--arg", help="key=value pair passed into the learn context."),
        ] = [],
        json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
    ) -> None:
        """Promote praxis learning into a plugin draft, then verify or install it."""
        from ._app import emit

        selected = sum(1 for v in (continue_, status, finish) if v)
        if selected > 1:
            typer.echo("error: choose only one of --status, --continue, or --finish", err=True)
            raise typer.Exit(code=1)
        if (continue_ or finish) and work_dir is None:
            typer.echo("error: --continue and --finish require --work-dir", err=True)
            raise typer.Exit(code=1)

        eidos_home = resolve_from_cwd()
        if status:
            result = _status_payload(work_dir, eidos_home)
            if json_:
                emit(result, json_mode=True)
                return
            typer.echo("=== eidos learn --status ===")
            if not result["runs"]:
                typer.echo("(no learn runs found)")
                return
            for run in result["runs"]:
                typer.echo(f"- {run['status']} {run['path']}")
                typer.echo(f"  draft_files={run['draft_file_count']}")
                typer.echo(f"  next: {run['suggestions'][1]}")
            return

        if continue_:
            _continue(work_dir or "", json_mode=json_)
            return
        if finish:
            _finish(work_dir or "", scope=scope, force=force, json_mode=json_)
            return

        plugin = _learn_plugin(eidos_home)
        ctx = emit_context_bundle(
            plugin,
            eidos_home=eidos_home,
            args=_parse_kvs(arg),
            base_dir=_invocation_base(eidos_home),
        )
        result = {"ok": True, **ctx.to_dict()}
        if json_:
            emit(result, json_mode=True)
            return
        typer.echo("=== eidos learn ===")
        typer.echo(f"invocation:    {ctx.invocation_id}")
        typer.echo(f"work_dir:      {ctx.work_dir}")
        typer.echo(f"playbook:      {ctx.playbook_path}")
        typer.echo(f"draft dir:     {ctx.draft_dir}")
        typer.echo("")
        typer.echo("next: substrate writes draft/plugin.yaml, draft/playbook.md,")
        typer.echo("      and draft/provenance.json, then invokes:")
        typer.echo(f"      eidos learn --continue --work-dir {ctx.work_dir}")
