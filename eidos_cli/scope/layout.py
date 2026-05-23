"""On-disk layout for an eidos: ``.eidos/`` directory structure, forge scaffolding."""

from __future__ import annotations

import os
from pathlib import Path

EIDOS_DIR = ".eidos"
POINTER_FILE = ".eidos-pointer"

FORGE_NAMES = ("governor", "research", "docket", "praxis")

# Per-forge subdirectory layout under .eidos/<forge>/. Mirrors the existing
# per-package directory shapes for migration compatibility.
_FORGE_LAYOUTS: dict[str, tuple[str, ...]] = {
    "governor": ("goals", "guardrails", "sops", "adr", "standards"),
    "research": ("findings", "candidates", "evaluations"),
    "docket": ("tasks", "milestones", "documents", "completed", "archive"),
    "praxis": ("turns", "patterns", "trials", "drift_categories"),
}


def create_eidos_home(home: Path) -> Path:
    """Create the ``.eidos/`` directory at *home*. Returns the eidos dir path."""
    home = Path(home).expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    eidos_dir = home / EIDOS_DIR
    eidos_dir.mkdir(exist_ok=True)
    (eidos_dir / "children").mkdir(exist_ok=True)
    return eidos_dir


def activate_forge(eidos_dir: Path, forge: str) -> Path:
    """Scaffold the directory structure for *forge* under *eidos_dir*.

    Returns the forge's root directory. Idempotent.
    """
    if forge not in _FORGE_LAYOUTS:
        raise ValueError(
            f"unknown forge {forge!r}; valid forges are {', '.join(FORGE_NAMES)}"
        )
    forge_dir = eidos_dir / forge
    forge_dir.mkdir(exist_ok=True)
    for sub in _FORGE_LAYOUTS[forge]:
        (forge_dir / sub).mkdir(exist_ok=True)
    return forge_dir


def forge_is_active(eidos_dir: Path, forge: str) -> bool:
    """Whether the forge's directory exists (i.e., has been activated)."""
    return (Path(eidos_dir) / forge).is_dir()


def write_pointer(repo_root: Path, eidos_home: Path) -> Path:
    """Write a ``.eidos-pointer`` file in *repo_root* pointing to *eidos_home*.

    The pointer is a single-line file (the absolute path to the eidos home),
    gitignored by convention so it doesn't get committed.
    """
    repo_root = Path(repo_root).expanduser().resolve()
    pointer = repo_root / POINTER_FILE
    pointer.write_text(str(Path(eidos_home).expanduser().resolve()) + "\n")
    _ensure_pointer_gitignored(repo_root)
    return pointer


def read_pointer(repo_root: Path) -> Path | None:
    """Read the eidos home from *repo_root*'s ``.eidos-pointer``, if present."""
    pointer = Path(repo_root) / POINTER_FILE
    if not pointer.is_file():
        return None
    line = pointer.read_text().strip()
    if not line:
        return None
    return Path(line)


def _ensure_pointer_gitignored(repo_root: Path) -> None:
    """If *repo_root* is a git repo, ensure ``.eidos-pointer`` is gitignored."""
    gitignore = repo_root / ".gitignore"
    if not (repo_root / ".git").exists():
        return
    existing = gitignore.read_text() if gitignore.is_file() else ""
    if POINTER_FILE in existing.split("\n"):
        return
    with gitignore.open("a") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(f"{POINTER_FILE}\n")
