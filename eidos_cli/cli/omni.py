"""``eidos omni [write]`` — land a four-field row on the tenant's paired Omni."""

from __future__ import annotations

import json as _json
from typing import Annotated, Optional

import typer

from ..omni import OmniError, build_row, pair_for, parse_data, write_row


def register(app: typer.Typer) -> None:
    @app.command("omni")
    def cmd_omni(
        action: Annotated[
            Optional[str],
            typer.Argument(help="Optional 'write'. Default is write."),
        ] = None,
        tenant: Annotated[
            str,
            typer.Option(
                "--tenant",
                help="Tenant pair (reeves, eidos, aic, arp, gmw). Default: reeves.",
            ),
        ] = "reeves",
        id: Annotated[
            Optional[str],
            typer.Option("--id", help="Row id. Generated if omitted."),
        ] = None,
        kind: Annotated[
            str,
            typer.Option("--kind", help="Row kind. Default: probe."),
        ] = "probe",
        data: Annotated[
            Optional[str],
            typer.Option("--data", help="JSON or text for the data field."),
        ] = None,
        json_: Annotated[
            bool,
            typer.Option("--json", "-J", help="JSON output."),
        ] = False,
    ) -> None:
        """Write a four-field Redis JSON row (id, kind, data, emb) to that tenant's Omni.

        Then SADD omni:index <id>. Targets {tenant}-omni on 127.0.0.1:PORT.
        Does not call the standalone omni binary.
        """
        if action not in (None, "write"):
            typer.echo(
                f"error: unknown omni action {action!r} (try: eidos omni write)",
                err=True,
            )
            raise typer.Exit(code=2)
        try:
            pair = pair_for(tenant)
            row = build_row(
                tenant=pair.tenant,
                id=id,
                kind=kind,
                data=parse_data(data),
            )
            write_row(pair, row)
        except OmniError as exc:
            typer.echo(f"error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        except OSError as exc:
            typer.echo(
                f"error: cannot reach {pair.container} at "
                f"{pair.host}:{pair.port} ({exc})",
                err=True,
            )
            raise typer.Exit(code=1) from exc

        result = {
            "ok": True,
            "tenant": pair.tenant,
            "container": pair.container,
            "host": pair.host,
            "port": pair.port,
            "id": row["id"],
            "index": "omni:index",
            "row": row,
        }
        if json_:
            typer.echo(_json.dumps(result, default=str))
            return
        typer.echo(
            f"wrote {row['id']} to {pair.container} "
            f"({pair.host}:{pair.port}) + SADD omni:index"
        )
