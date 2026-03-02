"""Configuration and token management for eidos CLI."""

import json
import time
from pathlib import Path

EIDOS_DIR = Path.home() / ".eidos"
TOKEN_FILE = EIDOS_DIR / "token.json"
CONFIG_FILE = EIDOS_DIR / "config.json"

VAULT_URL = "https://vault.eidosagi.com"


def ensure_dir():
    EIDOS_DIR.mkdir(exist_ok=True)


def save_token(token: str, expires_in: int, api_key: str):
    """Save JWT and API key to disk."""
    ensure_dir()
    TOKEN_FILE.write_text(json.dumps({
        "token": token,
        "api_key": api_key,
        "expires_at": time.time() + expires_in,
    }))
    TOKEN_FILE.chmod(0o600)


def load_token() -> dict | None:
    """Load cached token. Returns None if missing or expired."""
    if not TOKEN_FILE.exists():
        return None
    data = json.loads(TOKEN_FILE.read_text())
    if time.time() >= data.get("expires_at", 0):
        # Token expired — try to refresh using stored API key
        return _refresh(data) if data.get("api_key") else None
    return data


def _refresh(data: dict) -> dict | None:
    """Exchange stored API key for a new JWT."""
    import httpx
    try:
        resp = httpx.post(
            f"{VAULT_URL}/api/auth/token",
            headers={"Authorization": f"Bearer {data['api_key']}"},
            timeout=10,
        )
        if resp.status_code == 200:
            result = resp.json()
            save_token(result["token"], result["expires_in"], data["api_key"])
            return {
                "token": result["token"],
                "api_key": data["api_key"],
                "expires_at": time.time() + result["expires_in"],
            }
    except Exception:
        pass
    return None


def get_bearer_token() -> str | None:
    """Get a valid bearer token, refreshing if needed."""
    data = load_token()
    return data["token"] if data else None


def get_api_key() -> str | None:
    """Get the stored API key."""
    if not TOKEN_FILE.exists():
        return None
    data = json.loads(TOKEN_FILE.read_text())
    return data.get("api_key")


def clear_token():
    """Remove cached token."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
