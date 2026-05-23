"""Verify step for the bundled ``learn`` plugin.

Checks the substrate-written draft under ``<work_dir>/draft/`` has all
three required artifacts and that the plugin.yaml has a usable shape
(slug, version, description, when_to_fire). Returns the shape contracted
by ``plugin_runtime.runner.run_verify``.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


REQUIRED_FILES = ("plugin.yaml", "playbook.md", "provenance.json")
REQUIRED_MANIFEST_FIELDS = ("slug", "version", "description", "when_to_fire", "owner_forge")
REQUIRED_PROVENANCE_FIELDS = (
    "source_turns",
    "source_eidos_id",
    "promoted_by",
    "promoted_at",
    "rationale",
)


def verify(work_dir: Path, draft_dir: Path) -> dict:
    reasons: list[str] = []
    detail: dict = {}

    if not draft_dir.is_dir():
        return {
            "passed": False,
            "reasons": [f"draft_dir missing: {draft_dir}"],
            "detail": {},
        }

    # File presence
    missing = [f for f in REQUIRED_FILES if not (draft_dir / f).is_file()]
    if missing:
        reasons.append(f"missing required files under draft/: {missing}")
    detail["missing_files"] = missing

    # plugin.yaml shape
    pyaml = draft_dir / "plugin.yaml"
    manifest: dict = {}
    if pyaml.is_file():
        try:
            manifest = yaml.safe_load(pyaml.read_text()) or {}
        except yaml.YAMLError as e:
            reasons.append(f"plugin.yaml is not valid YAML: {e}")
            manifest = {}
        missing_fields = [f for f in REQUIRED_MANIFEST_FIELDS if not manifest.get(f)]
        if missing_fields:
            reasons.append(f"plugin.yaml missing required fields: {missing_fields}")
        detail["manifest_missing"] = missing_fields
        slug = str(manifest.get("slug", "")).strip()
        if slug and not _is_kebab(slug):
            reasons.append(f"slug {slug!r} must be kebab-case")
        if str(manifest.get("owner_forge", "")) not in {
            "telos",
            "research",
            "governor",
            "docket",
            "praxis",
            "",
        }:
            reasons.append(
                f"owner_forge {manifest.get('owner_forge')!r} must be one of "
                "telos/research/governor/docket/praxis"
            )

    # provenance.json shape
    pjson = draft_dir / "provenance.json"
    if pjson.is_file():
        try:
            prov = json.loads(pjson.read_text())
        except json.JSONDecodeError as e:
            reasons.append(f"provenance.json is not valid JSON: {e}")
            prov = {}
        if isinstance(prov, dict):
            missing_p = [f for f in REQUIRED_PROVENANCE_FIELDS if not prov.get(f)]
            if missing_p:
                reasons.append(f"provenance.json missing required fields: {missing_p}")
            detail["provenance_missing"] = missing_p
            turns = prov.get("source_turns") or []
            if not isinstance(turns, list) or not turns:
                reasons.append("provenance.source_turns must be a non-empty list")
        else:
            reasons.append("provenance.json must be a JSON object")

    # playbook.md non-empty
    pbk = draft_dir / "playbook.md"
    if pbk.is_file() and pbk.stat().st_size < 200:
        reasons.append(
            f"playbook.md is suspiciously short ({pbk.stat().st_size} bytes); "
            "expand it so a future substrate can execute it cold"
        )

    return {"passed": not reasons, "reasons": reasons, "detail": detail}


def _is_kebab(s: str) -> bool:
    import re

    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s))
