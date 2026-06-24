"""Top-level alias resolution per ADR-009 §6.

Scans both plugin stores at CLI startup; any plugin with ``alias: <name>``
in its manifest registers a top-level command that dispatches to
``eidos plugin run <slug>``. Aliases colliding with engine primitives are
*rejected* — the primitive wins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .store import PluginRef, list_plugins


# Reserved top-level command names from the engine. Plugins may not alias
# to any of these. Update when new primitives are added.
RESERVED_PRIMITIVES: frozenset[str] = frozenset(
    {
        "define",
        "enter",
        "status",
        "activate",
        "close",
        "tick",
        "do",
        "spawn",
        "migrate",
        "telos",
        "research",
        "governor",
        "docket",
        "praxis",
        "auth",
        "vault",
        "health",
        "doctor",
        "mcp",
        "plugin",
        "learn",
        "guide",
        "help",
        "--help",
    }
)


def discover_aliases(eidos_home: Optional[Path]) -> list[tuple[str, PluginRef]]:
    """Return ``(alias, plugin_ref)`` pairs ready to register.

    Rejects conflicts with reserved primitives silently; emits no output
    here (callers may surface via ``eidos plugin list``).
    """
    pairs: list[tuple[str, PluginRef]] = []
    seen_aliases: set[str] = set()
    for ref in list_plugins(eidos_home):
        alias = ref.alias
        if not alias:
            continue
        if alias in RESERVED_PRIMITIVES:
            continue
        if alias in seen_aliases:
            continue
        seen_aliases.add(alias)
        pairs.append((alias, ref))
    return pairs
