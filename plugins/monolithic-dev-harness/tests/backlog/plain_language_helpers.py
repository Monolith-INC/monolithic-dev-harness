"""Shared helpers for plain-language skill structural tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLUGIN_SKILLS = ROOT / "skills"
PLAIN_LANGUAGE_SKILL = PLUGIN_SKILLS / "generate-plain-language-documentation"
GLOSSARY_PATH = (
    PLAIN_LANGUAGE_SKILL / "references" / "assets" / "tech-glossary-en-pt-br.json"
)
GLOSSARY_DOC_PATH = "./references/assets/tech-glossary-en-pt-br.json"

INTEGRATION_NOTES_REL = (
    "../generate-plain-language-documentation/references/integration-notes.md"
)

REQUIRED_PHASES = (
    "PHASE 0",
    "PHASE 1",
    "PHASE 2",
    "PHASE 3",
    "PHASE 4",
    "PHASE 5",
)

REQUIRED_REFERENCE_FILES = (
    "plain-language-principles.md",
    "glossary-usage.md",
    "output-formats.md",
    "integration-notes.md",
    "pipeline.md",
)


def read_skill_text(skill_name: str, *parts: str) -> str:
    return (PLUGIN_SKILLS / skill_name / Path(*parts)).read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_skill_manifest(data: dict[str, Any], *, expected_name: str) -> list[str]:
    """Return validation errors for a skill manifest.json payload."""
    errors: list[str] = []
    if data.get("name") != expected_name:
        errors.append(f"name must be {expected_name!r}")
    if not isinstance(data.get("description"), str) or not data["description"].strip():
        errors.append("description must be a non-empty string")

    schema = data.get("input_schema")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        errors.append("input_schema must be an object schema")
    else:
        required = schema.get("required")
        if not isinstance(required, list) or "source" not in required:
            errors.append("input_schema.required must include 'source'")

    output_sig = data.get("output_signature")
    if not isinstance(output_sig, dict):
        errors.append("output_signature must be an object")
    elif not isinstance(output_sig.get("required"), list) or not output_sig["required"]:
        errors.append("output_signature.required must be a non-empty list")

    return errors


def validate_glossary_structure(data: dict[str, Any]) -> list[str]:
    """Return validation errors for tech-glossary-en-pt-br.json structure."""
    errors: list[str] = []
    for key in ("terms", "aliases", "schema", "count"):
        if key not in data:
            errors.append(f"missing top-level field {key!r}")

    terms = data.get("terms")
    if not isinstance(terms, dict) or not terms:
        errors.append("terms must be a non-empty object")
    else:
        sample_key = next(iter(terms))
        sample = terms[sample_key]
        if not isinstance(sample, dict) or "pt" not in sample:
            errors.append("each terms entry must have a pt field")

    aliases = data.get("aliases")
    if not isinstance(aliases, dict):
        errors.append("aliases must be an object")

    count = data.get("count")
    if not isinstance(count, int) or count <= 0:
        errors.append("count must be a positive integer")
    elif isinstance(terms, dict) and count != len(terms):
        errors.append("count must match number of terms entries")

    return errors


def glossary_lookup_pt(data: dict[str, Any], term: str) -> str | None:
    """Resolve an English term to its pt-BR glossary value."""
    key = data.get("aliases", {}).get(term) or term.lower()
    entry = data.get("terms", {}).get(key)
    if not isinstance(entry, dict):
        return None
    pt = entry.get("pt")
    return pt if isinstance(pt, str) else None


def missing_substrings(content: str, required: tuple[str, ...]) -> list[str]:
    return [item for item in required if item not in content]
