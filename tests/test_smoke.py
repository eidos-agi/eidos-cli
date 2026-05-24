"""End-to-end smoke tests for eidos-cli.

Each test exercises a real eidos surface against a temp directory — no
mocks for the forge libraries; they're called as installed packages.

Coverage:
- `eidos define` creates manifest + telos + active forge dirs + seeds per-forge configs
- `eidos enter` resolves from CWD and emits boot
- `eidos status` reports forge states
- `eidos activate` scaffolds dormant forges idempotently
- `eidos tick` emits snapshot + reads telos triggers
- `eidos docket task-create` writes into .eidos/docket/tasks/ (eidos-aware path)
- `eidos migrate` consolidates legacy state into .eidos/
- `eidos mcp serve` speaks stdio JSON-RPC, exposes one help tool
- `eidos close` writes pod.log entry
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


EIDOS = "eidos"  # installed via pip install -e .


def _run(
    args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        [EIDOS, *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=30,
        env=run_env,
    )


@pytest.fixture
def temp_eidos(tmp_path: Path):
    """Define a fresh eidos at tmp_path and yield the home + manifest."""
    proc = _run(
        [
            "define",
            str(tmp_path),
            "--name",
            "smoke",
            "--statement",
            "Smoke test the eidos surface",
            "--success-when",
            "all eidos verbs respond cleanly,manifest is durable",
            "--failure-when",
            "any verb crashes,manifest corrupts",
            "--success-when-not",
            "becomes chat-mode,couples to a single substrate",
            "--forges",
            "governor,docket,praxis",
            "--json",
        ]
    )
    assert proc.returncode == 0, f"define failed: {proc.stderr}"
    manifest = json.loads(proc.stdout)
    return tmp_path, manifest


# ── define ────────────────────────────────────────────────────────────────


def test_define_creates_eidos_home(temp_eidos):
    home, manifest = temp_eidos
    eidos_dir = home / ".eidos"
    assert eidos_dir.is_dir()
    assert (eidos_dir / "eidos.json").is_file()
    assert (eidos_dir / "telos.md").is_file()


def test_define_seeds_active_forge_dirs(temp_eidos):
    home, _ = temp_eidos
    for forge in ("governor", "docket", "praxis"):
        assert (home / ".eidos" / forge).is_dir(), f"{forge} not scaffolded"


def test_define_seeds_per_forge_configs(temp_eidos):
    home, _ = temp_eidos
    assert (home / ".eidos" / "docket" / "docket.json").is_file()
    assert (home / ".eidos" / "governor" / "config.yaml").is_file()
    # praxis doesn't get a seed config yet (planned in praxis-md follow-on)


def test_define_writes_4field_telos(temp_eidos):
    home, _ = temp_eidos
    content = (home / ".eidos" / "telos.md").read_text()
    assert "statement: Smoke test the eidos surface" in content
    assert "success_when:" in content
    assert "failure_when:" in content
    assert "success_when_not:" in content


def test_define_refuses_empty_telos_fields(tmp_path):
    # Should fail without success_when (missing required field per contract gate).
    proc = _run(
        [
            "define",
            str(tmp_path),
            "--statement",
            "x",
            # no --success-when, --failure-when, --success-when-not
            "--forges",
            "docket",
        ]
    )
    assert proc.returncode != 0
    assert "success_when" in (proc.stderr + proc.stdout)


def test_define_refuses_existing_eidos(temp_eidos):
    home, _ = temp_eidos
    proc = _run(
        [
            "define",
            str(home),
            "--statement",
            "x",
            "--success-when",
            "y",
            "--failure-when",
            "z",
            "--success-when-not",
            "w",
            "--forges",
            "docket",
        ]
    )
    assert proc.returncode != 0
    assert "already exists" in (proc.stderr + proc.stdout)


# ── enter / status ─────────────────────────────────────────────────────────


def test_enter_resolves_from_inside(temp_eidos):
    home, manifest = temp_eidos
    inside = home / ".eidos" / "docket"
    proc = _run(["enter"], cwd=inside)
    assert proc.returncode == 0
    assert manifest["id"] in proc.stdout


def test_status_reports_forge_states(temp_eidos):
    home, _ = temp_eidos
    proc = _run(["status", "--json"], cwd=home)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    states = data["forge_states"]
    assert states["governor"] == "active"
    assert states["docket"] == "active"
    assert states["praxis"] == "active"
    assert states["research"] == "dormant"


def test_scope_reports_missing_eidos_without_failure(tmp_path):
    proc = _run(["scope", "--json"], cwd=tmp_path)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["resolved"] is False
    assert data["home"] is None
    assert "no .eidos or .eidos-pointer" in data["reason"]
    assert any("eidos define" in action for action in data["actions"])


def test_scope_reports_resolved_eidos(temp_eidos):
    home, manifest = temp_eidos
    inside = home / ".eidos" / "docket"
    proc = _run(["scope", "--json"], cwd=inside)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["resolved"] is True
    assert data["home"] == str(home)
    assert data["name"] == manifest["name"]
    assert data["id"] == manifest["id"]


# ── activate ───────────────────────────────────────────────────────────────


def test_activate_scaffolds_dormant_forge(temp_eidos):
    home, _ = temp_eidos
    proc = _run(["activate", "research", str(home), "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["already_active"] is False
    assert "research" in data["active_forges"]
    assert (home / ".eidos" / "research" / "research.json").is_file()


def test_activate_idempotent(temp_eidos):
    home, _ = temp_eidos
    proc = _run(["activate", "governor", str(home), "--json"])
    data = json.loads(proc.stdout)
    assert data["already_active"] is True


# ── tick ───────────────────────────────────────────────────────────────────


def test_tick_emits_snapshot(temp_eidos):
    home, _ = temp_eidos
    proc = _run(["tick", str(home), "--json"])
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "telos" in data
    assert data["telos"]["statement"]
    assert len(data["telos"]["success_when"]) >= 1
    assert "advice" in data


# ── forge namespace: docket ────────────────────────────────────────────────


def test_docket_writes_into_eidos_dir(temp_eidos):
    home, manifest = temp_eidos
    # task-create from CWD inside the eidos.
    proc = _run(
        [
            "docket",
            "task-create",
            "--project-id",
            manifest["id"],
            "--title",
            "smoke task",
        ],
        cwd=home,
    )
    assert proc.returncode == 0, f"docket task-create failed: {proc.stderr}"
    # Task file must land in .eidos/docket/tasks/, not .docket/.
    tasks_dir = home / ".eidos" / "docket" / "tasks"
    assert tasks_dir.is_dir()
    task_files = list(tasks_dir.glob("*.md"))
    assert len(task_files) == 1
    assert not (home / ".docket").exists()


def test_docket_task_list_finds_eidos_aware_tasks(temp_eidos):
    home, manifest = temp_eidos
    _run(
        [
            "docket",
            "task-create",
            "--project-id",
            manifest["id"],
            "--title",
            "first",
        ],
        cwd=home,
    )
    _run(
        [
            "docket",
            "task-create",
            "--project-id",
            manifest["id"],
            "--title",
            "second",
        ],
        cwd=home,
    )
    proc = _run(["docket", "task-list", "--project-id", manifest["id"]], cwd=home)
    assert proc.returncode == 0
    assert "first" in proc.stdout
    assert "second" in proc.stdout


# ── migrate ─────────────────────────────────────────────────────────────────


def test_migrate_consolidates_legacy_docket(tmp_path: Path):
    # Define an eidos first, then plant a legacy .docket/ alongside.
    proc = _run(
        [
            "define",
            str(tmp_path),
            "--statement",
            "x",
            "--success-when",
            "a",
            "--failure-when",
            "b",
            "--success-when-not",
            "c",
            "--forges",
            "docket",
            "--json",
        ]
    )
    assert proc.returncode == 0
    legacy = tmp_path / ".docket"
    (legacy / "tasks").mkdir(parents=True)
    (legacy / "tasks" / "LEGACY-001 - x.md").write_text("legacy task file")
    proc = _run(["migrate", "--apply"], cwd=tmp_path)
    assert proc.returncode == 0
    # Legacy file moved into .eidos/docket/tasks/
    moved = tmp_path / ".eidos" / "docket" / "tasks" / "LEGACY-001 - x.md"
    assert moved.is_file()


def test_migrate_dry_run_does_not_move(tmp_path: Path):
    proc = _run(
        [
            "define",
            str(tmp_path),
            "--statement",
            "x",
            "--success-when",
            "a",
            "--failure-when",
            "b",
            "--success-when-not",
            "c",
            "--forges",
            "docket",
            "--json",
        ]
    )
    assert proc.returncode == 0
    legacy = tmp_path / ".docket"
    (legacy / "tasks").mkdir(parents=True)
    (legacy / "tasks" / "STAYS-001.md").write_text("should not move on dry-run")
    proc = _run(["migrate"], cwd=tmp_path)
    assert proc.returncode == 0
    # File still in legacy location after dry-run.
    assert (legacy / "tasks" / "STAYS-001.md").is_file()


# ── mcp serve via stdio ────────────────────────────────────────────────────


def test_mcp_serve_handshake_and_help():
    """Boot eidos mcp serve and exercise it via raw JSON-RPC."""
    proc = subprocess.Popen(
        [EIDOS, "mcp", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        def send(method, params=None, id=1):
            msg = {"jsonrpc": "2.0", "id": id, "method": method}
            if params is not None:
                msg["params"] = params
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        def notify(method, params=None):
            msg = {"jsonrpc": "2.0", "method": method}
            if params is not None:
                msg["params"] = params
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()

        init = send(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"},
            },
        )
        assert init["result"]["serverInfo"]["name"] == "eidos"
        notify("notifications/initialized")

        tools = send("tools/list", id=2)
        assert len(tools["result"]["tools"]) == 1
        assert tools["result"]["tools"][0]["name"] == "help"

        top = send("tools/call", {"name": "help", "arguments": {}}, id=3)
        text = top["result"]["content"][0]["text"]
        assert "eidos define" in text

        # Drill into a nested forge subcommand.
        nested = send(
            "tools/call",
            {"name": "help", "arguments": {"subcommand": "docket task-create"}},
            id=4,
        )
        text = nested["result"]["content"][0]["text"]
        assert "--title" in text
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


# ── close ─────────────────────────────────────────────────────────────────


def test_close_writes_pod_log(temp_eidos):
    home, _ = temp_eidos
    proc = _run(
        ["close", "abandoned", str(home), "--notes", "smoke complete", "--json"]
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["outcome"] == "abandoned"
    pod_log = home / ".eidos" / "pod.log"
    assert pod_log.is_file()
    content = pod_log.read_text()
    assert "CLOSE outcome=abandoned" in content


def test_close_supersede_requires_pointer(temp_eidos):
    home, _ = temp_eidos
    proc = _run(["close", "superseded", str(home)])
    assert proc.returncode != 0
    assert "--superseded-by" in (proc.stderr + proc.stdout)


# ── closeout ───────────────────────────────────────────────────────────────


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "smoke@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Smoke Test"], cwd=path, check=True)
    (path / "README.md").write_text("ok\n")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True, text=True)


def _path_with_fakebin(fakebin: Path) -> str:
    eidos_path = shutil.which(EIDOS)
    assert eidos_path
    return os.pathsep.join([str(fakebin), str(Path(eidos_path).parent), os.environ.get("PATH", "")])


def _write_fake_stepproof(fakebin: Path, *, audit_exit: int = 0, metrics: str = '{"ok": true}') -> None:
    fakebin.mkdir(parents=True, exist_ok=True)
    script = fakebin / "stepproof"
    script.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'if [ "$1" = "audit" ] && [ "$2" = "verify" ]; then',
                f"  echo audit-{audit_exit}",
                f"  exit {audit_exit}",
                "fi",
                'if [ "$1" = "metrics" ] && [ "$2" = "--json" ]; then',
                f"  printf '%s\\n' '{metrics}'",
                "  exit 0",
                "fi",
                "exit 2",
            ]
        )
        + "\n"
    )
    script.chmod(0o755)


def test_closeout_passes_for_clean_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins": []}')
    proc = _run(
        ["closeout", str(repo), "--json"],
        env={"EIDOS_CODEX_MARKETPLACE": str(marketplace)},
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["git"][0]["clean"] is True
    assert payload["stepproof"][0]["status"] == "absent"


def test_closeout_fails_for_dirty_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "dirty.txt").write_text("untracked\n")
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins": []}')
    proc = _run(
        ["closeout", str(repo), "--json"],
        env={"EIDOS_CODEX_MARKETPLACE": str(marketplace)},
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["git"][0]["untracked_count"] == 1


def test_closeout_catches_missing_codex_plugin(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    marketplace_root = tmp_path / ".agents" / "plugins"
    marketplace_root.mkdir(parents=True)
    marketplace = marketplace_root / "marketplace.json"
    marketplace.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "name": "missing",
                        "source": {"source": "local", "path": "./plugins/missing"},
                    }
                ]
            }
        )
    )
    proc = _run(
        ["closeout", str(repo), "--json"],
        env={"EIDOS_CODEX_MARKETPLACE": str(marketplace)},
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["codex_marketplace"]["missing"][0]["name"] == "missing"


def test_closeout_catches_incomplete_plugin_run(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    run_dir = repo / ".eidos" / "praxis" / "plugin_runs" / "learn-123"
    run_dir.mkdir(parents=True)
    (run_dir / "context.json").write_text("{}")
    (run_dir / "playbook.md").write_text("# learn\n")
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins": []}')
    proc = _run(
        ["closeout", str(repo), "--json"],
        env={"EIDOS_CODEX_MARKETPLACE": str(marketplace)},
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["plugin_runs"]["incomplete"][0]["path"].endswith("learn-123")
    suggestions = payload["plugin_runs"]["incomplete"][0]["suggestions"]
    assert any("eidos learn --status --work-dir" in s for s in suggestions)
    assert any("eidos learn --finish --work-dir" in s for s in suggestions)


def test_closeout_reports_stepproof_state_without_installed_cli(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / ".stepproof").mkdir()
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins": []}')

    from eidos_cli.cli.closeout import build_report

    with patch("eidos_cli.stepproof.shutil.which", return_value=None):
        payload = build_report(str(repo), [], True)

    assert payload["ok"] is True
    assert payload["stepproof"][0]["status"] == "advisory-pass"
    assert payload["stepproof"][0]["installed"] is False


def test_closeout_fails_on_corrupt_stepproof_audit(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / ".stepproof").mkdir()
    fakebin = tmp_path / "fakebin"
    _write_fake_stepproof(fakebin, audit_exit=1)
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins": []}')

    proc = _run(
        ["closeout", str(repo), "--json"],
        env={
            "EIDOS_CODEX_MARKETPLACE": str(marketplace),
            "PATH": _path_with_fakebin(fakebin),
        },
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["stepproof"][0]["audit"]["ok"] is False


# ── cleanup ─────────────────────────────────────────────────────────────────


def test_cleanup_classifies_dirty_source_and_derivative_surfaces(tmp_path: Path):
    source_root = tmp_path / "repos-eidos-agi"
    plugin_root = tmp_path / "plugins"
    cache_root = tmp_path / ".codex" / "plugins" / "cache" / "eidos-agi"
    source = source_root / "demo"
    source.mkdir(parents=True)
    _init_git_repo(source)
    (source / ".codex-plugin").mkdir()
    (source / ".codex-plugin" / "plugin.json").write_text('{"name": "demo"}\n')
    (source / "demo.py").write_text("print('dirty source')\n")
    mirror = plugin_root / "demo"
    (mirror / ".codex-plugin").mkdir(parents=True)
    (mirror / ".codex-plugin" / "plugin.json").write_text('{"name": "demo"}\n')
    cache = cache_root / "demo" / "0.1.0"
    cache.mkdir(parents=True)
    _init_git_repo(cache)
    (cache / ".codex-plugin").mkdir()
    (cache / ".codex-plugin" / "plugin.json").write_text('{"name": "demo"}\n')
    (cache / ".agents").mkdir()
    (cache / ".agents" / "skills").write_text("generated cache drift\n")

    proc = _run(
        [
            "cleanup",
            "--source-root",
            str(source_root),
            "--plugin-root",
            str(plugin_root),
            "--cache-root",
            str(cache_root),
            "--json",
        ]
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    source_item = next(item for item in payload["surfaces"] if item["path"] == str(source))
    mirror_item = next(item for item in payload["surfaces"] if item["path"] == str(mirror))
    cache_item = next(item for item in payload["surfaces"] if item["path"] == str(cache))
    assert source_item["kind"] == "canonical-source"
    assert source_item["status"] == "needs-shipment"
    assert "eidos ship" in source_item["next_actions"][0]
    assert mirror_item["kind"] == "local-plugin-mirror"
    assert mirror_item["source_of_truth"] == "derivative"
    assert cache_item["kind"] == "installed-cache"
    assert cache_item["status"] == "needs-refresh"
    assert "Do not commit from the cache" in cache_item["next_actions"][0]


def test_cleanup_passes_for_clean_source_repo(tmp_path: Path):
    source_root = tmp_path / "repos-eidos-agi"
    plugin_root = tmp_path / "plugins"
    cache_root = tmp_path / "cache"
    source = source_root / "demo"
    source.mkdir(parents=True)
    _init_git_repo(source)

    proc = _run(
        [
            "cleanup",
            "--source-root",
            str(source_root),
            "--plugin-root",
            str(plugin_root),
            "--cache-root",
            str(cache_root),
            "--json",
        ]
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["surfaces"][0]["status"] == "clean"


def test_closeout_fails_for_dirty_code_without_agentic_protocol(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "tool.py").write_text("print('code-only')\n")
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins": []}')

    proc = _run(
        ["closeout", str(repo), "--json"],
        env={"EIDOS_CODEX_MARKETPLACE": str(marketplace)},
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["agentic_first"]["ok"] is False
    assert payload["agentic_first"]["repos"][0]["dirty_code_changes"] == ["tool.py"]


def test_closeout_allows_dirty_code_with_agentic_protocol(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "tool.py").write_text("print('paired')\n")
    guides = repo / "eidos_cli" / "guides"
    guides.mkdir(parents=True)
    (guides / "loop.md").write_text("# Loop\n\nAgentic protocol changed.\n")
    marketplace = tmp_path / "marketplace.json"
    marketplace.write_text('{"plugins": []}')

    proc = _run(
        ["closeout", str(repo), "--json"],
        env={"EIDOS_CODEX_MARKETPLACE": str(marketplace)},
    )

    payload = json.loads(proc.stdout)
    assert payload["agentic_first"]["ok"] is True
    assert payload["agentic_first"]["repos"][0]["agentic_protocol_changes"] == [
        "eidos_cli/guides/loop.md"
    ]


# ── ship ───────────────────────────────────────────────────────────────────


def test_ship_passes_minimal_clean_repo_without_build(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    proc = _run(["ship", str(repo), "--skip-build", "--skip-tests", "--skip-live", "--json"])

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["agent_contract"]["role"] == "one-shot shipment gate"
    assert payload["agent_contract"]["invokes_subagents"] is False
    assert payload["agent_contract"]["max_repair_iterations"] == 0
    assert any(g["id"] == "git-clean-pushed" and g["status"] == "pass" for g in payload["gates"])
    assert any(g["id"] == "artifact-scan" and g["status"] == "pass" for g in payload["gates"])
    agentic_gate = next(g for g in payload["gates"] if g["id"] == "agentic-first-doctrine")
    assert agentic_gate["status"] == "skip"


def test_ship_fails_on_generated_artifacts(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "__pycache__").mkdir()

    proc = _run(
        ["ship", str(repo), "--skip-build", "--skip-tests", "--skip-live", "--no-clean", "--json"]
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    artifact_gate = next(g for g in payload["gates"] if g["id"] == "artifact-scan")
    assert artifact_gate["status"] == "fail"
    assert "__pycache__" in artifact_gate["artifacts"]


def test_ship_fails_code_repo_without_agentic_first_proof(tmp_path: Path):
    repo = tmp_path / "repo"
    pkg = repo / "src" / "demo_pkg"
    pkg.mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                'requires = ["setuptools>=68.0"]',
                'build-backend = "setuptools.build_meta"',
                "",
                "[project]",
                'name = "demo-pkg"',
                'version = "0.1.0"',
                'requires-python = ">=3.10"',
            ]
        )
    )
    (pkg / "__init__.py").write_text('__version__ = "0.1.0"\n')
    _init_git_repo(repo)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "package"], cwd=repo, check=True, capture_output=True, text=True)

    proc = _run(["ship", str(repo), "--skip-build", "--skip-tests", "--skip-live", "--json"])

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    gate = next(g for g in payload["gates"] if g["id"] == "agentic-first-doctrine")
    assert gate["status"] == "fail"
    assert "Before coding" in gate["detail"]


def test_ship_passes_code_repo_with_agentic_first_manifest(tmp_path: Path):
    repo = tmp_path / "repo"
    pkg = repo / "src" / "demo_pkg"
    pkg.mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                'requires = ["setuptools>=68.0"]',
                'build-backend = "setuptools.build_meta"',
                "",
                "[project]",
                'name = "demo-pkg"',
                'version = "0.1.0"',
                'requires-python = ">=3.10"',
            ]
        )
    )
    (pkg / "__init__.py").write_text('__version__ = "0.1.0"\n')
    ship_dir = repo / ".eidos" / "ship"
    ship_dir.mkdir(parents=True)
    (ship_dir / "manifest.toml").write_text(
        "\n".join(
            [
                "[repo]",
                "skip_tests = true",
                "skip_build = true",
                "skip_live = true",
                "",
                "[gates]",
                'builtin = ["git-clean-pushed", "agentic-first-doctrine"]',
                "",
                "[agentic_first]",
                'code_justification = "evidence gate"',
                'agentic_capability = "Makes closeout enforce proof before software progress."',
                'non_code_paths_considered = ["instruction", "routing", "proof"]',
            ]
        )
    )
    _init_git_repo(repo)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "package"], cwd=repo, check=True, capture_output=True, text=True)

    proc = _run(["ship", str(repo), "--json"])

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    gate = next(g for g in payload["gates"] if g["id"] == "agentic-first-doctrine")
    assert gate["status"] == "pass"
    assert payload["agent_contract"]["agentic_first"]["title"] == (
        "AGENTIC-FIRST SOFTWARE-SKEPTICAL DOCTRINE"
    )


def test_ship_catches_runtime_version_mismatch(tmp_path: Path):
    repo = tmp_path / "repo"
    pkg = repo / "src" / "demo_pkg"
    pkg.mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[build-system]",
                'requires = ["setuptools>=68.0"]',
                'build-backend = "setuptools.build_meta"',
                "",
                "[project]",
                'name = "demo-pkg"',
                'version = "0.2.0"',
                'requires-python = ">=3.10"',
                "",
                "[tool.setuptools.packages.find]",
                'where = ["src"]',
            ]
        )
    )
    (pkg / "__init__.py").write_text('__version__ = "0.1.0"\n')
    _init_git_repo(repo)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "package"], cwd=repo, check=True, capture_output=True, text=True)

    proc = _run(["ship", str(repo), "--skip-tests", "--skip-live", "--json"])

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    wheel_gate = next(g for g in payload["gates"] if g["id"] == "wheel-install")
    assert wheel_gate["status"] == "fail"
    assert "metadata=0.2.0 runtime=0.1.0" in wheel_gate["stdout_tail"]


def test_ship_uses_repo_local_manifest(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    ship_dir = repo / ".eidos" / "ship"
    ship_dir.mkdir(parents=True)
    (ship_dir / "manifest.toml").write_text(
        "\n".join(
            [
                "[repo]",
                'style = "minimal-test-shipment"',
                "skip_tests = true",
                "skip_build = true",
                "skip_live = true",
                "",
                "[gates]",
                'builtin = ["git-clean-pushed", "artifact-scan", "post-clean-artifact-scan"]',
                "",
                "[learnings]",
                'do_not = ["do not run package gates for this fixture"]',
                'yes = ["ship by proving git cleanliness and artifact cleanliness"]',
                "",
                "[evidence]",
                "auto_write = true",
            ]
        )
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "ship manifest"], cwd=repo, check=True, capture_output=True, text=True)

    proc = _run(["ship", str(repo), "--json"])

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["manifest"].endswith(".eidos/ship/manifest.toml")
    assert payload["shipment_style"] == "minimal-test-shipment"
    assert payload["evidence_path"].endswith(".eidos/ship/shipments/" + Path(payload["evidence_path"]).name)
    assert Path(payload["evidence_path"]).is_file()
    assert payload["do_not"] == ["do not run package gates for this fixture"]
    assert [g["id"] for g in payload["gates"]] == [
        "git-clean-pushed",
        "artifact-scan",
        "post-clean-artifact-scan",
    ]


def test_ship_runs_manifest_custom_gate(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    ship_dir = repo / ".eidos" / "ship"
    ship_dir.mkdir(parents=True)
    (ship_dir / "manifest.toml").write_text(
        "\n".join(
            [
                "[repo]",
                "skip_tests = true",
                "skip_build = true",
                "skip_live = true",
                "",
                "[gates]",
                'builtin = ["git-clean-pushed"]',
                "",
                "[[custom_gate]]",
                'id = "repo-specific-proof"',
                'facet = "custom"',
                'command = "test -f README.md"',
                'pass_detail = "README proof exists."',
                'fail_detail = "README proof missing."',
            ]
        )
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "custom manifest"], cwd=repo, check=True, capture_output=True, text=True)

    proc = _run(["ship", str(repo), "--json"])

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    custom = next(g for g in payload["gates"] if g["id"] == "repo-specific-proof")
    assert custom["status"] == "pass"


def test_ship_rejects_agent_custom_gate_kind(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    ship_dir = repo / ".eidos" / "ship"
    ship_dir.mkdir(parents=True)
    (ship_dir / "manifest.toml").write_text(
        "\n".join(
            [
                "[repo]",
                "skip_tests = true",
                "skip_build = true",
                "skip_live = true",
                "",
                "[gates]",
                'builtin = ["git-clean-pushed"]',
                "",
                "[[custom_gate]]",
                'id = "agent-review"',
                'kind = "agent-review"',
                'command = "echo review"',
            ]
        )
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "agent gate"], cwd=repo, check=True, capture_output=True, text=True)

    proc = _run(["ship", str(repo), "--json"])

    assert proc.returncode != 0
    assert "agent/subagent gates are not allowed" in (proc.stderr + proc.stdout)


def test_ship_fails_when_required_stepproof_unavailable(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    ship_dir = repo / ".eidos" / "ship"
    ship_dir.mkdir(parents=True)
    (ship_dir / "manifest.toml").write_text(
        "\n".join(
            [
                "[repo]",
                "skip_tests = true",
                "skip_build = true",
                "skip_live = true",
                "",
                "[gates]",
                'builtin = ["git-clean-pushed", "stepproof-audit"]',
                "",
                "[stepproof]",
                "required = true",
                "audit = true",
            ]
        )
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "require stepproof"], cwd=repo, check=True, capture_output=True, text=True)

    proc = _run(["ship", str(repo), "--json"])

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    gate = next(g for g in payload["gates"] if g["id"] == "stepproof-audit")
    assert gate["status"] == "fail"


def test_ship_records_stepproof_audit_and_metrics(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / ".stepproof").mkdir()
    ship_dir = repo / ".eidos" / "ship"
    ship_dir.mkdir(parents=True)
    (ship_dir / "manifest.toml").write_text(
        "\n".join(
            [
                "[repo]",
                "skip_tests = true",
                "skip_build = true",
                "skip_live = true",
                "",
                "[gates]",
                'builtin = ["git-clean-pushed", "stepproof-audit"]',
                "",
                "[stepproof]",
                "required = true",
                "audit = true",
                "metrics = true",
            ]
        )
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "require stepproof"], cwd=repo, check=True, capture_output=True, text=True)
    fakebin = tmp_path / "fakebin"
    _write_fake_stepproof(fakebin, audit_exit=0, metrics='{"deny_count": 0}')

    proc = _run(["ship", str(repo), "--json"], env={"PATH": _path_with_fakebin(fakebin)})

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    gate = next(g for g in payload["gates"] if g["id"] == "stepproof-audit")
    assert gate["status"] == "pass"
    assert gate["data"]["audit"]["ok"] is True
    assert gate["data"]["metrics"]["data"]["deny_count"] == 0


# ── help / version sanity ──────────────────────────────────────────────────


def test_top_level_help_lists_scope_verbs():
    proc = _run(["--help"])
    assert proc.returncode == 0
    for verb in ("define", "enter", "status", "activate", "tick", "closeout", "cleanup", "ship", "close", "learn"):
        assert verb in proc.stdout


def test_top_level_help_lists_forge_namespaces():
    proc = _run(["--help"])
    for ns in ("telos", "research", "governor", "docket", "praxis"):
        assert ns in proc.stdout


def test_guides_include_agentic_first_doctrine():
    guide = _run(["guide"])
    loop = _run(["guide", "loop"])

    assert guide.returncode == 0
    assert loop.returncode == 0
    assert "AGENTIC-FIRST SOFTWARE-SKEPTICAL DOCTRINE" in guide.stdout
    assert "Eidos prefers agentic improvement over software production." in guide.stdout
    assert "Before coding" in loop.stdout


def test_do_marks_production_migration_as_requiring_stepproof(temp_eidos):
    home, _ = temp_eidos
    task = home / ".eidos" / "docket" / "tasks" / "TASK-9001-prod-migration.md"
    task.write_text(
        "\n".join(
            [
                "---",
                "id: TASK-9001",
                "title: Run production migration",
                "tags:",
                "  - migration",
                "definition-of-done:",
                "  - migration proof attached",
                "---",
                "Run the production database migration with ceremony.",
            ]
        )
    )

    proc = _run(["do", "TASK-9001", "--json"], cwd=home)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["cardinality"]["requires_step_proof"] is True
    assert "step-proof-required" in payload["cardinality"]["triggers_fired"]
    context = json.loads(Path(payload["context_bundle"]).read_text())
    assert context["cardinality"]["requires_step_proof"] is True


def test_do_emits_agentic_first_preflight(temp_eidos):
    home, _ = temp_eidos
    task = home / ".eidos" / "docket" / "tasks" / "TASK-9002-agentic.md"
    task.write_text(
        "\n".join(
            [
                "---",
                "id: TASK-9002",
                "title: Improve agentic selection pressure",
                "definition-of-done:",
                "  - doctrine emitted",
                "---",
                "Make Eidos prefer agentic behavior over code-only work.",
            ]
        )
    )

    proc = _run(["do", "TASK-9002", "--json"], cwd=home)

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["agentic_first"]["title"] == "AGENTIC-FIRST SOFTWARE-SKEPTICAL DOCTRINE"
    context = json.loads(Path(payload["context_bundle"]).read_text())
    assert context["agentic_first"]["warning"] == "Do not write code merely because code is possible."
    plan = Path(payload["plan_path"]).read_text()
    assert "## Agentic-First Preflight" in plan
    assert "Why code is necessary:" in plan


# ── plugin runtime (ADR-009) ───────────────────────────────────────────────


def test_plugin_list_shows_bundled_learn():
    """First-run bootstrap copies the bundled `learn` plugin to ~/.eidos/plugins."""
    proc = _run(["plugin", "list"])
    assert proc.returncode == 0, proc.stderr
    assert "learn" in proc.stdout
    assert "alias=learn" in proc.stdout


def test_plugin_show_bundled_learn():
    proc = _run(["plugin", "show", "learn"])
    assert proc.returncode == 0, proc.stderr
    assert "slug: learn" in proc.stdout
    assert "playbook" in proc.stdout.lower()


def test_plugin_run_learn_emits_context_bundle(temp_eidos):
    home, _ = temp_eidos
    proc = _run(["plugin", "run", "learn", "--json"], cwd=home)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True
    wd = Path(out["work_dir"])
    assert wd.is_dir()
    assert (wd / "context.json").is_file()
    assert (wd / "playbook.md").is_file()
    assert (wd / "draft").is_dir()


def test_learn_status_with_no_runs(tmp_path: Path):
    user_home = tmp_path / "home"
    neutral_cwd = tmp_path / "neutral"
    user_home.mkdir()
    neutral_cwd.mkdir()
    proc = _run(
        ["learn", "--status", "--json"],
        cwd=neutral_cwd,
        env={"HOME": str(user_home)},
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["runs"] == []


def test_learn_status_for_incomplete_run(temp_eidos):
    home, _ = temp_eidos
    run_dir = home / ".eidos" / "praxis" / "plugin_runs" / "learn-123"
    run_dir.mkdir(parents=True)
    (run_dir / "context.json").write_text("{}")
    (run_dir / "playbook.md").write_text("# learn\n")
    proc = _run(["learn", "--status", "--work-dir", str(run_dir), "--json"], cwd=home)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["runs"][0]["status"] == "needs-draft"
    assert payload["runs"][0]["draft_file_count"] == 0


def test_learn_continue_preserves_verify_behavior(temp_eidos):
    home, _ = temp_eidos
    start = _run(["learn", "--json"], cwd=home)
    assert start.returncode == 0, start.stderr
    work_dir = json.loads(start.stdout)["work_dir"]
    proc = _run(["learn", "--continue", "--work-dir", work_dir, "--json"], cwd=home)
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "draft_dir" in payload["verify"]["reasons"][0] or "missing required files" in payload["verify"]["reasons"][0]


def test_learn_finish_refuses_invalid_draft(temp_eidos):
    home, _ = temp_eidos
    start = _run(["learn", "--json"], cwd=home)
    assert start.returncode == 0, start.stderr
    work_dir = json.loads(start.stdout)["work_dir"]
    proc = _run(["learn", "--finish", "--work-dir", work_dir, "--json"], cwd=home)
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["verify"]["passed"] is False


def test_learn_finish_installs_valid_draft(temp_eidos, tmp_path: Path):
    home, _ = temp_eidos
    user_home = tmp_path / "user-home"
    user_home.mkdir()
    start = _run(["learn", "--json"], cwd=home, env={"HOME": str(user_home)})
    assert start.returncode == 0, start.stderr
    payload = json.loads(start.stdout)
    work_dir = Path(payload["work_dir"])
    draft = work_dir / "draft"
    draft.joinpath("plugin.yaml").write_text(
        "\n".join(
            [
                "slug: learned-closeout-test",
                "version: 0.1.0",
                "description: Test plugin generated by learn finish.",
                "when_to_fire:",
                "  - when testing learn finish",
                "owner_forge: praxis",
                "required_evidence:",
                "  - playbook.md",
                "",
            ]
        )
    )
    draft.joinpath("playbook.md").write_text("# Learned Closeout Test\n\n" + ("Do the thing.\n" * 30))
    draft.joinpath("provenance.json").write_text(
        json.dumps(
            {
                "source_turns": ["TASK-0001.120000.md"],
                "source_eidos_id": "smoke",
                "promoted_by": "learn",
                "promoted_at": "2026-05-23",
                "rationale": "Exercise learn finish install behavior.",
            }
        )
    )
    proc = _run(
        ["learn", "--finish", "--work-dir", str(work_dir), "--scope", "global", "--json"],
        cwd=home,
        env={"HOME": str(user_home)},
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    installed = user_home / ".eidos" / "plugins" / "learned-closeout-test"
    assert installed.joinpath("plugin.yaml").is_file()


def test_perceive_matches_required_plugin(temp_eidos):
    """A task with required_plugins: [<slug>] is marked REQUIRED in matched_plugins."""
    home, _ = temp_eidos
    # Read project id from the docket config.
    docket_cfg = json.loads((home / ".eidos" / "docket" / "docket.json").read_text())
    project_id = docket_cfg["id"]
    # Create a task.
    proc = _run(
        [
            "docket",
            "task-create",
            "--project-id",
            project_id,
            "--title",
            "task for required-plugin test",
            "--description",
            "x",
        ],
        cwd=home,
    )
    assert proc.returncode == 0, proc.stderr
    # Inject required_plugins into the frontmatter.
    task_files = list((home / ".eidos" / "docket" / "tasks").glob("TASK-*.md"))
    assert len(task_files) == 1
    tp = task_files[0]
    text = tp.read_text()
    assert text.startswith("---\n")
    end = text.find("\n---", 4)
    augmented = (
        text[:end] + "\nrequired_plugins:\n  - learn\n" + text[end:]
    )
    tp.write_text(augmented)
    # Run eidos do --json and check matched_plugins.
    proc = _run(["do", "TASK-0001", "--json"], cwd=home)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    matched = payload.get("matched_plugins") or []
    slugs = {m["slug"] for m in matched}
    assert "learn" in slugs, f"learn not in matched_plugins: {matched}"
    learn = next(m for m in matched if m["slug"] == "learn")
    assert learn["required"] is True
    # Playbook should be copied into the context bundle.
    ctx_dir = home / ".eidos" / "docket" / "contexts" / "TASK-0001"
    assert (ctx_dir / "plugins" / "learn.md").is_file()


def test_perceive_no_match_when_no_signals(temp_eidos):
    home, _ = temp_eidos
    docket_cfg = json.loads((home / ".eidos" / "docket" / "docket.json").read_text())
    project_id = docket_cfg["id"]
    proc = _run(
        [
            "docket",
            "task-create",
            "--project-id",
            project_id,
            "--title",
            "trivial",
            "--description",
            "x",
        ],
        cwd=home,
    )
    assert proc.returncode == 0
    proc = _run(["do", "TASK-0001", "--json"], cwd=home)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload.get("matched_plugins") == []
