"""Two-tier plugin store with local precedence.

- Eidos-local: ``<eidos_home>/.eidos/plugins/<slug>/`` — applies to one eidos.
- User-global: ``~/.eidos/plugins/<slug>/`` — applies across every eidos.

Lookup is local-first; the same slug in both lets an eidos override the
user-global definition. Per ADR-009.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


USER_GLOBAL_STORE = Path.home() / ".eidos" / "plugins"


@dataclass
class PluginRef:
    """A located plugin: its slug, where it lives, and parsed manifest."""

    slug: str
    path: Path
    scope: str  # "local" (eidos-scoped) or "global" (user-scoped)
    manifest: dict = field(default_factory=dict)

    @property
    def playbook_path(self) -> Path:
        return self.path / "playbook.md"

    @property
    def verify_path(self) -> Path:
        return self.path / "verify.py"

    @property
    def alias(self) -> Optional[str]:
        """Top-level alias if the manifest declares one."""
        v = self.manifest.get("alias")
        return str(v).strip() if v else None

    @property
    def description(self) -> str:
        return str(self.manifest.get("description", "")).strip()

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", "")).strip()


def local_store_for(eidos_home: Optional[Path]) -> Optional[Path]:
    """Return ``<eidos_home>/.eidos/plugins`` or None if not inside an eidos."""
    if eidos_home is None:
        return None
    return eidos_home / ".eidos" / "plugins"


def _load_manifest(plugin_dir: Path) -> dict:
    manifest_file = plugin_dir / "plugin.yaml"
    if not manifest_file.is_file():
        return {}
    try:
        return yaml.safe_load(manifest_file.read_text()) or {}
    except yaml.YAMLError:
        return {}


def _scan_dir(store: Path, scope: str) -> list[PluginRef]:
    if not store.is_dir():
        return []
    refs: list[PluginRef] = []
    for entry in sorted(store.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        manifest = _load_manifest(entry)
        slug = str(manifest.get("slug") or entry.name)
        refs.append(PluginRef(slug=slug, path=entry, scope=scope, manifest=manifest))
    return refs


def discover_plugins(eidos_home: Optional[Path]) -> list[PluginRef]:
    """Return all visible plugins, local first then global.

    Duplicates by slug are *kept* — the caller decides whether to dedup
    (``list_plugins`` does; ``find_plugin`` returns the first match).
    """
    out: list[PluginRef] = []
    local = local_store_for(eidos_home)
    if local is not None:
        out.extend(_scan_dir(local, "local"))
    out.extend(_scan_dir(USER_GLOBAL_STORE, "global"))
    return out


def list_plugins(eidos_home: Optional[Path]) -> list[PluginRef]:
    """De-duped view: local slug wins over global slug of the same name."""
    seen: dict[str, PluginRef] = {}
    for ref in discover_plugins(eidos_home):
        if ref.slug not in seen:
            seen[ref.slug] = ref
    return list(seen.values())


def find_plugin(slug: str, eidos_home: Optional[Path]) -> Optional[PluginRef]:
    """Resolve ``slug`` with local precedence."""
    for ref in discover_plugins(eidos_home):
        if ref.slug == slug:
            return ref
    return None
