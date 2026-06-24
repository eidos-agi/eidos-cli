"""Top-level health and doctor commands."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Annotated, Any

import httpx
import typer

from ..config import VAULT_URL


VALID_CODEX_SERVICE_TIERS = {"fast", "flex"}
TASKR_COMMANDS = ("skillflow_execute", "taskr_triage", "taskr_governance_approve")
FACULTY_CANDIDATES = {
    "cept",
    "converge",
    "eidos-skills-hub",
    "eidos-storemetheus",
    "felix",
    "foreman",
    "pavo",
    "rhea",
    "storemetheus",
    "zoltar",
}


def build_health_report() -> dict[str, Any]:
    """Build a local health report without model calls or repair side effects."""
    checks = [
        _vault_check(),
        _codex_cli_check(),
        _taskr_check(),
        _faculty_check(),
    ]
    return {
        "ok": not any(c["status"] == "fail" for c in checks),
        "checks": checks,
    }


def _vault_check() -> dict[str, Any]:
    try:
        resp = httpx.get(f"{VAULT_URL}/health", timeout=5)
        data = resp.json()
        status = "pass" if resp.is_success and data.get("status") == "ok" else "fail"
        return {
            "id": "vault",
            "status": status,
            "detail": data.get("status", "unknown"),
            "data": data,
        }
    except Exception as e:
        return {"id": "vault", "status": "fail", "detail": f"down ({e})"}


def _codex_cli_check() -> dict[str, Any]:
    exe = shutil.which("codex")
    config_path = _codex_config_path()
    if not exe:
        return {
            "id": "codex-cli",
            "status": "warn",
            "detail": "codex command not found",
            "config_path": str(config_path),
        }
    service_tier = _top_level_toml_value(config_path, "service_tier")
    if service_tier and service_tier not in VALID_CODEX_SERVICE_TIERS:
        return {
            "id": "codex-cli",
            "status": "warn",
            "detail": (
                f"invalid service_tier {service_tier!r}; expected fast or flex"
            ),
            "path": exe,
            "config_path": str(config_path),
        }
    return {
        "id": "codex-cli",
        "status": "pass",
        "detail": "codex command found and config is sane",
        "path": exe,
        "config_path": str(config_path),
    }


def _codex_config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser() / "config.toml"


def _top_level_toml_value(path: Path, key: str) -> str | None:
    if not path.is_file():
        return None
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            return None
        name, sep, value = line.partition("=")
        if sep and name.strip() == key:
            return value.strip().strip('"').strip("'")
    return None


def _taskr_check() -> dict[str, Any]:
    missing = [cmd for cmd in TASKR_COMMANDS if shutil.which(cmd) is None]
    if missing:
        return {
            "id": "taskr",
            "status": "warn",
            "detail": "missing optional workflow commands",
            "missing": missing,
        }
    return {
        "id": "taskr",
        "status": "pass",
        "detail": "optional workflow commands found",
        "commands": list(TASKR_COMMANDS),
    }


def _faculty_check() -> dict[str, Any]:
    from ..plugin_runtime.store import list_plugins
    from ..scope.resolver import resolve_from_cwd

    missing = []
    for plugin in list_plugins(resolve_from_cwd()):
        if plugin.slug not in FACULTY_CANDIDATES:
            continue
        if not (plugin.manifest.get("faculty") or plugin.manifest.get("subagent")):
            missing.append({"slug": plugin.slug, "path": str(plugin.path)})
    if missing:
        return {
            "id": "faculties",
            "status": "warn",
            "detail": "specialist plugins missing faculty metadata",
            "missing": missing,
        }
    return {
        "id": "faculties",
        "status": "pass",
        "detail": "installed specialist plugins declare faculty metadata",
    }


def _format_report(report: dict[str, Any]) -> str:
    lines = []
    for check in report["checks"]:
        if check["id"] == "vault":
            if check.get("data") is not None:
                lines.append(
                    f"vault: {check['detail']} — {json.dumps(check['data'])}"
                )
            else:
                lines.append(f"vault: {check['detail']}")
            continue
        marker = check["status"]
        detail = check["detail"]
        if check["id"] == "taskr" and check.get("missing"):
            detail = f"{detail}: {', '.join(check['missing'])}"
        if check["id"] == "faculties" and check.get("missing"):
            slugs = ", ".join(item["slug"] for item in check["missing"])
            detail = f"{detail}: {slugs}"
        lines.append(f"{check['id']}: {marker} — {detail}")
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    @app.command("health")
    def cmd_health(
        json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
    ) -> None:
        """Check platform and local agent health."""
        report = build_health_report()
        typer.echo(json.dumps(report, default=str) if json_ else _format_report(report))

    @app.command("doctor")
    def cmd_doctor(
        json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
    ) -> None:
        """Check local agent prerequisite surfaces."""
        report = build_health_report()
        typer.echo(json.dumps(report, default=str) if json_ else _format_report(report))
