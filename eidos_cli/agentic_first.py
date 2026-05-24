"""Agentic-first doctrine and checks shared across Eidos CLI gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any


TITLE = "AGENTIC-FIRST SOFTWARE-SKEPTICAL DOCTRINE"
CORE_RULE = "Eidos prefers agentic improvement over software production."
WARNING = "Do not write code merely because code is possible."
PRE_CODE_QUESTION = (
    "Before coding, justify why instruction, routing, proof, Converge, Felix, "
    "StepProof, or praxis is insufficient."
)
JUSTIFICATION_CATEGORIES = [
    "evidence gate",
    "adapter",
    "thin CLI/plugin shim",
    "schema/contract",
    "specialist runtime",
    "business/domain logic",
]
NON_CODE_PATHS = ["instruction", "routing", "proof", "Converge", "Felix", "StepProof", "praxis"]

CODE_MARKER_FILES = {
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}
CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".css",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".m",
    ".mm",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
}
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


def doctrine() -> dict[str, Any]:
    return {
        "title": TITLE,
        "preference": CORE_RULE,
        "warning": WARNING,
        "pre_code_question": PRE_CODE_QUESTION,
        "code_justification_categories": JUSTIFICATION_CATEGORIES,
        "non_code_paths_preferred": NON_CODE_PATHS,
    }


def doctrine_lines() -> list[str]:
    return [
        TITLE,
        CORE_RULE,
        WARNING,
        PRE_CODE_QUESTION,
        "Software is justified only when it strengthens judgment, evidence, routing, "
        "memory, constraints, measurement, repair, learning, or closeout.",
    ]


def plan_preflight(task_id: str) -> str:
    categories = ", ".join(JUSTIFICATION_CATEGORIES)
    paths = ", ".join(NON_CODE_PATHS)
    return (
        f"# Plan - {task_id}\n\n"
        "## Agentic-First Preflight\n\n"
        "- Have:\n"
        "- Want:\n"
        "- Do not want:\n"
        "- Proof target:\n"
        "- Specialist owner:\n"
        "- Why code is necessary:\n"
        f"- Non-code paths considered ({paths}):\n"
        f"- Code justification category ({categories}):\n\n"
        "<the substrate writes the DECOMPOSE/SPECIALIZE output here>\n"
    )


def is_code_path(rel: str) -> bool:
    path = Path(rel)
    if any(part in IGNORED_PARTS for part in path.parts):
        return False
    if path.name in CODE_MARKER_FILES:
        return True
    return path.suffix in CODE_EXTENSIONS


def is_agentic_protocol_path(rel: str) -> bool:
    path = Path(rel)
    text = path.as_posix()
    return (
        text.startswith(".eidos/")
        or text.startswith(".stepproof/")
        or text.startswith("docs/")
        or text == "CODEX-PLUGIN.md"
        or text == "AGENTS.md"
        or (text.startswith("skills/") and text.endswith("/SKILL.md"))
        or (text.startswith("eidos_cli/guides/") and text.endswith(".md"))
    )


def repo_has_code(repo: Path) -> bool:
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo).as_posix()
        if is_code_path(rel):
            return True
    return False


def agentic_manifest_proof(manifest: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    raw = manifest.get("agentic_first")
    if not isinstance(raw, dict):
        return False, "No [agentic_first] table found in ship manifest.", {}

    code_justification = str(raw.get("code_justification") or "").strip()
    agentic_capability = str(raw.get("agentic_capability") or "").strip()
    non_code_paths = raw.get("non_code_paths_considered")
    if code_justification not in JUSTIFICATION_CATEGORIES:
        return (
            False,
            "agentic_first.code_justification must be one of the allowed categories.",
            {"code_justification": code_justification},
        )
    if not agentic_capability:
        return False, "agentic_first.agentic_capability is required.", {}
    if not isinstance(non_code_paths, list) or not [p for p in non_code_paths if str(p).strip()]:
        return False, "agentic_first.non_code_paths_considered must be a non-empty list.", {}
    return (
        True,
        "Agentic-first manifest proof is present.",
        {
            "code_justification": code_justification,
            "agentic_capability": agentic_capability,
            "non_code_paths_considered": [str(p) for p in non_code_paths],
        },
    )


def ship_gate_evidence(repo: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if not repo_has_code(repo):
        return {
            "status": "skip",
            "detail": "No code-bearing project files detected.",
            "data": {"doctrine": doctrine(), "code_bearing": False},
        }

    proof_file = repo / ".eidos" / "agentic-first.md"
    if proof_file.is_file():
        return {
            "status": "pass",
            "detail": "Agentic-first proof file exists.",
            "data": {
                "doctrine": doctrine(),
                "code_bearing": True,
                "proof_file": str(proof_file),
            },
        }

    ok, detail, data = agentic_manifest_proof(manifest)
    if ok:
        return {
            "status": "pass",
            "detail": detail,
            "data": {"doctrine": doctrine(), "code_bearing": True, "manifest": data},
        }
    return {
        "status": "fail",
        "detail": f"{PRE_CODE_QUESTION} {detail}",
        "data": {"doctrine": doctrine(), "code_bearing": True, "manifest": data},
    }


def parse_porcelain_path(line: str) -> str:
    rel = line[3:] if len(line) > 3 else line
    if " -> " in rel:
        rel = rel.split(" -> ", 1)[1]
    return rel.strip()

