"""eidos — CLI for the Eidos AGI platform."""

import json
import sys

import click
import httpx

from eidos_cli.config import VAULT_URL, save_token, load_token, clear_token
from eidos_cli.api import vault_request


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Eidos AGI platform CLI."""
    pass


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("api_key", envvar="EIDOS_API_KEY")
def login(api_key: str):
    """Authenticate with an API key (evk_...).

    Pass the key as an argument or set EIDOS_API_KEY env var.
    """
    if not api_key.startswith("evk_"):
        click.echo("Error: API key must start with evk_", err=True)
        raise SystemExit(1)

    click.echo("Exchanging API key for token...")
    try:
        resp = httpx.post(
            f"{VAULT_URL}/api/auth/token",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
    except httpx.ConnectError:
        click.echo(f"Error: cannot reach {VAULT_URL}", err=True)
        raise SystemExit(1)

    if resp.status_code != 200:
        click.echo(f"Error: {resp.json().get('detail', resp.text)}", err=True)
        raise SystemExit(1)

    result = resp.json()
    save_token(result["token"], result["expires_in"], api_key)
    click.echo(f"Logged in. Token expires in {result['expires_in']}s.")


@cli.command()
def logout():
    """Clear cached credentials."""
    clear_token()
    click.echo("Logged out.")


@cli.command()
def status():
    """Show current auth status."""
    data = load_token()
    if not data:
        click.echo("Not logged in.")
        return

    import time
    remaining = int(data["expires_at"] - time.time())
    if remaining > 0:
        click.echo(f"Logged in. Token valid for {remaining}s. Key: {data['api_key'][:12]}...")
    else:
        click.echo(f"Token expired. Key: {data['api_key'][:12]}... (will refresh on next request)")


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------

@cli.group()
def vault():
    """Manage secrets in eidos-vault."""
    pass


@vault.command("get")
@click.argument("path")
def vault_get(path: str):
    """Read a secret by path."""
    resp = vault_request("GET", f"/api/secrets/{path}")
    if resp.status_code == 404:
        click.echo(f"Not found: {path}", err=True)
        raise SystemExit(1)
    if resp.status_code == 403:
        click.echo(f"Forbidden: {resp.json().get('detail', '')}", err=True)
        raise SystemExit(1)
    data = resp.json()
    click.echo(data["value"])


@vault.command("set")
@click.argument("path")
@click.argument("value", required=False)
@click.option("--description", "-d", default="", help="Secret description")
@click.option(
    "--stdin",
    "from_stdin",
    is_flag=True,
    help="Read VALUE from stdin instead of argv (avoids exposing the secret in `ps`).",
)
def vault_set(path: str, value: str | None, description: str, from_stdin: bool):
    """Create or update a secret.

    Pass VALUE as the second positional argument, OR pass --stdin and pipe the
    value on stdin. --stdin is preferred for sensitive values: it keeps the
    secret out of argv (which is briefly visible via `ps aux`) and out of
    shell history.

    Examples:
        eidos vault set pypi/token sk-abc123                  # argv
        printf %s "$SECRET" | eidos vault set pypi/token --stdin
        # native macOS dialog:
        osascript -e 'text returned of (display dialog "Token:" default answer "" with hidden answer)' \\
            | eidos vault set pypi/token --stdin
    """
    if from_stdin:
        if value is not None:
            click.echo("--stdin and a positional VALUE are mutually exclusive.", err=True)
            raise SystemExit(2)
        value = sys.stdin.read()
        # Strip a single trailing newline only (preserve whitespace inside the value).
        if value.endswith("\n"):
            value = value[:-1]
        if not value:
            click.echo("--stdin received an empty value; refusing to write.", err=True)
            raise SystemExit(2)
    elif value is None:
        click.echo("Missing VALUE. Pass it as an argument or use --stdin.", err=True)
        raise SystemExit(2)

    resp = vault_request("POST", "/api/secrets", json={
        "path": path, "value": value, "description": description,
    })
    if resp.status_code == 403:
        click.echo(f"Forbidden: {resp.json().get('detail', '')}", err=True)
        raise SystemExit(1)
    data = resp.json()
    click.echo(f"{data['action']}: {data['path']}")


@vault.command("list")
def vault_list():
    """List all secrets (paths only, no values)."""
    resp = vault_request("GET", "/api/secrets")
    for s in resp.json():
        desc = f"  ({s['description']})" if s.get("description") else ""
        click.echo(f"{s['path']}{desc}")


@vault.command("rm")
@click.argument("path")
@click.confirmation_option(prompt="Delete this secret?")
def vault_rm(path: str):
    """Delete a secret."""
    resp = vault_request("DELETE", f"/api/secrets/{path}")
    if resp.status_code == 404:
        click.echo(f"Not found: {path}", err=True)
        raise SystemExit(1)
    click.echo(f"Deleted: {path}")


# ---------------------------------------------------------------------------
# Vault — Key Management
# ---------------------------------------------------------------------------

@vault.group("keys")
def vault_keys():
    """Manage API keys."""
    pass


@vault_keys.command("list")
def keys_list():
    """List API keys."""
    resp = vault_request("GET", "/api/keys")
    for k in resp.json():
        scopes = f"  scopes={','.join(k['scopes'])}" if k.get("scopes") else ""
        paths = f"  paths={','.join(k['paths'])}" if k.get("paths") else ""
        click.echo(f"{k['prefix']}...  {k['name']}  owner={k['owner']}{paths}{scopes}")


@vault_keys.command("create")
@click.option("--name", "-n", required=True, help="Key name")
@click.option("--paths", "-p", default=None, help="Comma-separated vault path globs")
@click.option("--scopes", "-s", default=None, help="Comma-separated scopes")
@click.option("--expires", default=None, help="Expiry (ISO format)")
def keys_create(name: str, paths: str | None, scopes: str | None, expires: str | None):
    """Create a new API key."""
    body = {"name": name}
    if paths:
        body["allowed_paths"] = [p.strip() for p in paths.split(",")]
    if scopes:
        body["scopes"] = [s.strip() for s in scopes.split(",")]
    if expires:
        body["expires_at"] = expires
    resp = vault_request("POST", "/api/keys", json=body)
    data = resp.json()
    click.echo(f"Key created: {data['name']}")
    click.echo(f"\n  {data['key']}\n")
    click.echo("Save this key — it will not be shown again.")


@vault_keys.command("revoke")
@click.argument("key_id", type=int)
@click.confirmation_option(prompt="Revoke this key?")
def keys_revoke(key_id: int):
    """Revoke an API key by ID."""
    resp = vault_request("DELETE", f"/api/keys/{key_id}")
    if resp.status_code == 404:
        click.echo("Key not found.", err=True)
        raise SystemExit(1)
    click.echo("Key revoked.")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@cli.command()
def health():
    """Check platform health."""
    services = {"vault": VAULT_URL}
    for name, url in services.items():
        try:
            resp = httpx.get(f"{url}/health", timeout=5)
            data = resp.json()
            click.echo(f"{name}: {data.get('status', 'unknown')} — {json.dumps(data)}")
        except Exception as e:
            click.echo(f"{name}: down ({e})")


if __name__ == "__main__":
    cli()
