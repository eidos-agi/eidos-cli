"""Typer root + shared output formatter for eidos-cli."""

from __future__ import annotations

import json as _json

import typer

app = typer.Typer(
    name="eidos",
    help=(
        "═══════════════════════════════════════════════════════════════════════════\n"
        "  NEW HERE?  →  RUN:  eidos guide\n"
        "  The guide drills recursively. Every page lists deeper pages.\n"
        "═══════════════════════════════════════════════════════════════════════════\n"
        "\n"
        "eidos — unified agent surface for the Eidos scope architecture.\n"
        "\n"
        "SCOPE:        eidos scope | define ... | enter | status | health | doctor | activate | close | closeout | cleanup | ship(manifest) | spawn | tick\n"
        "LOOP:         eidos do <task-id>          (PERCEIVE → CARDINALITY → … → LEARN)\n"
        "FORGES:       eidos telos ... | research ... | governor ... | docket ... | praxis ...\n"
        "PLUGINS:      eidos plugin list | install | run | show     |   eidos learn\n"
        "GUIDE:        eidos guide [topic [sub [...]]]              ← read this first\n"
        "AUTH:         eidos auth login | logout | status\n"
        "VAULT:        eidos vault get | set | list | rm | keys ...\n"
        "OMNI:         eidos omni [write] --tenant reeves\n"
        "MCP:          eidos mcp serve\n"
        "MIGRATE:      eidos migrate\n"
        "\n"
        "See THE-EIDOS in eidos-philosophy/ for the doctrine. The runtime guide is at\n"
        "`eidos guide` — read it the moment you land here."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


@app.callback()
def _root_callback() -> None:
    """Apply eidos-aware path resolution if CWD is inside an eidos.

    When invoked inside an eidos, monkey-patches each active forge library's
    state-dir constant to point at ``<eidos_home>/.eidos/<forge>/`` rather
    than the legacy ``.<forge>/`` location. This is what makes
    ``eidos docket task-create`` write into the eidos's own docket forge.

    Outside an eidos, this is a no-op: forge libraries use their legacy
    paths and operate as standalone tools.
    """
    from ..scope.manifest import load_manifest
    from ..scope.resolver import resolve_from_cwd
    from ..scope.forge_paths import activate_for_eidos

    eidos_home = resolve_from_cwd()
    if eidos_home is None:
        return
    eidos_dir = eidos_home / ".eidos"
    if not eidos_dir.is_dir():
        return
    manifest = load_manifest(eidos_dir)
    if manifest is None:
        return
    activate_for_eidos(eidos_home, manifest.active_forges)


def emit(result, *, json_mode: bool) -> None:
    """Print a result. JSON mode is compact (one line); otherwise human prose."""
    if json_mode:
        typer.echo(_json.dumps(result, default=str))
        return
    if isinstance(result, str):
        typer.echo(result)
    elif isinstance(result, (dict, list)):
        typer.echo(_json.dumps(result, indent=2, default=str))
    else:
        typer.echo(str(result))


def _wire() -> None:
    """Mount the subcommand groups. Local imports keep startup light."""
    from . import auth as _auth_cmd
    from . import cleanup as _cleanup_cmd
    from . import closeout as _closeout_cmd
    from . import do as _do_cmd
    from . import forges as _forges_cmd
    from . import guide as _guide_cmd
    from . import health as _health_cmd
    from . import learn as _learn_cmd
    from . import mcp as _mcp_cmd
    from . import migrate as _migrate_cmd
    from . import omni as _omni_cmd
    from . import plugin as _plugin_cmd
    from . import route as _route_cmd
    from . import ship as _ship_cmd
    from . import scope as _scope_cmd
    from . import spawn as _spawn_cmd
    from . import vault as _vault_cmd

    # Scope verbs at top level — the architectural surface of eidos-cli.
    _scope_cmd.register(app)
    _migrate_cmd.register(app)
    _closeout_cmd.register(app)
    _cleanup_cmd.register(app)
    _ship_cmd.register(app)
    _do_cmd.register(app)
    _route_cmd.register(app)
    _spawn_cmd.register(app)
    _guide_cmd.register(app)
    _learn_cmd.register(app)
    _omni_cmd.register(app)

    # Forge namespaces — direct access to the five forge libraries.
    _forges_cmd.register(app)

    app.add_typer(_auth_cmd.app, name="auth", help="Platform credentials.")
    app.add_typer(_vault_cmd.app, name="vault", help="Secrets stored in eidos-vault.")
    app.add_typer(_mcp_cmd.app, name="mcp", help="MCP server operations.")
    app.add_typer(
        _plugin_cmd.app, name="plugin", help="Plugin runtime (ADR-009)."
    )
    _health_cmd.register(app)

    # First-run bootstrap: install wheel-bundled plugins into ~/.eidos/plugins/
    # if missing. Idempotent; subsequent CLI upgrades do not overwrite user
    # edits. Failures here are non-fatal — the engine works without plugins.
    try:
        from ..plugin_runtime.bootstrap import install_bundled_plugins

        install_bundled_plugins()
    except Exception:
        pass

    # Top-level command aliasing per ADR-009 §6: scan installed plugins and
    # register a dispatcher for each declared alias that does not collide
    # with an engine primitive.
    try:
        from ..plugin_runtime.aliases import discover_aliases
        from ..scope.resolver import resolve_from_cwd

        _register_plugin_aliases(discover_aliases(resolve_from_cwd()))
    except Exception:
        pass


def _register_plugin_aliases(pairs) -> None:
    """For each ``(alias, ref)``, register a top-level command that
    dispatches to ``eidos plugin run <slug>``. The alias accepts repeatable
    ``--arg key=value`` pairs and a ``--continue --work-dir`` form.

    Uses typer's classic default-form options so the dispatcher does not
    rely on ``Annotated`` resolution at typer-introspection time (the
    closure's globals are this module, not the local scope).
    """
    for alias, ref in pairs:
        slug = ref.slug
        description = (
            ref.description.splitlines()[0] if ref.description else f"Plugin: {slug}"
        )

        def _make(_slug: str):
            def _dispatch(
                continue_: bool = typer.Option(
                    False, "--continue", help="Continue an in-flight invocation."
                ),
                work_dir: str = typer.Option(None, "--work-dir"),
                arg: list[str] = typer.Option(
                    [], "--arg", help="key=value pairs, repeatable."
                ),
                json_: bool = typer.Option(False, "--json", "-J", help="JSON output."),
            ) -> None:
                from . import plugin as _plug

                _plug.cmd_run(
                    slug=_slug,
                    continue_=continue_,
                    work_dir=work_dir,
                    arg=arg,
                    json_=json_,
                )

            return _dispatch

        app.command(alias, help=f"[plugin] {description}")(_make(slug))


_wire()


def main() -> None:
    """Console-script entry point (``eidos``)."""
    import sys

    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
    except (typer.Exit, typer.Abort, SystemExit):
        raise
    except Exception as e:
        typer.echo(f"error: {type(e).__name__}: {e}", err=True)
        sys.exit(1)
