"""Fleet cleanup audit for portable Eidos/Codex plugin software."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=10)


def _is_git_repo(path: Path) -> bool:
    return _run(["git", "rev-parse", "--show-toplevel"], path).returncode == 0


def _git_root(path: Path) -> Path | None:
    proc = _run(["git", "rev-parse", "--show-toplevel"], path)
    return Path(proc.stdout.strip()).resolve() if proc.returncode == 0 else None


def _git_state(path: Path) -> dict[str, Any]:
    root = _git_root(path)
    if root is None:
        return {"is_git": False}
    porcelain = _run(["git", "status", "--porcelain=v1"], root).stdout.splitlines()
    branch = _run(["git", "branch", "--show-current"], root).stdout.strip()
    upstream_proc = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root)
    upstream = upstream_proc.stdout.strip() if upstream_proc.returncode == 0 else ""
    ahead = behind = None
    if upstream:
        counts = _run(["git", "rev-list", "--left-right", "--count", f"HEAD...{upstream}"], root)
        if counts.returncode == 0:
            left, right = counts.stdout.strip().split()
            ahead, behind = int(left), int(right)
    return {
        "is_git": True,
        "root": str(root),
        "branch": branch,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "clean": not porcelain,
        "dirty_count": len(porcelain),
        "examples": porcelain[:10],
        "synced": bool(upstream) and ahead == 0 and behind == 0,
    }


def _has_plugin_surface(path: Path) -> bool:
    return (
        (path / ".codex-plugin" / "plugin.json").is_file()
        or (path / "skills").is_dir()
        or (path / "CODEX-PLUGIN.md").is_file()
        or (path / "pyproject.toml").is_file()
    )


def _children(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def _cache_children(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for plugin_dir in _children(root):
        versions = _children(plugin_dir)
        out.extend(versions or [plugin_dir])
    return sorted(out)


def _source_item(path: Path) -> dict[str, Any]:
    state = _git_state(path)
    dirty = bool(state.get("dirty_count"))
    unpushed = bool(state.get("ahead"))
    stale = bool(state.get("behind"))
    status = "clean"
    next_actions = ["No cleanup required; source repo is clean and synced."]
    if dirty or unpushed or stale:
        status = "needs-shipment"
        next_actions = [
            f"Run eidos ship {path}",
            "Review changes, commit source-owned work, and push the current branch.",
            "If changes are generated residue, remove them before claiming cleanup.",
        ]
    return {
        "path": str(path),
        "kind": "canonical-source",
        "source_of_truth": "source",
        "status": status,
        "installable_surface": _has_plugin_surface(path),
        "git": state,
        "next_actions": next_actions,
    }


def _mirror_item(path: Path) -> dict[str, Any]:
    state = _git_state(path) if _is_git_repo(path) else {"is_git": False}
    dirty = bool(state.get("dirty_count"))
    return {
        "path": str(path),
        "kind": "local-plugin-mirror",
        "source_of_truth": "derivative",
        "status": "needs-refresh" if dirty else "derivative",
        "installable_surface": _has_plugin_surface(path),
        "git": state,
        "next_actions": [
            "Refresh this mirror from its canonical source repo; do not treat it as source of truth."
        ],
    }


def _cache_item(path: Path) -> dict[str, Any]:
    state = _git_state(path) if _is_git_repo(path) else {"is_git": False}
    dirty = bool(state.get("dirty_count"))
    return {
        "path": str(path),
        "kind": "installed-cache",
        "source_of_truth": "derivative",
        "status": "needs-refresh" if dirty else "derivative",
        "installable_surface": _has_plugin_surface(path),
        "git": state,
        "next_actions": [
            "Do not commit from the cache; refresh it from the canonical source repo."
        ],
    }


def build_report(source_roots: list[Path], plugin_root: Path, cache_root: Path) -> dict[str, Any]:
    surfaces: list[dict[str, Any]] = []
    seen: set[str] = set()

    for root in source_roots:
        for path in _children(root.expanduser().resolve()):
            if not _is_git_repo(path):
                continue
            key = str(_git_root(path) or path.resolve())
            if key in seen:
                continue
            seen.add(key)
            surfaces.append(_source_item(Path(key)))

    for path in _children(plugin_root.expanduser().resolve()):
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            surfaces.append(_mirror_item(path.resolve()))

    for path in _cache_children(cache_root.expanduser().resolve()):
        key = str(path.resolve())
        if key not in seen:
            seen.add(key)
            surfaces.append(_cache_item(path.resolve()))

    blockers = [
        item
        for item in surfaces
        if item["kind"] == "canonical-source"
        and item["status"] != "clean"
        or item["kind"] in {"local-plugin-mirror", "installed-cache"}
        and item["status"] == "needs-refresh"
    ]
    return {
        "ok": not blockers,
        "goal": "Source repos are clean, pushed, and installable on any Codex-enabled Mac; mirrors and caches are derivative.",
        "source_roots": [str(p.expanduser().resolve()) for p in source_roots],
        "plugin_root": str(plugin_root.expanduser().resolve()),
        "cache_root": str(cache_root.expanduser().resolve()),
        "surfaces": surfaces,
        "blockers": blockers,
    }


def _format(report: dict[str, Any]) -> str:
    lines = [
        f"Cleanup verdict: {'PASS' if report['ok'] else 'NEEDS ATTENTION'}",
        report["goal"],
        "",
        "Surfaces:",
    ]
    for item in report["surfaces"]:
        lines.append(f"- {item['status'].upper()} {item['kind']} {item['path']}")
        git = item.get("git") or {}
        if git.get("is_git"):
            lines.append(
                f"  branch={git.get('branch') or '-'} upstream={git.get('upstream') or '-'} "
                f"ahead={git.get('ahead')} behind={git.get('behind')} dirty={git.get('dirty_count')}"
            )
        lines.append(f"  source_of_truth={item['source_of_truth']} installable_surface={item['installable_surface']}")
        for action in item.get("next_actions", [])[:3]:
            lines.append(f"  next: {action}")
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    @app.command("cleanup")
    def cmd_cleanup(
        source_root: Annotated[
            list[str],
            typer.Option("--source-root", help="Root containing canonical source repos. Repeatable."),
        ] = [],
        plugin_root: Annotated[
            str,
            typer.Option("--plugin-root", help="Local plugin mirror root."),
        ] = "~/plugins",
        cache_root: Annotated[
            str,
            typer.Option("--cache-root", help="Codex installed plugin cache root."),
        ] = "~/.codex/plugins/cache/eidos-agi",
        json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
    ) -> None:
        """Audit plugin/tool cleanup toward portable Codex installation.

        This command is read-only. It classifies canonical source repos,
        local plugin mirrors, and installed cache copies so cleanup preserves
        product work in source repos instead of treating caches as source.
        """
        roots = (
            [Path(p) for p in source_root]
            if source_root
            else [Path("~/repos-eidos-agi"), Path("~/repos-personal")]
        )
        report = build_report(roots, Path(plugin_root), Path(cache_root))
        typer.echo(json.dumps(report, indent=2, default=str) if json_ else _format(report))
        if not report["ok"]:
            raise typer.Exit(code=1)

