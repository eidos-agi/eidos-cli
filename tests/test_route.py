from __future__ import annotations

import json
from pathlib import Path

from eidos_cli.cli.route import load_registry, plan_route


def _registry_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root.parent / "eidos-plugin-store" / "examples" / "capability-registry.sample.json",
        Path("/Volumes/MacMiniStorage/Eidos/repos-eidos-agi/eidos-plugin-store/examples/capability-registry.sample.json"),
        Path("/Users/dshanklin/repos-eidos-agi/eidos-plugin-store/examples/capability-registry.sample.json"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise AssertionError("capability registry sample not found for route tests")


def _registry() -> dict:
    registry_path = _registry_path()
    data, _ = load_registry(str(registry_path))
    return data


def _route(text: str) -> dict:
    return plan_route(
        text,
        _registry(),
        registry_source=str(_registry_path()),
        task_source="test",
        eidos_home=None,
        limit=5,
    )


def test_route_high_stakes_browser_workflow_stops_at_apple_gates() -> None:
    route = _route(
        "EID-448 Surfari Knox Apple Developer browser workflow with login, MFA, "
        "passkeys, provisioning profile download, and profile install risk"
    )

    assert route["specialist_stack"][:4] == ["eidos", "surfari", "stepproof", "converge"]
    assert "knox" in route["specialist_stack"]
    assert "converge" in route["specialist_stack"]
    hard_stops = " ".join(route["hard_stops"]).lower()
    for gate in ("login", "mfa", "passkeys", "payments", "profile install"):
        assert gate in hard_stops
    assert route["recommended_next_command"] == "surfari doctor"


def test_route_plugin_shipment_uses_catalog_and_builder_stack() -> None:
    route = _route("Ship a plugin catalog marketplace capability registry update with CI proof")

    assert route["specialist_stack"][0] == "eidos"
    assert "eidos-plugin-store" in route["specialist_stack"]
    assert "felix" in route["specialist_stack"]
    assert route["recommended_next_command"].startswith("curl -fsSL")


def test_route_low_risk_docs_cleanup_stays_with_eidos() -> None:
    route = _route("Low-risk README documentation cleanup")

    assert route["specialist_stack"] == ["eidos"]
    assert route["recommended_next_command"] == "eidos do <task-id>"


def test_route_output_is_json_serializable() -> None:
    route = _route("Foreman Emux interactive worker implementation task")

    encoded = json.dumps(route)
    decoded = json.loads(encoded)
    assert "foreman" in decoded["specialist_stack"]
    assert "emux" in decoded["specialist_stack"]
