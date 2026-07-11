"""Overrides telos-md's ``set-north-star`` to stamp a trilogy pointer.

telos-md itself deliberately holds zero sibling knowledge — see
telos.md's own ``.converge/telos-holds-zero-sibling-knowledge-eidos-owns-the-ecosystem-map.md``,
a tested decision that cross-forge knowledge belongs to eidos, not
duplicated into every forge (a rename should touch one repo, not five).

This module is where that knowledge lives instead. It wraps telos-md's
``set-north-star`` so every file it writes carries a pointer back to the
trilogy (research.md -> governor.md -> docket.md) and to telos.md's own
docs — without telos-md itself ever knowing those tools exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

TRILOGY_REMINDER = (
    "# telos is the drift-guard for a three-tool decision loop, not a\n"
    "# standalone planning system:\n"
    "#   research.md (decide with evidence)\n"
    "#     -> governor.md (record the decision as an ADR/guardrail)\n"
    "#       -> docket.md (execute it as tasks)\n"
    "# Before acting on anything in this file, check governor's vision/ADRs/\n"
    "# guardrails and docket's task list -- this file is not the source of\n"
    "# truth for what to do, only for whether the loop is drifting.\n"
    "#\n"
    "# Docs: https://github.com/eidos-agi/research.md\n"
    "#       https://github.com/eidos-agi/governor.md\n"
    "#       https://github.com/eidos-agi/docket.md\n"
    "#       https://github.com/eidos-agi/telos.md  (this tool)\n"
    "# Use the unified `eidos` CLI (eidos research/governor/docket/telos ...)\n"
    "# rather than calling these tools directly.\n"
)

_MARKER = "# telos is the drift-guard"


def _prepend_reminder_once(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text()
    if text.startswith(_MARKER):
        return
    path.write_text(TRILOGY_REMINDER + text)


def _stamp_repo(repo_path: str) -> None:
    telos_dir = Path(repo_path) / ".telos"
    _prepend_reminder_once(telos_dir / "config.yaml")
    ns_dir = telos_dir / "north_stars"
    if ns_dir.is_dir():
        for f in ns_dir.glob("*.yaml"):
            _prepend_reminder_once(f)


def patch(telos_app: typer.Typer) -> None:
    """Replace ``telos_app``'s set-north-star command in place with a
    wrapped version that stamps every file it touches."""
    from telos_md._logic import _session as _sess
    from telos_md._logic import loop as _loop
    from telos_md.cli._app import emit

    @telos_app.command("set-north-star")
    def cmd_set_north_star(
        goal: Annotated[
            str, typer.Option(help="What this loop is trying to accomplish.")
        ],
        metric: Annotated[
            Optional[str], typer.Option(help="How success is measured. Free text.")
        ] = None,
        stop_max_iters: Annotated[
            Optional[int], typer.Option(help="Hard cap on iterations.")
        ] = None,
        stop_zero_delta_n: Annotated[
            int, typer.Option(help="Stop after N consecutive zero-delta ticks.")
        ] = 3,
        signature: Annotated[
            Optional[str], typer.Option(help="Optional hash of the work type.")
        ] = None,
        repo_path: Annotated[
            Optional[str],
            typer.Option(help="Absolute path to the repo this loop operates on."),
        ] = None,
        json_: Annotated[
            bool, typer.Option("--json", "-J", help="JSON output.")
        ] = False,
    ) -> None:
        """Register a north star -- a custody act. Returns the north_star_id."""
        resolved = _sess.resolve(repo_path)
        result = _loop.set_north_star(
            goal=goal,
            metric=metric,
            stop_max_iters=stop_max_iters,
            stop_zero_delta_n=stop_zero_delta_n,
            signature=signature,
            repo_path=resolved,
        )
        if resolved:
            _stamp_repo(resolved)
        emit(result, json_mode=json_)
