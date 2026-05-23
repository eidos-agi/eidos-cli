"""eidos — unified agent surface for the Eidos scope architecture.

The actual command surface is defined in :mod:`eidos_cli.cli`. This module
exposes the ``main`` console-script entry point used by ``pyproject.toml``.
"""

from __future__ import annotations

from .cli import main

__all__ = ["main"]


if __name__ == "__main__":
    main()
