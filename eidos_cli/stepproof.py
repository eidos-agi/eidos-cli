"""StepProof discovery and CLI-backed verification helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _run(cmd: list[str], cwd: Path, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def _tail(text: str, limit: int = 1200) -> str:
    text = text.strip()
    return text[-limit:] if len(text) > limit else text


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _pid_alive(pid: Any) -> bool | None:
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return None
    if pid_int <= 0:
        return False
    try:
        os.kill(pid_int, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def _heartbeat_status(path: Path) -> dict[str, Any] | None:
    data = _read_json(path)
    if not data:
        return None
    expires_raw = data.get("expires_at")
    expired = None
    if isinstance(expires_raw, str):
        try:
            expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
            expired = expires < datetime.now(timezone.utc)
        except ValueError:
            expired = None
    return {
        "path": str(path),
        "status": data.get("status"),
        "expires_at": expires_raw,
        "expired": expired,
    }


def check_repo(repo: Path, *, required: bool = False, audit: bool = True, metrics: bool = False) -> dict[str, Any]:
    """Return StepProof state for *repo* without importing StepProof packages."""
    repo = repo.expanduser().resolve()
    state = repo / ".stepproof"
    exe = shutil.which("stepproof")
    exists = state.is_dir()
    result: dict[str, Any] = {
        "path": str(repo),
        "kind": "stepproof",
        "ok": True,
        "status": "absent",
        "required": required,
        "installed": bool(exe),
        "state_dir": str(state) if exists else None,
        "active_run": None,
        "runtime": None,
        "runs_count": 0,
        "audit": {"checked": False, "ok": None},
        "metrics": None,
        "detail": "No .stepproof state found.",
    }
    if not exists:
        if required:
            result.update(ok=False, status="needs-attention", detail="StepProof is required but .stepproof is absent.")
        return result

    active = _read_json(state / "active-run.json")
    if active:
        run_id = active.get("run_id")
        hb = _heartbeat_status(state / "runs" / str(run_id) / "heartbeat.json") if run_id else None
        result["active_run"] = {
            "run_id": run_id,
            "current_step": active.get("current_step"),
            "template_id": active.get("template_id"),
            "allowed_tools": active.get("allowed_tools") or [],
            "heartbeat": hb,
        }

    runtime = _read_json(state / "runtime.url")
    if runtime:
        result["runtime"] = {
            "url": runtime.get("url"),
            "pid": runtime.get("pid"),
            "started_at": runtime.get("started_at"),
            "alive": _pid_alive(runtime.get("pid")),
        }

    runs_dir = state / "runs"
    if runs_dir.is_dir():
        result["runs_count"] = len([p for p in runs_dir.iterdir() if p.is_dir()])

    if not exe:
        status = "needs-attention" if required else "advisory-pass"
        result.update(
            ok=not required,
            status=status,
            detail=(
                "StepProof state exists, but stepproof CLI is not installed."
                if not required
                else "StepProof is required, but stepproof CLI is not installed."
            ),
        )
        return result

    if audit:
        try:
            proc = _run([exe, "audit", "verify"], repo, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as e:
            result["audit"] = {"checked": True, "ok": False, "error": str(e)}
            result.update(ok=False, status="needs-attention", detail="StepProof audit verification could not run.")
            return result
        result["audit"] = {
            "checked": True,
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        }
        if proc.returncode != 0:
            result.update(ok=False, status="needs-attention", detail="StepProof audit verification failed.")
            return result

    if metrics:
        try:
            proc = _run([exe, "metrics", "--json"], repo, timeout=30)
            parsed: Any
            try:
                parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
            except json.JSONDecodeError:
                parsed = None
            result["metrics"] = {
                "checked": True,
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "data": parsed,
                "stdout_tail": _tail(proc.stdout),
                "stderr_tail": _tail(proc.stderr),
            }
        except (OSError, subprocess.TimeoutExpired) as e:
            result["metrics"] = {"checked": True, "ok": False, "error": str(e)}

    result.update(
        ok=True,
        status="required-pass" if required else "advisory-pass",
        detail="StepProof state verified." if audit else "StepProof state detected.",
    )
    return result
