"""``eidos guide [topic ...]`` — recursive AI-facing documentation.

Each guide is a bundled markdown file under ``eidos_cli/guides/``. Topic
args join with ``/``::

    eidos guide                        → guides/index.md
    eidos guide loop                   → guides/loop.md
    eidos guide loop perceive          → guides/loop/perceive.md
    eidos guide plugins promotion      → guides/plugins/promotion.md

Each page is followed by a *deeper* footer listing its children (any
``<topic>/*.md`` siblings). Every page therefore points to the next
level — discoverability is recursive and obvious by construction.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml


GUIDES_PACKAGE = "eidos_cli.guides"


def register(app: typer.Typer) -> None:
    @app.command("guide")
    def cmd_guide(
        topic: Annotated[
            Optional[list[str]],
            typer.Argument(
                help=(
                    "Topic path. Examples: 'loop', 'loop perceive', "
                    "'plugins promotion'. No args → top-level index."
                ),
            ),
        ] = None,
        list_: Annotated[
            bool,
            typer.Option(
                "--list", help="List all available guide paths (one per line)."
            ),
        ] = False,
    ) -> None:
        """Read the AI-facing guide. Drill via ``eidos guide <topic> [<sub>...]``."""
        root = _guides_root()
        if list_:
            for rel in _walk_all(root):
                typer.echo(rel)
            return

        path_parts = list(topic or [])
        page = _resolve(root, path_parts)
        if page is None:
            typer.echo(
                f"error: no guide at {' '.join(path_parts) or '(root)'}.\n"
                f"       Run `eidos guide --list` to see all available pages.",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(_render(page, path_parts, root))


def _guides_root() -> Path:
    """Return the on-disk path to the bundled guides directory."""
    pkg = resources.files(GUIDES_PACKAGE)
    return Path(str(pkg))


def _resolve(root: Path, parts: list[str]) -> Optional[Path]:
    """Resolve a topic-path to its markdown file."""
    if not parts:
        idx = root / "index.md"
        return idx if idx.is_file() else None
    candidate = root.joinpath(*parts).with_suffix(".md")
    if candidate.is_file():
        return candidate
    # Fall back to <topic>/index.md if directory exists without sibling file.
    dir_candidate = root.joinpath(*parts) / "index.md"
    if dir_candidate.is_file():
        return dir_candidate
    return None


def _children(root: Path, parts: list[str]) -> list[tuple[str, str]]:
    """Return ``(slug, title)`` for each child page beneath ``parts``."""
    children_dir = root.joinpath(*parts) if parts else root
    if not children_dir.is_dir():
        return []
    out: list[tuple[str, str]] = []
    for entry in sorted(children_dir.iterdir()):
        if entry.is_file() and entry.suffix == ".md" and entry.stem != "index":
            slug = entry.stem
            title = _read_title(entry)
            out.append((slug, title))
        elif entry.is_dir() and (entry / "index.md").is_file():
            slug = entry.name
            title = _read_title(entry / "index.md")
            out.append((slug, title))
    return out


def _read_title(p: Path) -> str:
    """Read the page's H1 title or the YAML front-matter ``title``."""
    text = p.read_text()
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end > 0:
            try:
                fm = yaml.safe_load(text[4:end]) or {}
                if isinstance(fm, dict) and fm.get("title"):
                    return str(fm["title"])
            except yaml.YAMLError:
                pass
            text = text[end + 4 :].lstrip()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line:
            return line[:80]
    return p.stem


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    return text[end + 4 :].lstrip()


def _render(page: Path, parts: list[str], root: Path) -> str:
    body = _strip_frontmatter(page.read_text()).rstrip()
    # Compute children. For ``loop.md`` the children dir is ``loop/``.
    children = _children(root, parts)
    breadcrumb = "eidos guide " + " ".join(parts) if parts else "eidos guide"

    header = (
        "═══════════════════════════════════════════════════════════════════════════\n"
        f"  {breadcrumb}\n"
        "═══════════════════════════════════════════════════════════════════════════\n"
    )

    footer_lines = [
        "",
        "═══════════════════════════════════════════════════════════════════════════",
        "  deeper",
        "═══════════════════════════════════════════════════════════════════════════",
    ]
    if children:
        for slug, title in children:
            cmd = breadcrumb + f" {slug}"
            footer_lines.append(f"  {cmd:<48}  — {title}")
    else:
        footer_lines.append("  (this is a leaf page — no deeper drill-down)")

    # Always offer the way back up and the listing.
    footer_lines.append("")
    if parts:
        up = parts[:-1]
        up_cmd = "eidos guide" + ((" " + " ".join(up)) if up else "")
        footer_lines.append(f"  up:    {up_cmd}")
    footer_lines.append("  index: eidos guide")
    footer_lines.append("  all:   eidos guide --list")

    return header + body + "\n" + "\n".join(footer_lines) + "\n"


def _walk_all(root: Path) -> list[str]:
    """Recursively list every guide path (space-joined)."""
    out: list[str] = []

    def _walk(d: Path, prefix: list[str]) -> None:
        for entry in sorted(d.iterdir()):
            if entry.is_file() and entry.suffix == ".md":
                if entry.stem == "index":
                    label = " ".join(prefix) if prefix else "(root)"
                else:
                    label = " ".join(prefix + [entry.stem])
                out.append(label)
            elif entry.is_dir() and not entry.name.startswith("_"):
                _walk(entry, prefix + [entry.name])

    _walk(root, [])
    return out
