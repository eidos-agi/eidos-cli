"""Forge subcommand namespaces: ``eidos telos | research | governor | docket | praxis``.

Each forge package's Typer app is mounted as a subgroup under ``eidos``. The
forge libraries continue to write to their canonical state directories
(``.telos/``, ``.research/``, ``.governor/``, ``.docket/``) — the eidos-aware
path resolution (so they write into ``<eidos_home>/.eidos/<forge>/`` when run
inside an eidos) is a separate task, tracked in the eidos's own docket once
the docket integration is wired.

For now: ``eidos research finding-create ...`` is identical to running
``research-md finding-create ...`` from the same directory. The forge
namespacing exists so the agent surface presents one tool; the storage
unification follows.

praxis-md is the renamed hone package; until that rename ships, the praxis
namespace is reserved but not wired.
"""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    # Local imports avoid pulling forge dependencies into every startup;
    # this also lets the eidos CLI start even if a forge import fails.
    try:
        from telos_md.cli import app as telos_app  # type: ignore

        from . import telos_trilogy_pointer

        telos_trilogy_pointer.patch(telos_app)
        app.add_typer(
            telos_app,
            name="telos",
            help=(
                "Telos forge — define the north star. "
                "Writes to .telos/ (legacy) or .eidos/telos.md when inside an eidos."
            ),
        )
    except Exception as e:  # pragma: no cover — defensive against missing forge
        _stub(app, "telos", e)

    try:
        from research_md.cli import app as research_app  # type: ignore

        app.add_typer(
            research_app,
            name="research",
            help="Research forge — earned, evidence-graded decisions.",
        )
    except Exception as e:  # pragma: no cover
        _stub(app, "research", e)

    try:
        from governor_md.cli import app as governor_app  # type: ignore

        app.add_typer(
            governor_app,
            name="governor",
            help="Governor forge — vision, goals, guardrails, SOPs, ADRs.",
        )
    except Exception as e:  # pragma: no cover
        _stub(app, "governor", e)

    try:
        from docket_md.cli import app as docket_app  # type: ignore

        app.add_typer(
            docket_app,
            name="docket",
            help="Docket forge — tasks, milestones, documents, Definition of Done.",
        )
    except Exception as e:  # pragma: no cover
        _stub(app, "docket", e)

    try:
        from praxis_md.cli import app as praxis_app  # type: ignore

        app.add_typer(
            praxis_app,
            name="praxis",
            help="Praxis forge — steering ticks, write-turn, notebook, status.",
        )
    except Exception as e:  # pragma: no cover
        _stub(app, "praxis", e)


def _stub(app: typer.Typer, name: str, exc: Exception) -> None:
    """If a forge library is missing or broken, register a stub that explains why
    instead of crashing the whole CLI."""
    stub_app = typer.Typer(
        no_args_is_help=True,
        add_completion=False,
        pretty_exceptions_enable=False,
    )

    @stub_app.callback(invoke_without_command=True)
    def _missing(ctx: typer.Context) -> None:
        if ctx.invoked_subcommand is None:
            typer.echo(
                f"error: forge {name!r} is not available: {type(exc).__name__}: {exc}",
                err=True,
            )
            raise typer.Exit(code=1)

    app.add_typer(
        stub_app,
        name=name,
        help=f"({name} forge unavailable: {type(exc).__name__})",
    )
