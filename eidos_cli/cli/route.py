"""``eidos route`` — plan a specialist stack from capability metadata."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Annotated, Any

import typer


CAPABILITY_REGISTRY_URL = "https://eidosagi.com/.well-known/eidos/capability-registry.json"
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]+")

DOMAIN_BOOSTS: list[tuple[set[str], dict[str, int]]] = [
    (
        {
            "apple",
            "browser",
            "login",
            "mfa",
            "passkey",
            "profile",
            "provisioning",
            "account",
            "surfari",
        },
        {"surfari": 60, "stepproof": 35, "knox": 20, "converge": 12},
    ),
    (
        {"high-stakes", "audit", "sequential", "ceremony", "gated", "compliance"},
        {"stepproof": 45, "converge": 18},
    ),
    (
        {"plugin", "catalog", "marketplace", "capability", "registry", "install"},
        {"eidos-plugin-store": 45, "felix": 22, "forge-forge": 18},
    ),
    (
        {"ship", "shipping", "release", "publish", "deploy", "ci"},
        {"eidos-plugin-store": 24, "felix": 18, "converge": 18, "stepproof": 10},
    ),
    (
        {"delegate", "worker", "worktree", "parallel", "implementation", "coding"},
        {"foreman": 45, "emux": 20, "converge": 14},
    ),
    (
        {"tmux", "terminal", "interactive", "interrupt", "capture", "headed"},
        {"emux": 40, "foreman": 22},
    ),
    (
        {"model", "debate", "image", "pairing", "judgment", "outside"},
        {"rhea": 42},
    ),
    (
        {"forge", "workspace", "owner", "domain"},
        {"forge-forge": 35},
    ),
    (
        {"secret", "credential", "vault", "access", "password", "key"},
        {"knox": 50, "stepproof": 12},
    ),
    (
        {"docs", "documentation", "readme", "cleanup", "copy"},
        {"eidos": 12},
    ),
]

NEXT_COMMANDS = {
    "eidos": "eidos do <task-id>",
    "eidos-plugin-store": "curl -fsSL https://eidosagi.com/.well-known/eidos/capability-registry.json",
    "surfari": "surfari doctor",
    "stepproof": "stepproof audit verify",
    "converge": "eidos plugin show converge",
    "foreman": "foreman route <task>",
    "emux": "emux list",
    "knox": "eidos vault list",
    "felix": "felix --help",
    "rhea": "rhea --help",
    "forge-forge": "forge-forge route <task>",
}


def register(app: typer.Typer) -> None:
    @app.command("route")
    def cmd_route(
        text_or_task_id: Annotated[
            str,
            typer.Argument(help="Task text, route question, or local docket task id."),
        ],
        registry: Annotated[
            str | None,
            typer.Option(
                "--registry",
                help="Capability registry JSON path or URL. Defaults to local generated registries, then public URL.",
            ),
        ] = None,
        limit: Annotated[
            int,
            typer.Option("--limit", help="Maximum non-Eidos specialists to include."),
        ] = 5,
        json_: Annotated[bool, typer.Option("--json", "-J", help="JSON output.")] = False,
    ) -> None:
        """Plan the specialist stack, proof, hard stops, and next command for a task."""
        from ._app import emit
        from ..scope.resolver import resolve_from_cwd

        eidos_home = resolve_from_cwd()
        registry_data, registry_source = load_registry(registry)
        task_text, task_source = resolve_task_text(text_or_task_id, eidos_home)
        result = plan_route(
            task_text,
            registry_data,
            registry_source=registry_source,
            task_source=task_source,
            eidos_home=eidos_home,
            limit=limit,
        )
        if json_:
            emit(result, json_mode=True)
            return
        emit(format_route(result), json_mode=False)


def load_registry(registry: str | None = None) -> tuple[dict[str, Any], str]:
    for candidate in registry_candidates(registry):
        if candidate.startswith("http://") or candidate.startswith("https://"):
            try:
                with urllib.request.urlopen(candidate, timeout=8) as response:
                    return json.loads(response.read().decode("utf-8")), candidate
            except Exception:
                continue
        path = Path(candidate).expanduser()
        if path.is_file():
            return json.loads(path.read_text()), str(path)
    raise RuntimeError("no capability registry found; pass --registry <path-or-url>")


def registry_candidates(registry: str | None) -> list[str]:
    if registry:
        return [registry]

    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    workspace = repo_root.parent
    return [
        str(workspace / "eidosagi.com" / "src" / "data" / "capability-registry.generated.json"),
        str(workspace / "eidos-plugin-store" / "examples" / "capability-registry.sample.json"),
        CAPABILITY_REGISTRY_URL,
    ]


def resolve_task_text(text_or_task_id: str, eidos_home: Path | None) -> tuple[str, str]:
    if eidos_home is None:
        return text_or_task_id, "argument"

    tasks_dir = eidos_home / ".eidos" / "docket" / "tasks"
    if not tasks_dir.is_dir():
        return text_or_task_id, "argument"

    candidates = sorted(tasks_dir.glob(f"{text_or_task_id}*.md"))
    if not candidates:
        return text_or_task_id, "argument"

    task_path = candidates[0]
    return task_path.read_text(), str(task_path)


def plan_route(
    task_text: str,
    registry: dict[str, Any],
    *,
    registry_source: str,
    task_source: str,
    eidos_home: Path | None,
    limit: int,
) -> dict[str, Any]:
    plugins = registry.get("plugins") or []
    by_slug = {plugin["slug"]: plugin for plugin in plugins if isinstance(plugin, dict) and plugin.get("slug")}
    scores = score_plugins(task_text, plugins)
    task_tokens = tokenize(task_text)
    priorities = route_priorities(task_tokens)

    selected_slugs = ["eidos"]
    for slug, score in sorted(
        scores.items(),
        key=lambda item: (priorities.get(item[0], 100), -item[1], item[0]),
    ):
        if slug == "eidos" or score <= 0:
            continue
        if slug in by_slug:
            selected_slugs.append(slug)
        if len(selected_slugs) >= max(1, limit) + 1:
            break

    selected_plugins = [by_slug[slug] for slug in selected_slugs if slug in by_slug]
    if len(selected_plugins) == 1 and selected_plugins[0]["slug"] == "eidos":
        selected_plugins = [by_slug["eidos"]]

    proof_requirements = unique(
        item
        for plugin in selected_plugins
        for item in collect_proof_requirements(plugin)
    )
    hard_stops = unique(
        stop
        for plugin in selected_plugins
        for stop in plugin.get("hard_stops", [])
    )

    next_command = recommended_next_command(selected_plugins, task_text)
    return {
        "ok": True,
        "task": task_text.strip(),
        "task_source": task_source,
        "scope": {
            "resolved": eidos_home is not None,
            "home": str(eidos_home) if eidos_home else None,
        },
        "registry_source": registry_source,
        "specialist_stack": [plugin["slug"] for plugin in selected_plugins],
        "owners": [
            {
                "slug": plugin["slug"],
                "name": plugin.get("name"),
                "owns": plugin.get("owns", {}),
                "score": scores.get(plugin["slug"], 0),
            }
            for plugin in selected_plugins
        ],
        "proof_requirements": proof_requirements,
        "hard_stops": hard_stops,
        "recommended_next_command": next_command,
    }


def score_plugins(task_text: str, plugins: list[dict[str, Any]]) -> dict[str, int]:
    task_tokens = tokenize(task_text)
    scores: dict[str, int] = {}
    for plugin in plugins:
        slug = plugin.get("slug")
        if not slug:
            continue
        haystack = searchable_text(plugin)
        overlap = task_tokens & tokenize(haystack)
        scores[slug] = len(overlap)
        if slug in task_tokens or tokenize(plugin.get("name", "")) & task_tokens:
            scores[slug] += 25

    for trigger_tokens, boosts in DOMAIN_BOOSTS:
        if task_tokens & trigger_tokens:
            for slug, boost in boosts.items():
                scores[slug] = scores.get(slug, 0) + boost

    if scores.get("surfari", 0) > 0:
        scores["eidos"] = max(scores.get("eidos", 0), 10)
    return scores


def route_priorities(task_tokens: set[str]) -> dict[str, int]:
    protected_browser_terms = {
        "apple",
        "browser",
        "login",
        "mfa",
        "passkey",
        "passkeys",
        "profile",
        "provisioning",
        "account",
    }
    if task_tokens & protected_browser_terms:
        return {
            "surfari": 0,
            "stepproof": 1,
            "converge": 2,
            "knox": 3,
            "foreman": 4,
            "emux": 5,
        }
    return {}


def searchable_text(plugin: dict[str, Any]) -> str:
    parts = [
        plugin.get("slug", ""),
        plugin.get("name", ""),
        plugin.get("summary", ""),
        plugin.get("owns", {}).get("domain", ""),
        plugin.get("owns", {}).get("boundary", ""),
        " ".join(plugin.get("proof_types", [])),
        " ".join(plugin.get("hard_stops", [])),
        " ".join(plugin.get("dependencies", [])),
        " ".join(plugin.get("works_with", [])),
    ]
    for route in plugin.get("eidos_routes", []):
        parts.append(route.get("when", ""))
        parts.append(" ".join(route.get("proof_required", [])))
    for command in plugin.get("commands", []):
        parts.extend([command.get("name", ""), command.get("command", ""), command.get("purpose", "")])
    return " ".join(parts)


def collect_proof_requirements(plugin: dict[str, Any]) -> list[str]:
    proof = list(plugin.get("proof_types", []))
    for route in plugin.get("eidos_routes", []):
        proof.extend(route.get("proof_required", []))
    return proof


def recommended_next_command(selected_plugins: list[dict[str, Any]], task_text: str) -> str:
    for plugin in selected_plugins:
        slug = plugin.get("slug")
        if slug == "eidos":
            continue
        command = NEXT_COMMANDS.get(slug)
        if command:
            if "<task>" in command:
                return command.replace("<task>", json.dumps(task_text.strip()))
            return command
    return NEXT_COMMANDS["eidos"]


def tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def unique(items) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def format_route(result: dict[str, Any]) -> str:
    lines = [
        "Route verdict:",
        " -> ".join(result["specialist_stack"]),
        "",
        f"Scope: {'resolved at ' + result['scope']['home'] if result['scope']['resolved'] else 'no local eidos scope'}",
        f"Registry: {result['registry_source']}",
        "",
        "Owners:",
    ]
    for owner in result["owners"]:
        owns = owner.get("owns") or {}
        lines.append(f"- {owner['slug']} ({owner['score']}): {owns.get('domain', '')}")
    lines.extend(["", "Proof required:"])
    for proof in result["proof_requirements"]:
        lines.append(f"- {proof}")
    lines.extend(["", "Hard stops:"])
    for stop in result["hard_stops"]:
        lines.append(f"- {stop}")
    lines.extend(["", f"Next: {result['recommended_next_command']}"])
    return "\n".join(lines)
