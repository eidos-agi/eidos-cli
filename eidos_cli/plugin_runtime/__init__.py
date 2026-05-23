"""Plugin runtime — minimal bootstrap for the recursive layer.

Per [ADR-009](../../../../../governor.md/.governor/adr/ADR-009-plugins-as-recursive-layer.md),
the engine ships four verbs (`list`, `install`, `run`, `show`) plus the
bundled `learn` plugin. Everything else plugin-related is implementable
as a plugin.
"""

from .store import (
    PluginRef,
    USER_GLOBAL_STORE,
    discover_plugins,
    find_plugin,
    list_plugins,
    local_store_for,
)
from .bootstrap import bundled_plugin_paths, install_bundled_plugins
from .runner import emit_context_bundle, run_verify
from .aliases import discover_aliases

__all__ = [
    "PluginRef",
    "USER_GLOBAL_STORE",
    "discover_plugins",
    "find_plugin",
    "list_plugins",
    "local_store_for",
    "bundled_plugin_paths",
    "install_bundled_plugins",
    "emit_context_bundle",
    "run_verify",
    "discover_aliases",
]
