"""Auth verbs: ``eidos auth login | logout | status``."""

from __future__ import annotations

import time
from typing import Annotated, Optional

import httpx
import typer

from ..config import VAULT_URL, clear_token, load_token, save_token

app = typer.Typer(no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)


@app.command("login")
def cmd_login(
    api_key: Annotated[
        Optional[str],
        typer.Argument(
            envvar="EIDOS_API_KEY",
            help="Eidos API key starting with evk_. Pass as arg or set EIDOS_API_KEY.",
        ),
    ] = None,
) -> None:
    """Authenticate with an API key and cache a session token."""
    if not api_key:
        typer.echo("error: missing api_key (pass as argument or set EIDOS_API_KEY)", err=True)
        raise typer.Exit(code=2)
    if not api_key.startswith("evk_"):
        typer.echo("error: API key must start with evk_", err=True)
        raise typer.Exit(code=1)

    typer.echo("Exchanging API key for token...")
    try:
        resp = httpx.post(
            f"{VAULT_URL}/api/auth/token",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
    except httpx.ConnectError:
        typer.echo(f"error: cannot reach {VAULT_URL}", err=True)
        raise typer.Exit(code=1)

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        typer.echo(f"error: {detail}", err=True)
        raise typer.Exit(code=1)

    result = resp.json()
    save_token(result["token"], result["expires_in"], api_key)
    typer.echo(f"Logged in. Token expires in {result['expires_in']}s.")


@app.command("logout")
def cmd_logout() -> None:
    """Clear cached credentials."""
    clear_token()
    typer.echo("Logged out.")


@app.command("status")
def cmd_status() -> None:
    """Show current auth status."""
    data = load_token()
    if not data:
        typer.echo("Not logged in.")
        return

    remaining = int(data["expires_at"] - time.time())
    if remaining > 0:
        typer.echo(
            f"Logged in. Token valid for {remaining}s. Key: {data['api_key'][:12]}..."
        )
    else:
        typer.echo(
            f"Token expired. Key: {data['api_key'][:12]}... (will refresh on next request)"
        )
