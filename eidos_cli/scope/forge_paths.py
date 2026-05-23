"""Eidos-aware path resolution for forge libraries.

When ``eidos <forge>`` commands run inside an eidos, the forge libraries
should write to ``<eidos_home>/.eidos/<forge>/`` rather than the legacy
``<cwd>/.<forge>/`` location. This module makes that happen by:

1. Monkey-patching each forge's state-dir constant (``CONFIG_DIR``,
   ``GOVERNOR_DIR``, ``DOCKET_DIR``) to point at ``.eidos/<forge>``.
2. Ensuring the forge's project config file exists at the eidos's
   location (creating with the eidos's identity if missing).
3. Pre-registering the forge's project so the eidos's uuid is the
   project_id for that forge.

This is a transitional implementation: the doctrine (THE-EIDOS) commits
to forge libraries being eidos-aware, but currently each forge library
walks for its legacy ``.research/``, ``.governor/``, ``.docket/`` dir.
Patching their constants at runtime achieves the same effect without
requiring upstream changes to the forge libraries. TASK in the eidos's
own docket tracks the longer-term move to library-level eidos-awareness.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from .layout import EIDOS_DIR

# Forge-name → (module path, constant name, default value).
# Each forge library exposes its state-dir as a module-level constant.
_FORGE_CONSTANTS: dict[str, tuple[str, str, str]] = {
    "research": ("research_md.config", "CONFIG_DIR", ".research"),
    "governor": ("governor_md.constants", "GOVERNOR_DIR", ".governor"),
    "docket": ("docket_md.config", "DOCKET_DIR", ".docket"),
}


def _set_constant(module_path: str, name: str, value: str) -> None:
    """Import a module and override one of its constants."""
    import importlib

    mod = importlib.import_module(module_path)
    setattr(mod, name, value)


_FORGE_CONFIG_FILES: dict[str, str] = {
    "research": "research.json",
    "governor": "config.yaml",
    "docket": "docket.json",
}


def activate_for_eidos(eidos_home: Path, active_forges: list[str]) -> None:
    """Patch each active forge's state-dir constant to point at the eidos.

    After this call, ``register_project(<eidos_home>)`` for any forge in
    *active_forges* will look for / write to ``<eidos_home>/.eidos/<forge>/``
    instead of the legacy ``<eidos_home>/.<forge>/``.

    Only patches forges whose eidos-aware config file actually exists. For
    forges where the eidos-aware config is missing (e.g., an eidos defined
    before the auto-seeding patch landed), this leaves the forge on its
    legacy ``.<forge>/`` path. Idempotent. Safe to call repeatedly.
    """
    eidos_home = Path(eidos_home).expanduser().resolve()
    for forge in active_forges:
        if forge not in _FORGE_CONSTANTS:
            continue
        config_name = _FORGE_CONFIG_FILES.get(forge)
        if config_name is None:
            continue
        eidos_aware_config = eidos_home / EIDOS_DIR / forge / config_name
        if not eidos_aware_config.is_file():
            # Eidos-aware config not seeded yet — leave the forge on its
            # legacy path so commands keep working against .<forge>/.
            continue
        module_path, const_name, _legacy = _FORGE_CONSTANTS[forge]
        _set_constant(module_path, const_name, f"{EIDOS_DIR}/{forge}")


def init_forge_project(
    eidos_home: Path,
    forge: str,
    eidos_id: str,
    eidos_name: str,
) -> None:
    """Write the forge's project config file inside ``<eidos_home>/.eidos/<forge>/``
    so the forge library can register and operate against it.

    For docket-md, this is ``docket.json``; for research-md, ``.research/research.json``
    (note research-md nests its config one deeper); for governor-md,
    ``config.yaml`` with an id field.

    The forge's project_id is set to the eidos's uuid so the trilogy verbs
    can be invoked without the user typing --project-id every time once
    the auto-resolution helpers are wired (a separate task).
    """
    eidos_home = Path(eidos_home).expanduser().resolve()
    forge_dir = eidos_home / EIDOS_DIR / forge
    forge_dir.mkdir(parents=True, exist_ok=True)

    if forge == "docket":
        cfg = forge_dir / "docket.json"
        if not cfg.exists():
            cfg.write_text(
                json.dumps(
                    {
                        "id": eidos_id,
                        "version": "0.1.0",
                        "project": eidos_name,
                        "created": _today(),
                        "docket_path": ".eidos/docket",
                    },
                    indent=2,
                )
                + "\n"
            )

    elif forge == "research":
        cfg = forge_dir / "research.json"
        if not cfg.exists():
            cfg.write_text(
                json.dumps(
                    {
                        "id": eidos_id,
                        "version": "0.1.0",
                        "projectName": eidos_name,
                        "phase": "research",
                        "transitions": [
                            {"phase": "research", "date": _today()}
                        ],
                    },
                    indent=2,
                )
                + "\n"
            )

    elif forge == "governor":
        cfg = forge_dir / "config.yaml"
        if not cfg.exists():
            cfg.write_text(
                f"id: {eidos_id}\n"
                f"project: {eidos_name}\n"
                f"created: {_today()}\n"
            )

    # praxis: nothing to seed yet — praxis-md rename pending


def _today() -> str:
    from datetime import date

    return date.today().isoformat()
