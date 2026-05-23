"""Find the eidos home from a path: walk up looking for ``.eidos/``, then ``.eidos-pointer``."""

from __future__ import annotations

from pathlib import Path

from .layout import EIDOS_DIR, POINTER_FILE, read_pointer


def resolve_home_from_path(start: Path) -> Path | None:
    """Walk up from *start* looking for an eidos home.

    Returns the eidos home directory (NOT the ``.eidos`` subdir). Returns
    ``None`` if no eidos can be resolved.

    Resolution order at each level:

    1. If ``<level>/.eidos/`` exists, *<level>* is the home.
    2. If ``<level>/.eidos-pointer`` exists, follow it to the home it names.
    3. Otherwise, ascend one directory and retry.
    """
    cur = Path(start).expanduser().resolve()
    while True:
        if (cur / EIDOS_DIR / "eidos.json").is_file():
            return cur
        pointer = read_pointer(cur)
        if pointer is not None:
            if (pointer / EIDOS_DIR / "eidos.json").is_file():
                return pointer
            # Pointer points somewhere that no longer has an eidos. Treat as
            # broken pointer; keep ascending. Could surface a warning.
        if cur.parent == cur:
            return None
        cur = cur.parent


def resolve_from_cwd() -> Path | None:
    """Convenience: resolve eidos home starting from the process CWD."""
    return resolve_home_from_path(Path.cwd())
