"""Vault verbs: ``eidos vault get | set | list | rm | keys ...``."""

from __future__ import annotations

import sys
from typing import Annotated, Optional

import typer

from ..api import vault_request

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


@app.command("get")
def cmd_get(
    path: Annotated[str, typer.Argument(help="Secret path.")],
) -> None:
    """Read a secret by path."""
    resp = vault_request("GET", f"/api/secrets/{path}")
    if resp.status_code == 404:
        typer.echo(f"error: not found: {path}", err=True)
        raise typer.Exit(code=1)
    if resp.status_code == 403:
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = ""
        typer.echo(f"error: forbidden: {detail}", err=True)
        raise typer.Exit(code=1)
    typer.echo(resp.json()["value"])


@app.command("set")
def cmd_set(
    path: Annotated[str, typer.Argument(help="Secret path.")],
    value: Annotated[
        Optional[str],
        typer.Argument(help="The secret value. Omit when using --stdin."),
    ] = None,
    description: Annotated[
        str, typer.Option("--description", "-d", help="Secret description.")
    ] = "",
    from_stdin: Annotated[
        bool,
        typer.Option(
            "--stdin",
            help="Read VALUE from stdin (avoids exposing it in argv / shell history).",
        ),
    ] = False,
) -> None:
    """Create or update a secret.

    Pass VALUE as the second positional argument, OR pass --stdin and pipe the
    value on stdin. --stdin is preferred for sensitive values.
    """
    if from_stdin:
        if value is not None:
            typer.echo(
                "--stdin and a positional VALUE are mutually exclusive.", err=True
            )
            raise typer.Exit(code=2)
        value = sys.stdin.read()
        if value.endswith("\n"):
            value = value[:-1]
        if not value:
            typer.echo("--stdin received an empty value; refusing to write.", err=True)
            raise typer.Exit(code=2)
    elif value is None:
        typer.echo("Missing VALUE. Pass it as an argument or use --stdin.", err=True)
        raise typer.Exit(code=2)

    resp = vault_request(
        "POST",
        "/api/secrets",
        json={"path": path, "value": value, "description": description},
    )
    if resp.status_code == 403:
        try:
            detail = resp.json().get("detail", "")
        except Exception:
            detail = ""
        typer.echo(f"error: forbidden: {detail}", err=True)
        raise typer.Exit(code=1)
    data = resp.json()
    typer.echo(f"{data['action']}: {data['path']}")


@app.command("list")
def cmd_list() -> None:
    """List all secrets (paths only, no values)."""
    resp = vault_request("GET", "/api/secrets")
    for s in resp.json():
        desc = f"  ({s['description']})" if s.get("description") else ""
        typer.echo(f"{s['path']}{desc}")


@app.command("rm")
def cmd_rm(
    path: Annotated[str, typer.Argument(help="Secret path.")],
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")
    ] = False,
) -> None:
    """Delete a secret."""
    if not yes:
        confirm = typer.confirm(f"Delete this secret? ({path})")
        if not confirm:
            raise typer.Abort()
    resp = vault_request("DELETE", f"/api/secrets/{path}")
    if resp.status_code == 404:
        typer.echo(f"error: not found: {path}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Deleted: {path}")


# ── Vault keys subgroup ──────────────────────────────────────────────────────


keys_app = typer.Typer(
    no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False
)
app.add_typer(keys_app, name="keys", help="Manage API keys.")


@keys_app.command("list")
def keys_list() -> None:
    """List API keys."""
    resp = vault_request("GET", "/api/keys")
    for k in resp.json():
        scopes = f"  scopes={','.join(k['scopes'])}" if k.get("scopes") else ""
        paths = f"  paths={','.join(k['paths'])}" if k.get("paths") else ""
        typer.echo(
            f"{k['prefix']}...  {k['name']}  owner={k['owner']}{paths}{scopes}"
        )


@keys_app.command("create")
def keys_create(
    name: Annotated[str, typer.Option("--name", "-n", help="Key name.")],
    paths: Annotated[
        Optional[str],
        typer.Option("--paths", "-p", help="Comma-separated vault path globs."),
    ] = None,
    scopes: Annotated[
        Optional[str], typer.Option("--scopes", "-s", help="Comma-separated scopes.")
    ] = None,
    expires: Annotated[
        Optional[str], typer.Option("--expires", help="Expiry (ISO format).")
    ] = None,
) -> None:
    """Create a new API key."""
    body: dict = {"name": name}
    if paths:
        body["allowed_paths"] = [p.strip() for p in paths.split(",")]
    if scopes:
        body["scopes"] = [s.strip() for s in scopes.split(",")]
    if expires:
        body["expires_at"] = expires
    resp = vault_request("POST", "/api/keys", json=body)
    data = resp.json()
    typer.echo(f"Key created: {data['name']}")
    typer.echo(f"\n  {data['key']}\n")
    typer.echo("Save this key — it will not be shown again.")


@keys_app.command("revoke")
def keys_revoke(
    key_id: Annotated[int, typer.Argument(help="Numeric key ID to revoke.")],
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt.")
    ] = False,
) -> None:
    """Revoke an API key by ID."""
    if not yes:
        confirm = typer.confirm("Revoke this key?")
        if not confirm:
            raise typer.Abort()
    resp = vault_request("DELETE", f"/api/keys/{key_id}")
    if resp.status_code == 404:
        typer.echo("error: key not found.", err=True)
        raise typer.Exit(code=1)
    typer.echo("Key revoked.")
