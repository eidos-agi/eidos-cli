"""The ``eidos.json`` manifest: identity, membership, activated forges."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .layout import EIDOS_DIR

MANIFEST_FILE = "eidos.json"


@dataclass
class EidosMember:
    repo: str
    role: str = "primary"


@dataclass
class EidosManifest:
    id: str
    name: str
    home: str
    parent_id: str | None
    members: list[EidosMember]
    telos_hash: str
    active_forges: list[str]
    created: str

    @classmethod
    def new(
        cls,
        name: str,
        home: Path,
        telos_text: str,
        active_forges: list[str],
        members: list[EidosMember] | None = None,
        parent_id: str | None = None,
    ) -> "EidosManifest":
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            home=str(Path(home).expanduser().resolve()),
            parent_id=parent_id,
            members=members or [],
            telos_hash=telos_hash(telos_text),
            active_forges=sorted(active_forges),
            created=date.today().isoformat(),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["members"] = [asdict(m) if isinstance(m, EidosMember) else m for m in self.members]
        return d


def telos_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def manifest_path(eidos_dir: Path) -> Path:
    return Path(eidos_dir) / MANIFEST_FILE


def save_manifest(eidos_dir: Path, manifest: EidosManifest) -> Path:
    path = manifest_path(eidos_dir)
    data = manifest.to_dict()
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def load_manifest(eidos_dir: Path) -> EidosManifest | None:
    path = manifest_path(eidos_dir)
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    members = [EidosMember(**m) for m in data.get("members", [])]
    return EidosManifest(
        id=data["id"],
        name=data["name"],
        home=data["home"],
        parent_id=data.get("parent_id"),
        members=members,
        telos_hash=data["telos_hash"],
        active_forges=data.get("active_forges", []),
        created=data["created"],
    )


def find_eidos_dir(home: Path) -> Path:
    """Given a home path (either the eidos home itself or its ``.eidos/`` subdir),
    return the ``.eidos/`` directory.
    """
    home = Path(home).expanduser().resolve()
    if home.name == EIDOS_DIR and home.is_dir():
        return home
    direct = home / EIDOS_DIR
    if direct.is_dir():
        return direct
    raise FileNotFoundError(
        f"no {EIDOS_DIR}/ found at {home} (and {home} is not a {EIDOS_DIR} directory)"
    )
