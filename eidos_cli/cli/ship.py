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

from .. import stepproof
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

BUILTIN_GATE_IDS = {
    "git-clean-pushed",
    "artifact-scan",
    "python-tests",
    "python-build",
    "twine-check",
    "wheel-install",
    "entrypoints",
    "codex-plugin-validator",
    "felix-plugin-doctor",
    "marketplace-check",
    "eidos-plugin-show",
    "eidos-plugin-run",
    "stepproof-audit",
    "post-clean-artifact-scan",
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


def _load_ship_manifest(repo: Path) -> tuple[Path | None, dict[str, Any]]:
    path = repo / ".eidos" / "ship" / "manifest.toml"
    if not path.is_file():
        return None, {}
    return path, tomllib.loads(path.read_text(encoding="utf-8"))


def _list_value(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _manifest_table(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    value = manifest.get(key)
    return value if isinstance(value, dict) else {}


def _manifest_repo(manifest: dict[str, Any]) -> dict[str, Any]:
    return _manifest_table(manifest, "repo")


def _manifest_artifacts(manifest: dict[str, Any]) -> dict[str, Any]:
    return _manifest_table(manifest, "artifacts")


def _manifest_learnings(manifest: dict[str, Any]) -> dict[str, Any]:
    return _manifest_table(manifest, "learnings")


def _manifest_stepproof(manifest: dict[str, Any]) -> dict[str, Any]:
    return _manifest_table(manifest, "stepproof")


def _manifest_builtin_gate_ids(manifest: dict[str, Any]) -> list[str] | None:
    gates = _manifest_table(manifest, "gates")
    raw = gates.get("builtin")
    if raw is None:
        return None
    ids = _list_value(raw)
    unknown = sorted(set(ids) - BUILTIN_GATE_IDS)
    if unknown:
        raise ValueError(f"unknown built-in ship gate(s) in manifest: {', '.join(unknown)}")
    return ids


def _manifest_custom_gates(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    raw = manifest.get("custom_gate")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("[[custom_gate]] entries must be TOML tables")
    gates: list[dict[str, Any]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"custom_gate #{idx} must be a TOML table")
        if not item.get("id"):
            raise ValueError(f"custom_gate #{idx} is missing id")
        if not item.get("command"):
            raise ValueError(f"custom_gate {item.get('id')} is missing command")
        gates.append(item)
    return gates


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


def _artifact_names(manifest: dict[str, Any]) -> set[str]:
    artifacts = _manifest_artifacts(manifest)
    names = set(ARTIFACT_NAMES)
    names.update(_list_value(artifacts.get("generated_names")))
    names.difference_update(_list_value(artifacts.get("allow_names")))
    return names


def _find_artifacts(repo: Path, manifest: dict[str, Any] | None = None) -> list[str]:
    manifest = manifest or {}
    artifact_names = _artifact_names(manifest)
    artifact_paths = set(_list_value(_manifest_artifacts(manifest).get("generated_paths")))
    matches: list[str] = []
    for path in repo.rglob("*"):
        rel = path.relative_to(repo)
        parts = set(rel.parts)
        if ".git" in parts:
            continue
        rel_text = str(rel)
        if (
            path.name in artifact_names
            or path.name.endswith(".egg-info")
            or rel_text in artifact_paths
        ):
            matches.append(str(rel))
    return sorted(matches)[:200]


def _clean_artifacts(repo: Path, manifest: dict[str, Any] | None = None) -> None:
    manifest = manifest or {}
    for name in _artifact_names(manifest):
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
    for rel in _list_value(_manifest_artifacts(manifest).get("generated_paths")):
        path = repo / rel
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink(missing_ok=True)


def _artifact_gate(repo: Path, manifest: dict[str, Any] | None = None) -> Gate:
    artifacts = _find_artifacts(repo, manifest)
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


def _custom_gate(repo: Path, item: dict[str, Any]) -> Gate:
    command = item["command"]
    cmd = command if isinstance(command, list) else ["bash", "--noprofile", "--norc", "-lc", str(command)]
    cwd_raw = item.get("cwd")
    cwd = (repo / str(cwd_raw)).resolve() if cwd_raw else repo
    env = {str(k): str(v) for k, v in (item.get("env") or {}).items()}
    return _command_gate(
        str(item["id"]),
        str(item.get("facet") or "custom"),
        [str(part) for part in cmd],
        cwd=cwd,
        timeout=int(item.get("timeout") or 120),
        env=env,
        pass_detail=str(item.get("pass_detail") or "Custom shipment gate passed."),
        fail_detail=str(item.get("fail_detail") or "Custom shipment gate failed."),
    )


def _stepproof_gate(repo: Path, manifest: dict[str, Any]) -> Gate:
    config = _manifest_stepproof(manifest)
    required = bool(config.get("required"))
    audit = bool(config.get("audit", True))
    metrics = bool(config.get("metrics"))
    check = stepproof.check_repo(repo, required=required, audit=audit, metrics=metrics)
    status = "pass" if check["ok"] else "fail"
    if check.get("status") == "absent" and not required:
        status = "skip"
    return Gate(
        id="stepproof-audit",
        facet="stepproof",
        status=status,
        detail=check.get("detail", "StepProof check complete."),
        cwd=str(repo),
        data=check,
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
    neutral_cwd = Path(tempfile.gettempdir())
    return [
        _command_gate(
            "eidos-plugin-show",
            "eidos-plugin",
            ["eidos", "plugin", "show", slug],
            cwd=neutral_cwd,
            timeout=60,
            pass_detail="Installed Eidos plugin is visible.",
            fail_detail="Installed Eidos plugin is not visible.",
        ),
        _eidos_plugin_run_gate(slug, neutral_cwd),
    ]


def _eidos_plugin_run_gate(slug: str, cwd: Path) -> Gate:
    cmd = ["eidos", "plugin", "run", slug, "--json"]
    gate = _command_gate(
        "eidos-plugin-run",
        "eidos-plugin",
        cmd,
        cwd=cwd,
        timeout=60,
        pass_detail="Installed Eidos plugin run path responds.",
        fail_detail="Installed Eidos plugin run path failed.",
    )
    if not gate.ok or not gate.stdout_tail:
        return gate
    try:
        payload = json.loads(gate.stdout_tail)
    except json.JSONDecodeError:
        return gate
    work_dir = payload.get("work_dir")
    if isinstance(work_dir, str):
        shutil.rmtree(work_dir, ignore_errors=True)
        gate.data["work_dir"] = work_dir
        gate.data["work_dir_cleaned"] = True
    return gate


def _write_evidence(repo: Path, report: dict[str, Any], manifest: dict[str, Any] | None = None) -> Path:
    evidence_dir = repo / str(_manifest_table(manifest or {}, "evidence").get("path") or ".eidos/ship/shipments")
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
    manifest_path, manifest = _load_ship_manifest(repo)
    repo_manifest = _manifest_repo(manifest)
    gates_manifest = _manifest_table(manifest, "gates")
    if marketplace is None and repo_manifest.get("marketplace"):
        marketplace = (repo / str(repo_manifest["marketplace"])).expanduser().resolve()
    if live_plugin is None and repo_manifest.get("live_plugin"):
        live_plugin = str(repo_manifest["live_plugin"])
    if repo_manifest.get("skip_tests") is not None:
        skip_tests = bool(repo_manifest["skip_tests"])
    if repo_manifest.get("skip_build") is not None:
        skip_build = bool(repo_manifest["skip_build"])
    if repo_manifest.get("skip_live") is not None:
        skip_live = bool(repo_manifest["skip_live"])
    if repo_manifest.get("clean") is not None:
        clean = bool(repo_manifest["clean"])
    builtin_gate_ids = _manifest_builtin_gate_ids(manifest)
    include_all_builtins = builtin_gate_ids is None

    def wants(gate_id: str) -> bool:
        return include_all_builtins or gate_id in (builtin_gate_ids or [])

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
    if wants("stepproof-audit") or _manifest_stepproof(manifest):
        facets.append("stepproof")

    gates: list[Gate] = []
    if wants("git-clean-pushed"):
        gates.append(_git_gate(repo))
    if wants("artifact-scan"):
        initial_artifacts = _find_artifacts(repo, manifest)
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
            _clean_artifacts(repo, manifest)
        else:
            gates.append(_artifact_gate(repo, manifest))
    if pyproject and project_name:
        if not skip_tests and wants("python-tests"):
            gates.append(_python_test_gate(repo, project_name))
        if not skip_build and wants("python-build"):
            gates.append(_build_gate(repo))
        if not skip_build and wants("twine-check"):
            gates.append(_twine_gate(repo))
        if not skip_build and wants("wheel-install"):
            gates.append(_wheel_install_gate(repo, project_name))
        if wants("entrypoints"):
            gates.extend(_entrypoint_gates(repo, pyproject))
    if wants("codex-plugin-validator"):
        gates.append(_codex_plugin_gate(repo))
    if wants("felix-plugin-doctor"):
        gates.append(_felix_plugin_gate(repo))
    if wants("marketplace-check"):
        gates.append(_marketplace_check_gate(repo, marketplace.expanduser().resolve() if marketplace else None))
    if not skip_live:
        live_gates = _live_plugin_gate(live_plugin, repo)
        if wants("eidos-plugin-show"):
            gates.extend(live_gates[:1])
        if wants("eidos-plugin-run"):
            gates.extend(live_gates[1:])
    if wants("stepproof-audit") or _manifest_stepproof(manifest):
        gates.append(_stepproof_gate(repo, manifest))
    for item in _manifest_custom_gates(manifest):
        gates.append(_custom_gate(repo, item))

    if clean and wants("post-clean-artifact-scan"):
        _clean_artifacts(repo, manifest)
        post_artifacts = _artifact_gate(repo, manifest)
        post_artifacts.id = "post-clean-artifact-scan"
        gates.append(post_artifacts)

    payload = {
        "ok": all(g.ok for g in gates),
        "repo": str(repo),
        "manifest": str(manifest_path) if manifest_path else None,
        "shipment_style": repo_manifest.get("style"),
        "facets": sorted(set(facets)),
        "project": {"name": project_name, "scripts": sorted(_scripts(pyproject).keys()) if pyproject else []},
        "do_not": _list_value(_manifest_learnings(manifest).get("do_not")),
        "yes": _list_value(_manifest_learnings(manifest).get("yes")),
        "notes": _list_value(_manifest_learnings(manifest).get("notes")),
        "gates": [g.to_dict() for g in gates],
    }
    return payload


def _format(report: dict[str, Any]) -> str:
    lines = [
        f"Shipment verdict: {'PASS' if report['ok'] else 'NEEDS ATTENTION'}",
        f"Repo: {report['repo']}",
        f"Manifest: {report.get('manifest') or 'none (auto-discovered gates)'}",
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
    if report.get("do_not"):
        lines.extend(["", "Do Not:"])
        lines.extend(f"- {item}" for item in report["do_not"])
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
            typer.Option("--write-evidence", help="Write the shipment report to .eidos/ship/shipments/."),
        ] = False,
        json_: Annotated[bool, typer.Option("--json", "-J", help="Compact JSON output.")] = False,
    ) -> None:
        """Run a manifest-aware shipment gate.

        If `.eidos/ship/manifest.toml` exists, Eidos uses it as the repo-local
        source of truth for shipment gates, defaults, artifact policy, evidence
        storage, and yes/do-not learning. Without a manifest, Eidos falls back
        to auto-discovered generic gates.
        """

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
        _, manifest = _load_ship_manifest(repo)
        evidence_manifest = _manifest_table(manifest, "evidence")
        if write_evidence or bool(evidence_manifest.get("auto_write")):
            evidence = _write_evidence(repo, report, manifest)
            report["evidence_path"] = str(evidence)
        typer.echo(json.dumps(report, indent=2, default=str) if json_ else _format(report))
        if not report["ok"]:
            raise typer.Exit(code=1)
