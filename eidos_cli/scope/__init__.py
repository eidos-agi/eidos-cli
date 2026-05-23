"""Scope core: the eidos manifest, on-disk layout, telos artifact, and resolver.

This is the persistence + resolution layer for the architecture described in
``eidos-philosophy/THE-EIDOS.md``. It does not deliberate. It does not convene
Pods. It reads and writes the eidos's durable state per the contract.

Modules:

- :mod:`eidos_cli.scope.manifest` — ``eidos.json`` read/write.
- :mod:`eidos_cli.scope.layout` — ``.eidos/`` directory creation, forge
  scaffolding, ``.eidos-pointer`` file management.
- :mod:`eidos_cli.scope.telos` — the four-field telos artifact.
- :mod:`eidos_cli.scope.resolver` — ``boot_from_cwd``: walk up looking for
  ``.eidos/`` or ``.eidos-pointer``.
"""

from .layout import (
    EIDOS_DIR,
    FORGE_NAMES,
    POINTER_FILE,
    activate_forge,
    create_eidos_home,
    forge_is_active,
)
from .manifest import EidosManifest, load_manifest, save_manifest
from .resolver import resolve_from_cwd, resolve_home_from_path
from .telos import Telos, load_telos, save_telos

__all__ = [
    "EIDOS_DIR",
    "FORGE_NAMES",
    "POINTER_FILE",
    "EidosManifest",
    "Telos",
    "activate_forge",
    "create_eidos_home",
    "forge_is_active",
    "load_manifest",
    "load_telos",
    "resolve_from_cwd",
    "resolve_home_from_path",
    "save_manifest",
    "save_telos",
]
