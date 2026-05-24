"""Shipment checks: prove the shipped surfaces, not just the source tree."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import venv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from . import closeout

try:  # py310+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


ARTIFACT_NAMES = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".build",
    "dist",
    "build",
}


@dataclass
class Gate:
    id: str
    facet: str
    status: str
    detail: str
    command: list[str] | None = None
    cwd: str | None = None
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration_seconds: float | None = None
    artifacts: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "skip"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "facet": self.facet,
            "status": self.status,
            "ok": self.ok,
            "detail": self.detail,
            "command": self.command,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "duration_seconds": self.duration_seconds,
            "artifacts": self.artifacts,
            "data": self.data,
        }


def _tail(text: str, limit: int = 2400) -> str:
    text = text.strip()
    return text[-limit:] if len(text) > limit else text


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], float]:
    run_env = os.environ.copy()
    run_env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(Path(tempfile.gettempdir()) / "eidos-ship-pycache"),
        }
    )
    if env:
        run_env.update(env)
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=run_env,
    )
    return proc, round(time.monotonic() - start, 3)


def _command_gate(
    gate_id: str,
    facet: str,
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    pass_detail: str,
    fail_detail: str,
) -> Gate:
    try:
        proc, duration = _run(cmd, cwd=cwd, timeout=timeout, env=env)
    except FileNotFoundError as e:
        return Gate(
            id=gate_id,
            facet=facet,
            status="fail",
            detail=f"{fail_detail}: command not found: {e.filename}",
            command=cmd,
            cwd=str(cwd),
        )
    except subprocess.TimeoutExpired:
        return Gate(
            id=gate_id,
            facet=facet,
            status="fail",
            detail=f"{fail_detail}: timed out after {timeout}s",
            command=cmd,
            cwd=str(cwd),
        )
    return Gate(
        id=gate_id,
        facet=facet,
        status="pass" if proc.returncode == 0 else "fail",
        detail=pass_detail if proc.returncode == 0 else fail_detail,
        command=cmd,
        cwd=str(cwd),
        exit_code=proc.returncode,
        stdout_tail=_tail(proc.stdout),
        stderr_tail=_tail(proc.stderr),
        duration_seconds=duration,
    )


def _load_pyproject(repo: Path) -> dict[str, Any] | None:
    path = repo / "pyproject.toml"
    if not path.is_file():
        return None
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _project_name(pyproject: dict[str, Any]) -> str | None:
    project = pyproject.get("project")
    return project.get("name") if isinstance(project, dict) else None


def _module_name(project_name: str) -> str:
    return project_name.replace("-", "_")


def _scripts(pyproject: dict[str, Any]) -> dict[str, str]:
    project = pyproject.get("project")
    if not isinstance(project, dict):
        return {}
    scripts = project.get("scripts")
    return scripts if isinstance(scripts, dict) else {}


def _find_artifacts(repo: Path) -> list[str]:
    matches: list[str] = []
    for path in repo.rglob("*"):
        rel = path.relative_to(repo)
        parts = set(rel.parts)
        if ".git" in parts:
            continue
        if path.name in ARTIFACT_NAMES or path.name.endswith(".egg-info"):
            matches.append(str(rel))
    return sorted(matches)[:200]


def _clean_artifacts(repo: Path) -> None:
    for name in ARTIFACT_NAMES:
        for path in list(repo.rglob(name)):
            if ".git" in path.relative_to(repo).parts:
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink(missing_ok=True)
    for egg_info in list(repo.rglob("*.egg-info")):
        if ".git" in egg_info.relative_to(repo).parts:
            continue
        if egg_info.is_dir():
            shutil.rmtree(egg_info, ignore_errors=True)
        else:
            egg_info.unlink(missing_ok=True)


def _artifact_gate(repo: Path) -> Gate:
    artifacts = _find_artifacts(repo)
    return Gate(
        id="artifact-scan",
        facet="workspace",
        status="fail" if artifacts else "pass",
        detail=(
            "Generated artifacts found in the checkout."
            if artifacts
            else "No generated build/cache artifacts found in the checkout."
        ),
        cwd=str(repo),
        artifacts=artifacts,
    )


def _git_gate(repo: Path) -> Gate:
    check = closeout._git_check(repo)  # engine-local reuse; closeout is the source of truth.
    return Gate(
        id="git-clean-pushed",
        facet="workspace",
        status="pass" if check["ok"] else "fail",
        detail=check["detail"],
        cwd=str(repo),
        data=check,
    )


def _python_test_gate(repo: Path, project_name: str) -> Gate:
    if not (repo / "tests").is_dir():
        return Gate(
            id="python-tests",
            facet="python-package",
            status="skip",
            detail="No tests/ directory found.",
            cwd=str(repo),
        )
    env_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_name)
    return _command_gate(
        "python-tests",
        "python-package",
        ["uv", "run", "--extra", "dev", "python", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=repo,
        timeout=300,
        env={"UV_PROJECT_ENVIRONMENT": str(Path(tempfile.gettempdir()) / f"eidos-ship-{env_name}-uv")},
        pass_detail="Python test suite passed.",
        fail_detail="Python test suite failed.",
    )


def _build_gate(repo: Path) -> Gate:
    shutil.rmtree(repo / "dist", ignore_errors=True)
    shutil.rmtree(repo / "build", ignore_errors=True)
    for egg_info in (repo / "src").glob("*.egg-info") if (repo / "src").is_dir() else []:
        shutil.rmtree(egg_info, ignore_errors=True)
    gate = _command_gate(
        "python-build",
        "python-package",
        ["uv", "build"],
        cwd=repo,
        timeout=180,
        pass_detail="Wheel and source distribution build completed.",
        fail_detail="Package build failed.",
    )
    dist = repo / "dist"
    gate.artifacts = sorted(str(p.relative_to(repo)) for p in dist.glob("*")) if dist.is_dir() else []
    return gate


def _twine_gate(repo: Path) -> Gate:
    if not (repo / "dist").is_dir():
        return Gate(
            id="twine-check",
            facet="python-package",
            status="skip",
            detail="No dist/ directory exists; build gate did not produce artifacts.",
            cwd=str(repo),
        )
    return _command_gate(
        "twine-check",
        "python-package",
        ["uvx", "twine", "check", "dist/*"],
        cwd=repo,
        timeout=180,
        pass_detail="Distribution metadata passed twine check.",
        fail_detail="Distribution metadata failed twine check.",
    )


def _wheel_install_gate(repo: Path, project_name: str) -> Gate:
    wheels = sorted((repo / "dist").glob("*.whl"))
    if not wheels:
        return Gate(
            id="wheel-install",
            facet="python-package",
            status="fail",
            detail="No wheel artifact found in dist/.",
            cwd=str(repo),
        )
    tmp = Path(tempfile.mkdtemp(prefix="eidos-ship-wheel-"))
    try:
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(tmp)
        python = tmp / "bin" / "python"
        module = _module_name(project_name)
        code = (
            "from importlib.metadata import version\n"
            f"import {module} as pkg\n"
            f"metadata = version({project_name!r})\n"
            "runtime = getattr(pkg, '__version__', metadata)\n"
            "print(f'metadata={metadata} runtime={runtime}')\n"
            "raise SystemExit(0 if metadata == runtime else 1)\n"
        )
        cmd = [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--quiet",
            str(wheels[-1]),
        ]
        install_gate = _command_gate(
            "wheel-install",
            "python-package",
            cmd,
            cwd=repo,
            timeout=180,
            pass_detail="Wheel installed into a clean virtual environment.",
            fail_detail="Wheel failed to install into a clean virtual environment.",
        )
        if not install_gate.ok:
            return install_gate
        verify_gate = _command_gate(
            "wheel-version",
            "python-package",
            [str(python), "-c", code],
            cwd=repo,
            timeout=30,
            pass_detail="Installed package runtime version matches metadata.",
            fail_detail="Installed package runtime version does not match metadata.",
        )
        verify_gate.id = "wheel-install"
        verify_gate.command = [*cmd, "&&", str(python), "-c", "<metadata/runtime version check>"]
        verify_gate.stdout_tail = "\n".join(
            part for part in [install_gate.stdout_tail, verify_gate.stdout_tail] if part
        )
        verify_gate.stderr_tail = "\n".join(
            part for part in [install_gate.stderr_tail, verify_gate.stderr_tail] if part
        )
        verify_gate.duration_seconds = (install_gate.duration_seconds or 0) + (
            verify_gate.duration_seconds or 0
        )
        return verify_gate
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _entrypoint_gates(repo: Path, pyproject: dict[str, Any]) -> list[Gate]:
    gates: list[Gate] = []
    for script in sorted(_scripts(pyproject)):
        gates.append(
            _command_gate(
                f"entrypoint-{script}-help",
                "cli",
                [script, "--help"],
                cwd=repo,
                timeout=30,
                pass_detail=f"{script} --help responds.",
                fail_detail=f"{script} --help failed.",
            )
        )
    return gates


def _codex_plugin_gate(repo: Path) -> Gate:
    if not (repo / ".codex-plugin" / "plugin.json").is_file():
        return Gate(
            id="codex-plugin-validator",
            facet="codex-plugin",
            status="skip",
            detail="No .codex-plugin/plugin.json found.",
            cwd=str(repo),
        )
    validator = Path.home() / ".codex" / "skills" / ".system" / "plugin-creator" / "scripts" / "validate_plugin.py"
    if not validator.is_file():
        return Gate(
            id="codex-plugin-validator",
            facet="codex-plugin",
            status="fail",
            detail=f"Codex plugin validator not found at {validator}.",
            cwd=str(repo),
        )
    return _command_gate(
        "codex-plugin-validator",
        "codex-plugin",
        ["python3", str(validator), str(repo)],
        cwd=repo,
        timeout=60,
        pass_detail="Codex plugin manifest validated.",
        fail_detail="Codex plugin validation failed.",
    )


def _felix_plugin_gate(repo: Path) -> Gate:
    if not (repo / ".codex-plugin" / "plugin.json").is_file() and not (repo / "plugin.yaml").is_file():
        return Gate(
            id="felix-plugin-doctor",
            facet="plugin",
            status="skip",
            detail="No plugin manifest found for Felix doctor.",
            cwd=str(repo),
        )
    if shutil.which("felix") is None:
        return Gate(
            id="felix-plugin-doctor",
            facet="plugin",
            status="skip",
            detail="felix command is not installed.",
            cwd=str(repo),
        )
    return _command_gate(
        "felix-plugin-doctor",
        "plugin",
        ["felix", "plugin", "doctor", str(repo)],
        cwd=repo,
        timeout=90,
        pass_detail="Felix plugin doctor passed.",
        fail_detail="Felix plugin doctor failed.",
    )


def _marketplace_check_gate(repo: Path, marketplace: Path | None) -> Gate:
    if marketplace is None:
        return Gate(
            id="marketplace-check",
            facet="marketplace",
            status="skip",
            detail="No marketplace repo supplied.",
            cwd=str(repo),
        )
    tool = marketplace / "tools" / "marketplace_publish.py"
    if not tool.is_file():
        return Gate(
            id="marketplace-check",
            facet="marketplace",
            status="skip",
            detail=f"No marketplace_publish.py found at {tool}.",
            cwd=str(repo),
        )
    slug = repo.name
    return _command_gate(
        "marketplace-check",
        "marketplace",
        ["python3", str(tool), "check", slug, "--source", str(repo)],
        cwd=marketplace,
        timeout=90,
        pass_detail="Marketplace bundle matches source.",
        fail_detail="Marketplace bundle drift or validation failure.",
    )


def _live_plugin_gate(slug: str | None, repo: Path) -> list[Gate]:
    if not slug:
        return []
    if shutil.which("eidos") is None:
        return [
            Gate(
                id="eidos-plugin-show",
                facet="eidos-plugin",
                status="skip",
                detail="eidos command is not installed.",
                cwd=str(repo),
            )
        ]
    return [
        _command_gate(
            "eidos-plugin-show",
            "eidos-plugin",
            ["eidos", "plugin", "show", slug],
            cwd=repo,
            timeout=60,
            pass_detail="Installed Eidos plugin is visible.",
            fail_detail="Installed Eidos plugin is not visible.",
        ),
        _command_gate(
            "eidos-plugin-run",
            "eidos-plugin",
            ["eidos", "plugin", "run", slug, "--json"],
            cwd=repo,
            timeout=60,
            pass_detail="Installed Eidos plugin run path responds.",
            fail_detail="Installed Eidos plugin run path failed.",
        ),
    ]


def _write_evidence(repo: Path, report: dict[str, Any]) -> Path:
    evidence_dir = repo / ".eidos" / "shipments"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = evidence_dir / f"shipment-{stamp}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return path


def build_report(
    repo: Path,
    *,
    marketplace: Path | None = None,
    live_plugin: str | None = None,
    skip_tests: bool = False,
    skip_build: bool = False,
    skip_live: bool = False,
    clean: bool = True,
) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    pyproject = _load_pyproject(repo)
    project_name = _project_name(pyproject) if pyproject else None
    facets = ["workspace"]
    if pyproject:
        facets.extend(["python-package", "cli"])
    if (repo / ".codex-plugin" / "plugin.json").is_file():
        facets.append("codex-plugin")
    if marketplace is not None:
        facets.append("marketplace")
    if live_plugin:
        facets.append("eidos-plugin")

    gates: list[Gate] = [_git_gate(repo)]
    initial_artifacts = _find_artifacts(repo)
    if initial_artifacts and clean:
        gates.append(
            Gate(
                id="pre-clean-artifact-scan",
                facet="workspace",
                status="pass",
                detail="Generated artifacts were found before shipment and cleaned before gates ran.",
                cwd=str(repo),
                artifacts=initial_artifacts,
            )
        )
        _clean_artifacts(repo)
    else:
        gates.append(_artifact_gate(repo))
    if pyproject and project_name:
        if not skip_tests:
            gates.append(_python_test_gate(repo, project_name))
        if not skip_build:
            gates.append(_build_gate(repo))
            gates.append(_twine_gate(repo))
            gates.append(_wheel_install_gate(repo, project_name))
        gates.extend(_entrypoint_gates(repo, pyproject))
    gates.append(_codex_plugin_gate(repo))
    gates.append(_felix_plugin_gate(repo))
    gates.append(_marketplace_check_gate(repo, marketplace.expanduser().resolve() if marketplace else None))
    if not skip_live:
        gates.extend(_live_plugin_gate(live_plugin, repo))

    if clean:
        _clean_artifacts(repo)
        post_artifacts = _artifact_gate(repo)
        post_artifacts.id = "post-clean-artifact-scan"
        gates.append(post_artifacts)

    payload = {
        "ok": all(g.ok for g in gates),
        "repo": str(repo),
        "facets": sorted(set(facets)),
        "project": {"name": project_name, "scripts": sorted(_scripts(pyproject).keys()) if pyproject else []},
        "gates": [g.to_dict() for g in gates],
    }
    return payload


def _format(report: dict[str, Any]) -> str:
    lines = [
        f"Shipment verdict: {'PASS' if report['ok'] else 'NEEDS ATTENTION'}",
        f"Repo: {report['repo']}",
        f"Facets: {', '.join(report['facets'])}",
        "",
        "Gates:",
    ]
    for gate in report["gates"]:
        marker = "PASS" if gate["status"] == "pass" else "SKIP" if gate["status"] == "skip" else "FAIL"
        lines.append(f"- {marker} {gate['id']} [{gate['facet']}] — {gate['detail']}")
        if gate.get("command"):
            lines.append(f"  cmd: {' '.join(gate['command'])}")
        if gate.get("artifacts"):
            lines.append(f"  artifacts: {', '.join(gate['artifacts'][:8])}")
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    @app.command("ship")
    def cmd_ship(
        path: Annotated[
            Optional[str],
            typer.Argument(help="Repo path to ship. Defaults to the current directory."),
        ] = None,
        marketplace: Annotated[
            Optional[str],
            typer.Option("--marketplace", help="Marketplace repo path for source/bundle drift checks."),
        ] = None,
        live_plugin: Annotated[
            Optional[str],
            typer.Option("--live-plugin", help="Installed Eidos plugin slug to show/run as a live surface."),
        ] = None,
        skip_tests: Annotated[bool, typer.Option("--skip-tests", help="Skip Python test gate.")] = False,
        skip_build: Annotated[bool, typer.Option("--skip-build", help="Skip build/twine/wheel gates.")] = False,
        skip_live: Annotated[bool, typer.Option("--skip-live", help="Skip live installed plugin gates.")] = False,
        no_clean: Annotated[
            bool,
            typer.Option("--no-clean", help="Do not remove dist/build/egg-info artifacts after build gates."),
        ] = False,
        write_evidence: Annotated[
            bool,
            typer.Option("--write-evidence", help="Write the shipment report to .eidos/shipments/."),
        ] = False,
        json_: Annotated[bool, typer.Option("--json", "-J", help="Compact JSON output.")] = False,
    ) -> None:
        """Run a facet-aware shipment gate and fail closed on weak proof."""

        repo = Path(path).expanduser().resolve() if path else Path.cwd().resolve()
        report = build_report(
            repo,
            marketplace=Path(marketplace).expanduser().resolve() if marketplace else None,
            live_plugin=live_plugin,
            skip_tests=skip_tests,
            skip_build=skip_build,
            skip_live=skip_live,
            clean=not no_clean,
        )
        if write_evidence:
            evidence = _write_evidence(repo, report)
            report["evidence_path"] = str(evidence)
        typer.echo(json.dumps(report, indent=2, default=str) if json_ else _format(report))
        if not report["ok"]:
            raise typer.Exit(code=1)
