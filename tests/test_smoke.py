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
import subprocess
import tempfile
from pathlib import Path

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


# ── ship ───────────────────────────────────────────────────────────────────


def test_ship_passes_minimal_clean_repo_without_build(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)

    proc = _run(["ship", str(repo), "--skip-build", "--skip-tests", "--skip-live", "--json"])

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert any(g["id"] == "git-clean-pushed" and g["status"] == "pass" for g in payload["gates"])
    assert any(g["id"] == "artifact-scan" and g["status"] == "pass" for g in payload["gates"])


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


# ── help / version sanity ──────────────────────────────────────────────────


def test_top_level_help_lists_scope_verbs():
    proc = _run(["--help"])
    assert proc.returncode == 0
    for verb in ("define", "enter", "status", "activate", "tick", "closeout", "ship", "close", "learn"):
        assert verb in proc.stdout


def test_top_level_help_lists_forge_namespaces():
    proc = _run(["--help"])
    for ns in ("telos", "research", "governor", "docket", "praxis"):
        assert ns in proc.stdout


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
