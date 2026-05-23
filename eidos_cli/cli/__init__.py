"""eidos-cli command surface.

The unified agent-facing CLI for the Eidos scope architecture. Verbs are
organized into:

- **Scope** (``define / enter / status / activate / close / closeout / spawn / tick``) —
  the eidos lifecycle.
- **Forge namespaces** (``eidos telos / research / governor / docket / praxis``)
  — direct access to the five forge libraries.
- **Auth** (``eidos auth login / logout / status``) — platform credentials.
- **Vault** (``eidos vault get / set / list / rm / keys``) — secrets.
- **MCP** (``eidos mcp serve``) — boots the razor-thin MCP server.
- **Migrate** (``eidos migrate``) — consolidates legacy
  ``.telos / .research / .governor / .docket / .hone`` directories into
  the unified ``.eidos/`` layout.

See ``eidos-philosophy/THE-EIDOS.md`` for the architecture this surface
implements, and ``governor.md/.governor/adr/ADR-007`` for the commitment.
"""

from ._app import app, main

__all__ = ["app", "main"]
