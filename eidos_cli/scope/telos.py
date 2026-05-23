"""The telos artifact: statement + three ``_when`` trigger lists, stored as
markdown with YAML front matter.

See ``eidos-philosophy/THE-EIDOS.md`` for the four-field contract. This module
is the storage layer; deliberation and contract verification live elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

TELOS_FILE = "telos.md"


@dataclass
class Telos:
    statement: str
    success_when: list[str] = field(default_factory=list)
    failure_when: list[str] = field(default_factory=list)
    success_when_not: list[str] = field(default_factory=list)
    superseded_by: str | None = None

    def to_dict(self) -> dict:
        d = {
            "statement": self.statement,
            "success_when": list(self.success_when),
            "failure_when": list(self.failure_when),
            "success_when_not": list(self.success_when_not),
        }
        if self.superseded_by:
            d["superseded_by"] = self.superseded_by
        return d

    def validate(self) -> list[str]:
        """Return a list of contract violations (empty list = valid)."""
        errors: list[str] = []
        if not self.statement or not self.statement.strip():
            errors.append("telos.statement is required (one sentence; what this eidos is for)")
        elif "\n" in self.statement.strip():
            errors.append("telos.statement should be a single sentence (no newlines)")
        if not self.success_when:
            errors.append(
                "telos.success_when must have at least one observable condition of arrival"
            )
        if not self.failure_when:
            errors.append(
                "telos.failure_when must have at least one observable condition of death"
            )
        if not self.success_when_not:
            errors.append(
                "telos.success_when_not must have at least one anti-goal "
                "(what this eidos refuses to become)"
            )
        return errors


def telos_path(eidos_dir: Path) -> Path:
    return Path(eidos_dir) / TELOS_FILE


def save_telos(eidos_dir: Path, telos: Telos) -> Path:
    """Write the telos artifact as markdown with YAML front matter."""
    path = telos_path(eidos_dir)
    front = yaml.safe_dump({"telos": telos.to_dict()}, sort_keys=False)
    body = _human_body(telos)
    path.write_text(f"---\n{front}---\n\n{body}")
    return path


def load_telos(eidos_dir: Path) -> Telos | None:
    """Read the telos artifact, if it exists."""
    path = telos_path(eidos_dir)
    if not path.is_file():
        return None
    text = path.read_text()
    front = _parse_front_matter(text)
    if not front or "telos" not in front:
        return None
    data = front["telos"]
    return Telos(
        statement=data.get("statement", ""),
        success_when=list(data.get("success_when", [])),
        failure_when=list(data.get("failure_when", [])),
        success_when_not=list(data.get("success_when_not", [])),
        superseded_by=data.get("superseded_by"),
    )


def telos_text(telos: Telos) -> str:
    """Canonical string form of the telos for hashing (manifest.telos_hash)."""
    return yaml.safe_dump(telos.to_dict(), sort_keys=False)


def _human_body(telos: Telos) -> str:
    lines = [f"# Telos\n\n> {telos.statement}\n"]
    lines.append("## What success looks like\n")
    for s in telos.success_when:
        lines.append(f"- {s}")
    lines.append("\n## What failure looks like\n")
    for s in telos.failure_when:
        lines.append(f"- {s}")
    lines.append("\n## What this eidos refuses to become\n")
    for s in telos.success_when_not:
        lines.append(f"- {s}")
    if telos.superseded_by:
        lines.append(f"\n_Superseded by: {telos.superseded_by}_")
    return "\n".join(lines) + "\n"


def _parse_front_matter(text: str) -> dict | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    front = text[4:end]
    return yaml.safe_load(front)
