"""Top-level health command: ``eidos health``."""

from __future__ import annotations

import json

import httpx
import typer

from ..config import VAULT_URL


def register(app: typer.Typer) -> None:
    @app.command("health")
    def cmd_health() -> None:
        """Check platform health."""
        services = {"vault": VAULT_URL}
        for name, url in services.items():
            try:
                resp = httpx.get(f"{url}/health", timeout=5)
                data = resp.json()
                typer.echo(
                    f"{name}: {data.get('status', 'unknown')} — {json.dumps(data)}"
                )
            except Exception as e:
                typer.echo(f"{name}: down ({e})")
