"""First-run bootstrap: copy wheel-bundled plugins into ``~/.eidos/plugins/``.

The bundled set is whatever ships under ``eidos_cli/plugins/``. v1.0
ships exactly one: ``learn``. Per ADR-009 §5, after copy the user owns
the file — subsequent ``eidos-cli`` upgrades do not overwrite. Drift
between bundled and installed versions is surfaced via
``eidos plugin show <slug>``.
"""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

from .store import USER_GLOBAL_STORE


def bundled_plugin_paths() -> list[Path]:
    """Return paths to every plugin directory bundled in the wheel."""
    plugins_root = resources.files("eidos_cli.plugins")
    out: list[Path] = []
    for entry in plugins_root.iterdir():  # type: ignore[attr-defined]
        if entry.is_dir() and (entry / "plugin.yaml").is_file():
            out.append(Path(str(entry)))
    return out


def install_bundled_plugins(*, force: bool = False) -> list[tuple[str, str]]:
    """Copy bundled plugins to the user-global store.

    Returns a list of ``(slug, action)`` where ``action`` is one of
    ``installed``, ``skipped-exists``, ``overwrote`` (when ``force``).
    """
    USER_GLOBAL_STORE.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str]] = []
    for src in bundled_plugin_paths():
        slug = src.name
        dst = USER_GLOBAL_STORE / slug
        if dst.exists() and not force:
            results.append((slug, "skipped-exists"))
            continue
        if dst.exists() and force:
            shutil.rmtree(dst)
            shutil.copytree(src, dst)
            results.append((slug, "overwrote"))
        else:
            shutil.copytree(src, dst)
            results.append((slug, "installed"))
    return results
