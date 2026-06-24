"""Mission closeout checks: prove a loop can be closed cleanly."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from ..agentic_first import (
    PRE_CODE_QUESTION,
    doctrine,
    is_agentic_protocol_path,
    is_code_path,
    parse_porcelain_path,
)
from .. import stepproof
from ..scope.manifest import load_manifest
from ..scope.resolver import resolve_from_cwd, resolve_home_from_path


def _run(cmd: list[str], cwd: Path, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def _git_root(path: Path) -> Path | None:
    proc = _run(["git", "rev-parse", "--show-toplevel"], path)
    return Path(proc.stdout.strip()).resolve() if proc.returncode == 0 else None


def _git_check(path: Path) -> dict:
    root = _git_root(path)
    if root is None:
        return {
            "path": str(path.resolve()),
            "kind": "git",
            "ok": False,
            "status": "not-git",
            "detail": "No git repository found at or above this path.",
        }

    porcelain = [
        line
        for line in _run(["git", "status", "--porcelain=v1"], root).stdout.splitlines()
        if not _is_runtime_state_path(parse_porcelain_path(line))
    ]
    branch = _run(["git", "branch", "--show-current"], root).stdout.strip()
    head = _run(["git", "rev-parse", "--short", "HEAD"], root).stdout.strip()
    upstream_proc = _run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root)
    upstream = upstream_proc.stdout.strip() if upstream_proc.returncode == 0 else ""

    ahead = behind = None
    synced = True
    if upstream:
        counts = _run(["git", "rev-list", "--left-right", "--count", f"{branch}...{upstream}"], root)
        if counts.returncode == 0:
            left, right = counts.stdout.strip().split()
            ahead, behind = int(left), int(right)
            synced = ahead == 0 and behind == 0

    modified = [line for line in porcelain if not line.startswith("??")]
    untracked = [line for line in porcelain if line.startswith("??")]
    clean = not porcelain
    ok = clean and synced
    return {
        "path": str(root),
        "kind": "git",
        "ok": ok,
        "status": "ok" if ok else "needs-attention",
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "ahead": ahead,
        "behind": behind,
        "clean": clean,
        "modified_count": len(modified),
        "untracked_count": len(untracked),
        "examples": porcelain[:10],
        "detail": "Clean and synced." if ok else "Working tree or upstream state needs attention.",
    }


def _is_runtime_state_path(path: str) -> bool:
    return path == ".stepproof" or path.startswith(".stepproof/")


def _resolve_repo_paths(path: Optional[str], repos: list[str]) -> list[Path]:
    start = Path(path).expanduser().resolve() if path else Path.cwd().resolve()
    home = resolve_home_from_path(start) if path else resolve_from_cwd()
    paths: list[Path] = []
    if home is not None:
        paths.append(home)
        manifest = load_manifest(home / ".eidos")
        if manifest is not None:
            paths.extend(Path(m.repo).expanduser().resolve() for m in manifest.members)
    else:
        paths.append(start)
    paths.extend(Path(r).expanduser().resolve() for r in repos)

    deduped: list[Path] = []
    seen: set[str] = set()
    for p in paths:
        if str(p) not in seen:
            seen.add(str(p))
            deduped.append(p)
    return deduped


def _codex_marketplace_check() -> dict:
    marketplace = _resolve_codex_marketplace_path()
    result = {
        "kind": "codex-marketplace",
        "path": str(marketplace),
        "ok": True,
        "status": "ok",
        "missing": [],
        "checked": 0,
        "detail": "Codex marketplace plugin paths resolve.",
    }
    if not marketplace.exists():
        result.update(ok=False, status="missing", detail="Codex marketplace file not found.")
        return result

    data = json.loads(marketplace.read_text())
    if marketplace.parent.name == "plugins" and marketplace.parent.parent.name == ".agents":
        root = marketplace.parent.parent.parent
    else:
        root = marketplace.parent
    for entry in data.get("plugins", []):
        source = entry.get("source", {})
        if not isinstance(source, dict) or source.get("source") != "local":
            continue
        rel = source.get("path")
        if not isinstance(rel, str):
            continue
        plugin_path = (root / rel).resolve()
        result["checked"] += 1
        if not (plugin_path / ".codex-plugin" / "plugin.json").is_file():
            result["missing"].append({"name": entry.get("name"), "path": str(plugin_path)})

    if result["missing"]:
        result.update(
            ok=False,
            status="needs-attention",
            detail="One or more marketplace entries point at missing Codex plugin manifests.",
        )
    return result


def _resolve_codex_marketplace_path() -> Path:
    configured = os.environ.get("EIDOS_CODEX_MARKETPLACE")
    if configured:
        return Path(configured).expanduser()

    config_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    config_path = config_home / "config.toml"
    source = _configured_eidos_marketplace_source(config_path)
    if source:
        return source / ".agents" / "plugins" / "marketplace.json"

    return Path.home() / ".agents" / "plugins" / "marketplace.json"


def _configured_eidos_marketplace_source(config_path: Path) -> Path | None:
    if not config_path.is_file():
        return None

    in_eidos_marketplace = False
    source_type = ""
    for raw_line in config_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_eidos_marketplace = line == "[marketplaces.eidos-agi]"
            source_type = ""
            continue
        if not in_eidos_marketplace:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key == "source_type":
            source_type = value
            continue
        if key != "source":
            continue
        if value and source_type != "git" and "://" not in value and not value.startswith("git@"):
            return Path(value).expanduser()
    return None


def _plugin_runs_check(paths: list[Path]) -> dict:
    result = {
        "kind": "plugin-runs",
        "ok": True,
        "status": "ok",
        "checked": 0,
        "incomplete": [],
        "detail": "No incomplete plugin run workspaces found.",
    }
    seen: set[str] = set()
    for path in paths:
        runs_dir = path / ".eidos" / "praxis" / "plugin_runs"
        if not runs_dir.is_dir():
            continue
        for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
            key = str(run_dir.resolve())
            if key in seen:
                continue
            seen.add(key)
            result["checked"] += 1
            draft_dir = run_dir / "draft"
            draft_files = [p for p in draft_dir.rglob("*") if p.is_file()] if draft_dir.is_dir() else []
            if not draft_files:
                result["incomplete"].append(
                    {
                        "path": str(run_dir),
                        "status": "needs-draft",
                        "detail": "No draft outputs found. Continue/install the plugin draft or remove the run.",
                        "suggestions": [
                            f"eidos learn --status --work-dir {run_dir}",
                            f"eidos learn --continue --work-dir {run_dir}",
                            f"eidos learn --finish --work-dir {run_dir} --scope global",
                            f"manual discard: remove {run_dir} only if the draft is intentionally abandoned",
                        ],
                    }
                )

    if result["incomplete"]:
        result.update(
            ok=False,
            status="needs-attention",
            detail="One or more plugin run workspaces have no draft outputs.",
        )
    return result


def _expand_status_paths(root: Path, paths: list[str]) -> list[str]:
    expanded: list[str] = []
    for rel in paths:
        path = root / rel
        if path.is_dir():
            expanded.extend(
                p.relative_to(root).as_posix() for p in path.rglob("*") if p.is_file()
            )
        else:
            expanded.append(rel)
    return sorted(set(expanded))


def _agentic_first_check(paths: list[Path]) -> dict:
    result = {
        "kind": "agentic-first",
        "ok": True,
        "status": "ok",
        "doctrine": doctrine(),
        "repos": [],
        "detail": "Code changes are paired with agentic protocol or proof changes.",
    }
    seen: set[str] = set()
    for path in paths:
        root = _git_root(path)
        if root is None:
            continue
        key = str(root)
        if key in seen:
            continue
        seen.add(key)

        porcelain = _run(["git", "status", "--porcelain=v1"], root).stdout.splitlines()
        dirty_paths = _expand_status_paths(root, [parse_porcelain_path(line) for line in porcelain])
        dirty_code = sorted(p for p in dirty_paths if is_code_path(p))
        dirty_protocol = sorted(p for p in dirty_paths if is_agentic_protocol_path(p))

        upstream_proc = _run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root
        )
        upstream = upstream_proc.stdout.strip() if upstream_proc.returncode == 0 else ""
        unpushed_paths: list[str] = []
        if upstream:
            diff_proc = _run(["git", "diff", "--name-only", f"{upstream}..HEAD"], root)
            if diff_proc.returncode == 0:
                unpushed_paths = [line.strip() for line in diff_proc.stdout.splitlines() if line.strip()]
        unpushed_code = sorted(p for p in unpushed_paths if is_code_path(p))
        unpushed_protocol = sorted(p for p in unpushed_paths if is_agentic_protocol_path(p))

        repo_ok = True
        reasons: list[str] = []
        if dirty_code and not dirty_protocol:
            repo_ok = False
            reasons.append("dirty code changes have no paired agentic protocol/proof change")
        if unpushed_code and not unpushed_protocol:
            repo_ok = False
            reasons.append("unpushed code commits have no paired agentic protocol/proof change")
        result["repos"].append(
            {
                "path": key,
                "ok": repo_ok,
                "dirty_code_changes": dirty_code,
                "agentic_protocol_changes": dirty_protocol,
                "unpushed_code_changes": unpushed_code,
                "unpushed_agentic_protocol_changes": unpushed_protocol,
                "detail": "; ".join(reasons) if reasons else "Agentic-first pairing satisfied.",
            }
        )

    if any(not repo["ok"] for repo in result["repos"]):
        result.update(ok=False, status="needs-attention", detail=PRE_CODE_QUESTION)
    return result


def _catalog_drift_check(paths: list[Path]) -> dict[str, Any]:
    registry, source = _load_local_capability_registry()
    result: dict[str, Any] = {
        "kind": "catalog-drift",
        "ok": True,
        "status": "ok",
        "registry_source": source,
        "items": [],
        "detail": "No blocking catalog drift found.",
    }
    plugins = {
        plugin.get("slug"): plugin
        for plugin in (registry.get("plugins", []) if registry else [])
        if isinstance(plugin, dict) and plugin.get("slug")
    }
    seen: set[str] = set()
    for path in paths:
        root = _git_root(path)
        if root is None:
            continue
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        slug, version = _plugin_identity(root)
        if not slug:
            continue
        item = _catalog_drift_item(root, slug, version, plugins.get(slug), source)
        result["items"].append(item)

    if any(item["severity"] == "blocker" for item in result["items"]):
        result.update(ok=False, status="blocked", detail="Catalog drift includes blockers.")
    elif any(item["severity"] == "warning" for item in result["items"]):
        result.update(status="warning", detail="Catalog drift includes warnings.")
    elif result["items"]:
        result.update(status="advisory", detail="Catalog entries match local source metadata.")
    return result


def _load_local_capability_registry() -> tuple[dict[str, Any] | None, str | None]:
    candidates = [
        Path.cwd() / "src" / "data" / "capability-registry.generated.json",
        Path.cwd().parent / "eidosagi.com" / "src" / "data" / "capability-registry.generated.json",
        Path.cwd().parent / "eidos-plugin-store" / "examples" / "capability-registry.sample.json",
        Path("/Users/dshanklin/repos-eidos-agi/eidosagi.com/src/data/capability-registry.generated.json"),
        Path("/Users/dshanklin/repos-eidos-agi/eidos-plugin-store/examples/capability-registry.sample.json"),
        Path("/Volumes/MacMiniStorage/Eidos/repos-eidos-agi/eidosagi.com/src/data/capability-registry.generated.json"),
        Path("/Volumes/MacMiniStorage/Eidos/repos-eidos-agi/eidos-plugin-store/examples/capability-registry.sample.json"),
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            return json.loads(path.read_text()), str(path)
        except json.JSONDecodeError:
            continue
    return None, None


def _plugin_identity(root: Path) -> tuple[str | None, str | None]:
    manifest_path = root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return None, None
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return None, None
    name = manifest.get("name")
    slug = str(name).strip() if isinstance(name, str) and name.strip() else root.name
    version = manifest.get("version")
    return slug, str(version) if isinstance(version, str) else None


def _catalog_drift_item(
    root: Path,
    slug: str,
    version: str | None,
    registry_entry: dict[str, Any] | None,
    registry_source: str | None,
) -> dict[str, Any]:
    if registry_entry is None:
        severity = "warning" if registry_source else "advisory"
        detail = (
            "plugin is not represented in the local capability registry"
            if registry_source
            else "no local capability registry found for drift comparison"
        )
        return {
            "slug": slug,
            "path": str(root),
            "severity": severity,
            "status": "missing" if registry_source else "unchecked",
            "detail": detail,
        }

    install = registry_entry.get("install_status", {})
    source_repo = install.get("source", {}).get("repo")
    public_status = install.get("public_catalog", {}).get("status")
    live_version = install.get("live_version")
    details: list[str] = []
    severity = "advisory"
    if source_repo and root.name not in str(source_repo):
        severity = "warning"
        details.append(f"registry source repo {source_repo!r} does not match local repo name {root.name!r}")
    if public_status not in {"listed", "not_listed", "unknown"}:
        severity = "warning"
        details.append(f"registry public catalog status is invalid: {public_status!r}")
    if version and live_version and version != live_version:
        severity = "warning"
        details.append(f"local version {version} differs from registry live_version {live_version}")
    if not details:
        details.append("registry entry found; source, public status, and version metadata are comparable")
    return {
        "slug": slug,
        "path": str(root),
        "severity": severity,
        "status": "ok" if severity == "advisory" else "drift",
        "detail": "; ".join(details),
    }


def _format(report: dict, *, verbose: bool = False) -> str:
    failed_git = [check for check in report["git"] if not check["ok"]]
    missing_marketplace = report["codex_marketplace"].get("missing", [])
    incomplete_runs = report["plugin_runs"].get("incomplete", [])
    agentic_failures = [repo for repo in report["agentic_first"].get("repos", []) if not repo["ok"]]
    stepproof_failures = [sp for sp in report.get("stepproof", []) if not sp["ok"]]
    catalog_items = report.get("catalog_drift", {}).get("items", [])
    catalog_blockers = [item for item in catalog_items if item.get("severity") == "blocker"]
    catalog_warnings = [item for item in catalog_items if item.get("severity") == "warning"]

    lines = [
        f"Closeout verdict: {'PASS' if report['ok'] else 'NEEDS ATTENTION'}",
        "",
        f"Summary: {len(failed_git)} dirty git repos, {len(missing_marketplace)} missing marketplace entries, "
        f"{len(incomplete_runs)} incomplete plugin runs, {len(agentic_failures)} agentic-first failures, "
        f"{len(stepproof_failures)} StepProof failures, {len(catalog_blockers)} catalog blockers, "
        f"{len(catalog_warnings)} catalog warnings.",
    ]

    if verbose:
        _format_verbose_sections(report, lines)
        return "\n".join(lines)

    if failed_git:
        lines.append("")
        lines.append("Git blockers:")
        for check in failed_git:
            lines.append(f"- {check['path']}")
            if check.get("status") != "not-git":
                lines.append(
                    f"  branch={check.get('branch')} upstream={check.get('upstream') or '-'} "
                    f"ahead={check.get('ahead')} behind={check.get('behind')} "
                    f"modified={check.get('modified_count')} untracked={check.get('untracked_count')}"
                )
            else:
                lines.append(f"  {check['detail']}")

    if missing_marketplace:
        lines.append("")
        lines.append("Marketplace blockers:")
        for missing in missing_marketplace[:10]:
            lines.append(f"- {missing['name']}: {missing['path']}")

    if incomplete_runs:
        lines.append("")
        lines.append("Plugin-run blockers:")
        for incomplete in incomplete_runs[:10]:
            lines.append(f"- {incomplete['path']}: {incomplete['detail']}")

    if agentic_failures:
        lines.append("")
        lines.append("Agentic-first blockers:")
        for repo in agentic_failures[:10]:
            lines.append(
                f"- {repo['path']}: code={len(repo.get('dirty_code_changes', []))} "
                f"protocol={len(repo.get('agentic_protocol_changes', []))} "
                f"unpushed_code={len(repo.get('unpushed_code_changes', []))}"
            )

    if stepproof_failures:
        lines.append("")
        lines.append("StepProof blockers:")
        for sp in stepproof_failures[:10]:
            lines.append(f"- {sp['path']}: {sp.get('detail')}")

    if catalog_blockers or catalog_warnings:
        lines.append("")
        lines.append("Catalog drift:")
        for item in (catalog_blockers + catalog_warnings)[:10]:
            lines.append(f"- {item['severity'].upper()} {item['slug']}: {item['detail']}")

    return "\n".join(lines)


def _format_verbose_sections(report: dict, lines: list[str]) -> None:
    lines.extend(["", "Git repositories:"])
    for check in report["git"]:
        marker = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- {marker} {check['path']}")
        if check.get("status") != "not-git":
            lines.append(
                f"  branch={check.get('branch')} upstream={check.get('upstream') or '-'} "
                f"ahead={check.get('ahead')} behind={check.get('behind')} "
                f"modified={check.get('modified_count')} untracked={check.get('untracked_count')}"
            )
        else:
            lines.append(f"  {check['detail']}")
    mp = report["codex_marketplace"]
    marker = "PASS" if mp["ok"] else "FAIL"
    lines.extend(["", f"Codex marketplace: {marker} {mp['path']}"])
    lines.append(f"  checked={mp.get('checked', 0)} missing={len(mp.get('missing', []))}")
    for missing in mp.get("missing", [])[:10]:
        lines.append(f"  missing {missing['name']}: {missing['path']}")
    runs = report["plugin_runs"]
    marker = "PASS" if runs["ok"] else "FAIL"
    lines.extend(["", f"Plugin runs: {marker}"])
    lines.append(
        f"  checked={runs.get('checked', 0)} incomplete={len(runs.get('incomplete', []))}"
    )
    for incomplete in runs.get("incomplete", [])[:10]:
        lines.append(f"  incomplete {incomplete['path']}: {incomplete['detail']}")
        for suggestion in incomplete.get("suggestions", [])[:4]:
            lines.append(f"    next: {suggestion}")
    af = report["agentic_first"]
    marker = "PASS" if af["ok"] else "FAIL"
    lines.extend(["", f"Agentic-first: {marker}"])
    lines.append(f"  {af['detail']}")
    for repo in af.get("repos", [])[:10]:
        lines.append(
            f"  {repo['path']}: code={len(repo.get('dirty_code_changes', []))} "
            f"protocol={len(repo.get('agentic_protocol_changes', []))} "
            f"unpushed_code={len(repo.get('unpushed_code_changes', []))}"
        )
    lines.extend(["", "StepProof:"])
    for sp in report.get("stepproof", []):
        marker = "PASS" if sp["ok"] else "FAIL"
        lines.append(f"- {marker} {sp['path']}")
        lines.append(
            f"  status={sp.get('status')} installed={sp.get('installed')} "
            f"runs={sp.get('runs_count', 0)} detail={sp.get('detail')}"
        )
        active = sp.get("active_run") or {}
        if active:
            lines.append(
                f"  active_run={active.get('run_id')} step={active.get('current_step') or '-'}"
            )
    lines.extend(["", "Catalog drift:"])
    for item in report.get("catalog_drift", {}).get("items", []):
        lines.append(f"- {item['severity'].upper()} {item['slug']}: {item['detail']}")


def build_report(path: Optional[str], repos: list[str], include_codex_marketplace: bool) -> dict:
    repo_paths = _resolve_repo_paths(path, repos)
    git_checks = [_git_check(p) for p in repo_paths]
    codex_marketplace = (
        _codex_marketplace_check()
        if include_codex_marketplace
        else {"kind": "codex-marketplace", "ok": True, "status": "skipped"}
    )
    plugin_runs = _plugin_runs_check(repo_paths)
    agentic_first = _agentic_first_check(repo_paths)
    stepproof_checks = [stepproof.check_repo(p) for p in repo_paths]
    catalog_drift = _catalog_drift_check(repo_paths)
    ok = (
        all(check["ok"] for check in git_checks)
        and codex_marketplace["ok"]
        and plugin_runs["ok"]
        and agentic_first["ok"]
        and all(check["ok"] for check in stepproof_checks)
        and catalog_drift["ok"]
    )
    return {
        "ok": ok,
        "git": git_checks,
        "codex_marketplace": codex_marketplace,
        "plugin_runs": plugin_runs,
        "agentic_first": agentic_first,
        "stepproof": stepproof_checks,
        "catalog_drift": catalog_drift,
    }


def register(app: typer.Typer) -> None:
    @app.command("closeout")
    def cmd_closeout(
        path: Annotated[
            Optional[str],
            typer.Argument(help="Eidos home or repo path. Defaults to the current directory."),
        ] = None,
        repo: Annotated[
            list[str],
            typer.Option("--repo", help="Additional repo path to include. Repeatable."),
        ] = [],
        no_codex_marketplace: Annotated[
            bool,
            typer.Option("--no-codex-marketplace", help="Skip Codex marketplace pointer checks."),
        ] = False,
        verbose: Annotated[
            bool,
            typer.Option("--verbose", help="Show all repositories and checks, including passes."),
        ] = False,
        json_: Annotated[bool, typer.Option("--json", "-J", help="Compact JSON output.")] = False,
    ) -> None:
        """Check whether a mission is clean enough to close.

        This command is read-only. It reports dirty git state, unpushed commits,
        missing Codex plugin bundles, and other residue that should be resolved
        before an agent claims the work is done.
        """
        report = build_report(path, repo, not no_codex_marketplace)
        typer.echo(json.dumps(report, indent=2) if json_ else _format(report, verbose=verbose))
        if not report["ok"]:
            raise typer.Exit(code=1)
