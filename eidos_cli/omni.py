"""Write a four-field row to a tenant's paired Omni Redis.

Paired Omni is ``{tenant}-omni`` (no space). Host-published ports live on
hostkey at 127.0.0.1. This module talks Redis RESP directly — it does not
call or wrap the standalone ``omni`` binary.
"""

from __future__ import annotations

import json
import socket
import uuid
from dataclasses import dataclass
from typing import Any

# Hostkey pair ports. kai has no Omni. Do not invent a sixth store.
TENANT_PORTS: dict[str, int] = {
    "reeves": 16772,
    "eidos": 16773,
    "aic": 16774,
    "arp": 16775,
    "gmw": 16776,
}

FORBIDDEN_TENANTS = frozenset({"kai"})
DEFAULT_TENANT = "reeves"
INDEX_KEY = "omni:index"
ROW_FIELDS = ("id", "kind", "data", "emb")
OMNI_HOST = "127.0.0.1"


@dataclass(frozen=True)
class OmniPair:
    tenant: str
    container: str
    host: str
    port: int


class OmniError(Exception):
    """Tenant targeting or Redis write failed."""


def pair_for(tenant: str) -> OmniPair:
    name = tenant.strip().lower()
    if not name:
        raise OmniError("tenant is required")
    if name in FORBIDDEN_TENANTS:
        raise OmniError(f"{name} has no paired Omni")
    port = TENANT_PORTS.get(name)
    if port is None:
        known = ", ".join(sorted(TENANT_PORTS))
        raise OmniError(f"unknown tenant {name!r}; known: {known}")
    return OmniPair(
        tenant=name,
        container=f"{name}-omni",
        host=OMNI_HOST,
        port=port,
    )


def build_row(
    *,
    tenant: str,
    id: str | None = None,
    kind: str = "probe",
    data: Any = None,
    emb: Any = None,
) -> dict[str, Any]:
    row_id = id or f"eidos-omni-{uuid.uuid4()}"
    if data is None:
        data = {"source": "eidos omni", "tenant": tenant}
    if emb is None:
        emb = []
    return {"id": row_id, "kind": kind, "data": data, "emb": emb}


def parse_data(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def write_row(pair: OmniPair, row: dict[str, Any], timeout: float = 5.0) -> None:
    missing = [field for field in ROW_FIELDS if field not in row]
    if missing:
        raise OmniError(f"row missing fields: {', '.join(missing)}")
    payload = json.dumps(row, separators=(",", ":"), default=str)
    conn = socket.create_connection((pair.host, pair.port), timeout=timeout)
    try:
        _command(conn, "SET", row["id"], payload)
        _command(conn, "SADD", INDEX_KEY, row["id"])
    finally:
        conn.close()


def _command(conn: socket.socket, *parts: str) -> None:
    conn.sendall(_encode(parts))
    reply = _read_reply(conn)
    if isinstance(reply, bytes) and reply.startswith(b"ERR"):
        raise OmniError(reply.decode("utf-8", errors="replace"))


def _encode(parts: tuple[str, ...]) -> bytes:
    chunks = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        data = part.encode()
        chunks.append(f"${len(data)}\r\n".encode())
        chunks.append(data)
        chunks.append(b"\r\n")
    return b"".join(chunks)


def _read_reply(conn: socket.socket) -> bytes | int | None:
    line = _readline(conn)
    if not line:
        raise OmniError("empty Redis reply")
    kind, rest = line[:1], line[1:]
    if kind == b"+":
        return rest
    if kind == b":":
        return int(rest)
    if kind == b"$":
        n = int(rest)
        if n < 0:
            return None
        data = _readexact(conn, n + 2)
        return data[:-2]
    if kind == b"-":
        raise OmniError(rest.decode("utf-8", errors="replace"))
    if kind == b"*":
        n = int(rest)
        if n < 0:
            return None
        for _ in range(n):
            _read_reply(conn)
        return n
    raise OmniError(f"unexpected Redis reply: {line!r}")


def _readline(conn: socket.socket) -> bytes:
    buf = bytearray()
    while not buf.endswith(b"\r\n"):
        chunk = conn.recv(1)
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf[:-2] if buf.endswith(b"\r\n") else buf)


def _readexact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise OmniError("truncated Redis reply")
        buf.extend(chunk)
    return bytes(buf)
