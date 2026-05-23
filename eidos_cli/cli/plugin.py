"""``eidos plugin`` — the four-verb plugin runtime per ADR-009.

Verbs:
  - ``eidos plugin list``    — show installed plugins + their alias + scope.
  - ``eidos plugin install`` — copy a plugin directory into the chosen store.
  - ``eidos plugin run``     — emit a context bundle for the substrate; with
                                ``--continue``, run the plugin's verify.py.
  - ``eidos plugin show``    — print the plugin.yaml + a head of the playbook.

Everything plugin-related beyond these four is itself implementable as a plugin.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(name="plugin", help="Plugin runtime: list, install, run, show.")


def install_plugin_dir(source: Path, *, scope: str, force: bool, eidos_home: Optional[Path]) -> dict:
    """Install a plugin directory into the local or global store."""
    from ..plugin_runtime.store import USER_GLOBAL_STORE, local_store_for

    src = source.expanduser().resolve()
    if not src.is_dir():
        raise ValueError(f"{src} is not a directory")
    if not (src / "plugin.yaml").is_file():
        raise ValueError(f"{src}/plugin.yaml not found")

    if scope == "local":
        store = local_store_for(eidos_home)
        if store is None:
            raise ValueError(
                "--scope local requires being inside an eidos. "
                "Run inside an eidos or use --scope global."
            )
    elif scope == "global":
        store = USER_GLOBAL_STORE
    else:
        raise ValueError(f"--scope must be 'local' or 'global', got {scope!r}")

    store.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml

    try:
        manifest = _yaml.safe_load((src / "plugin.yaml").read_text()) or {}
        slug = str(manifest.get("slug") or src.name).strip()
    except Exception:
        slug = src.name
    dst = store / slug
    if dst.exists() and not force:
        raise FileExistsError(f"{dst} already exists. Use --force to overwrite.")
    if dst.exists() and force:
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return {"ok": True, "slug": slug, "scope": scope, "installed_at": str(dst)}


@app.command("list")
def cmd_list(
    candidates: Annotated[
        bool,
        typer.Option(
            "--candidates",
            help="Also list plugin candidates from the current eidos's ledger.",
        ),
    ] = False,
    json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
) -> None:
    """List installed plugins (local-first, then user-global)."""
    from ._app import emit
    from ..plugin_runtime.store import list_plugins, USER_GLOBAL_STORE
    from ..scope.resolver import resolve_from_cwd

    eidos_home = resolve_from_cwd()
    plugins = list_plugins(eidos_home)

    entries = [
        {
            "slug": p.slug,
            "scope": p.scope,
            "version": p.version,
            "alias": p.alias,
            "description": p.description,
            "path": str(p.path),
        }
        for p in plugins
    ]

    cand_entries: list[dict] = []
    if candidates and eidos_home is not None:
        cand_path = eidos_home / ".eidos" / "praxis" / "plugin_candidates.jsonl"
        if cand_path.is_file():
            for line in cand_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    cand_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    result = {
        "installed": entries,
        "global_store": str(USER_GLOBAL_STORE),
        "local_store": str(eidos_home / ".eidos" / "plugins") if eidos_home else None,
    }
    if candidates:
        result["candidates"] = cand_entries

    if json_:
        emit(result, json_mode=True)
        return

    if not entries:
        typer.echo("(no plugins installed)")
    for p in entries:
        alias = f"  alias={p['alias']}" if p["alias"] else ""
        ver = f" v{p['version']}" if p["version"] else ""
        typer.echo(f"{p['slug']:<24} [{p['scope']}]{ver}{alias}")
        if p["description"]:
            first_line = p["description"].splitlines()[0].strip()
            typer.echo(f"  {first_line}")
    if candidates:
        typer.echo(f"\ncandidates: {len(cand_entries)}")
        for c in cand_entries[:10]:
            typer.echo(f"  - {c}")


@app.command("install")
def cmd_install(
    source: Annotated[
        str,
        typer.Argument(help="Path to a plugin directory (must contain plugin.yaml)."),
    ],
    scope: Annotated[
        str,
        typer.Option(
            "--scope",
            help="Where to install: 'global' (~/.eidos/plugins/) or 'local' (this eidos).",
        ),
    ] = "global",
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite if a plugin with that slug already exists."),
    ] = False,
    json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
) -> None:
    """Copy a plugin directory into the chosen store."""
    from ._app import emit
    from ..scope.resolver import resolve_from_cwd

    try:
        result = install_plugin_dir(
            Path(source),
            scope=scope,
            force=force,
            eidos_home=resolve_from_cwd(),
        )
    except (ValueError, FileExistsError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1)
    if json_:
        emit(result, json_mode=True)
        return
    typer.echo(f"installed {result['slug']} ({scope}) → {result['installed_at']}")


@app.command("run")
def cmd_run(
    slug: Annotated[str, typer.Argument(help="Plugin slug to run.")],
    continue_: Annotated[
        bool,
        typer.Option("--continue", help="Continue an in-flight invocation; run verify."),
    ] = False,
    work_dir: Annotated[
        Optional[str],
        typer.Option(
            "--work-dir",
            help="With --continue, the invocation work_dir from the first call.",
        ),
    ] = None,
    arg: Annotated[
        list[str],
        typer.Option(
            "--arg",
            help="key=value pair passed into the plugin's context. Repeatable.",
        ),
    ] = [],
    json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
) -> None:
    """Run a plugin: emit context bundle (default) or verify (--continue)."""
    from ._app import emit
    from ..plugin_runtime.store import find_plugin
    from ..plugin_runtime.runner import emit_context_bundle, run_verify, PluginContext
    from ..scope.resolver import resolve_from_cwd

    eidos_home = resolve_from_cwd()
    plugin = find_plugin(slug, eidos_home)
    if plugin is None:
        typer.echo(
            f"error: plugin {slug!r} not found in local or global store. "
            f"Run `eidos plugin list` to see installed plugins.",
            err=True,
        )
        raise typer.Exit(code=1)

    if not continue_:
        args = _parse_kvs(arg)
        base = _invocation_base(eidos_home)
        ctx = emit_context_bundle(
            plugin, eidos_home=eidos_home, args=args, base_dir=base
        )
        result = {"ok": True, **ctx.to_dict()}
        if json_:
            emit(result, json_mode=True)
            return
        typer.echo(f"=== eidos plugin run {slug} ===")
        typer.echo(f"invocation:    {ctx.invocation_id}")
        typer.echo(f"work_dir:      {ctx.work_dir}")
        typer.echo(f"playbook:      {ctx.playbook_path}")
        typer.echo(f"draft dir:     {ctx.draft_dir}")
        typer.echo("")
        typer.echo("next: substrate reads the playbook + context.json, writes")
        typer.echo("      outputs under draft/, then invokes:")
        typer.echo(f"      eidos plugin run --continue {slug} --work-dir {ctx.work_dir}")
        return

    # --continue: run verify against an existing invocation.
    if work_dir is None:
        typer.echo("error: --continue requires --work-dir", err=True)
        raise typer.Exit(code=1)
    wd = Path(work_dir).expanduser().resolve()
    if not (wd / "context.json").is_file():
        typer.echo(f"error: {wd}/context.json not found; not a plugin invocation", err=True)
        raise typer.Exit(code=1)

    # Reconstruct minimal PluginContext for verify.
    ctx = PluginContext(
        plugin=plugin,
        invocation_id=wd.name,
        work_dir=wd,
        context_json=wd / "context.json",
        playbook_path=wd / "playbook.md",
        draft_dir=wd / "draft",
    )
    vr = run_verify(plugin, ctx)
    result = {"ok": vr.passed, "verify": vr.to_dict(), "work_dir": str(wd)}
    if json_:
        emit(result, json_mode=True)
        raise typer.Exit(code=0 if vr.passed else 2)
    typer.echo(f"=== eidos plugin run --continue {slug} ===")
    typer.echo(f"verify:  {'PASS' if vr.passed else 'FAIL'}")
    for r in vr.reasons:
        typer.echo(f"  - {r}")
    if vr.passed:
        typer.echo("")
        typer.echo("next: review the draft and install it:")
        typer.echo(f"      eidos plugin install {ctx.draft_dir}")
    raise typer.Exit(code=0 if vr.passed else 2)


@app.command("show")
def cmd_show(
    slug: Annotated[str, typer.Argument(help="Plugin slug to show.")],
    json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
) -> None:
    """Print the plugin's manifest + a head of the playbook."""
    from ._app import emit
    from ..plugin_runtime.store import find_plugin
    from ..scope.resolver import resolve_from_cwd

    eidos_home = resolve_from_cwd()
    plugin = find_plugin(slug, eidos_home)
    if plugin is None:
        typer.echo(f"error: plugin {slug!r} not found", err=True)
        raise typer.Exit(code=1)

    pb = ""
    if plugin.playbook_path.is_file():
        pb = plugin.playbook_path.read_text()

    if json_:
        emit(
            {
                "slug": plugin.slug,
                "scope": plugin.scope,
                "path": str(plugin.path),
                "manifest": plugin.manifest,
                "playbook_head": pb[:2000],
                "has_verify": plugin.verify_path.is_file(),
            },
            json_mode=True,
        )
        return

    typer.echo(f"=== plugin: {plugin.slug} ({plugin.scope}) ===")
    typer.echo(f"path:     {plugin.path}")
    typer.echo(f"version:  {plugin.version}")
    typer.echo(f"alias:    {plugin.alias or '(none)'}")
    typer.echo(f"verify:   {'yes' if plugin.verify_path.is_file() else 'no'}")
    typer.echo("")
    typer.echo("--- plugin.yaml ---")
    if (plugin.path / "plugin.yaml").is_file():
        typer.echo((plugin.path / "plugin.yaml").read_text())
    if pb:
        typer.echo("--- playbook.md (head) ---")
        head = "\n".join(pb.splitlines()[:40])
        typer.echo(head)
        if len(pb.splitlines()) > 40:
            typer.echo(f"... ({len(pb.splitlines()) - 40} more lines)")


def _parse_kvs(items: list[str]) -> dict:
    out: dict = {}
    for it in items:
        if "=" not in it:
            continue
        k, v = it.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _invocation_base(eidos_home: Optional[Path]) -> Path:
    if eidos_home is not None:
        base = eidos_home / ".eidos" / "praxis" / "plugin_runs"
    else:
        base = Path.home() / ".eidos" / "plugin_runs"
    base.mkdir(parents=True, exist_ok=True)
    return base
