"""HTTP client for Eidos services."""

import click
import httpx

from eidos_cli.config import get_bearer_token, get_api_key, VAULT_URL


def _auth_headers(use_jwt: bool = True) -> dict:
    """Get authorization headers. Uses JWT by default, falls back to API key."""
    if use_jwt:
        token = get_bearer_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
    # Fall back to API key for direct vault access
    api_key = get_api_key()
    if api_key:
        return {"Authorization": f"Bearer {api_key}"}
    click.echo("Not logged in. Run: eidos login", err=True)
    raise SystemExit(1)


def vault_request(method: str, path: str, **kwargs) -> httpx.Response:
    """Make an authenticated request to vault."""
    url = f"{VAULT_URL}{path}"
    headers = _auth_headers(use_jwt=False)  # Direct vault access uses API key
    resp = httpx.request(method, url, headers=headers, timeout=15, **kwargs)
    if resp.status_code == 401:
        click.echo("Authentication failed. Run: eidos login", err=True)
        raise SystemExit(1)
    return resp
