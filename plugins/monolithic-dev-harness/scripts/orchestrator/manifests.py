from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .contracts import (
    Parsed,
    Rejected,
    ValueContract,
    parse_value_contract,
)
from .exhaustive import assert_never
from .failures import SkillAssetMissing
from .state import FrozenDict, deep_freeze

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ManifestDiagnostic:
    """One capability manifest rejected during discovery."""

    path: Path
    code: str
    message: str


@dataclass(frozen=True)
class CapabilityManifest:
    """A discovered capability, parsed once into its declared contract.

    ``wire`` is the frozen image of the ``manifest.json`` body: JSON-identical
    to the file (arrays become tuples, which serialize the same). It exists
    solely so host dialect projections -- MCP ``inputSchema`` and Anthropic
    tool schemas -- can emit the JSON Schema those hosts expect. Nothing
    may re-derive a rule from it; the rules live in ``inputs`` and ``outputs``.
    """

    name: str
    description: str
    inputs: ValueContract
    outputs: ValueContract
    wire: Mapping[str, Any] = field(default_factory=FrozenDict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "wire", deep_freeze(self.wire))


@dataclass(frozen=True)
class ManifestParsed:
    manifest: CapabilityManifest


@dataclass(frozen=True)
class ManifestRejected:
    diagnostics: tuple[ManifestDiagnostic, ...]


ManifestParse = ManifestParsed | ManifestRejected


@dataclass(frozen=True)
class ManifestDiscovery:
    """Valid manifests and deterministic diagnostics from one filesystem scan."""

    manifests: tuple[CapabilityManifest, ...] = ()
    diagnostics: tuple[ManifestDiagnostic, ...] = ()


def parse_manifest(data: Any, path: str | Path) -> ManifestParse:
    """Parse one raw manifest body into a capability or into diagnostics."""
    manifest_path = Path(path)

    def reject(code: str, message: str) -> ManifestDiagnostic:
        return ManifestDiagnostic(manifest_path, code, message)

    if not isinstance(data, dict):
        return ManifestRejected(
            (reject("root_not_object", "Manifest root must be an object."),)
        )

    diagnostics: tuple[ManifestDiagnostic, ...] = ()

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        diagnostics += (
            reject("invalid_name", "Manifest name must be a non-empty string."),
        )

    description = data.get("description")
    if description is not None and not isinstance(description, str):
        diagnostics += (
            reject("invalid_description", "Manifest description must be a string."),
        )

    contracts: dict[str, ValueContract] = {}
    for field_name in ("input_schema", "output_signature"):
        match parse_value_contract(data.get(field_name), field_name):
            case Parsed(contract):
                contracts[field_name] = contract
            case Rejected(issues):
                diagnostics += tuple(
                    reject(issue.code, issue.message) for issue in issues
                )
            case _ as unmatched:
                assert_never(unmatched)

    if diagnostics:
        return ManifestRejected(diagnostics)

    return ManifestParsed(
        CapabilityManifest(
            name=str(name),
            description=description or "",
            inputs=contracts["input_schema"],
            outputs=contracts["output_signature"],
            wire=data,
        )
    )


def validate_manifest(data: Any, path: str | Path) -> tuple[ManifestDiagnostic, ...]:
    """Diagnostics-only projection of :func:`parse_manifest`."""
    match parse_manifest(data, path):
        case ManifestParsed():
            return ()
        case ManifestRejected(diagnostics):
            return diagnostics
        case _ as unmatched:
            assert_never(unmatched)


def discover_manifests(skills_dir: str | Path) -> ManifestDiscovery:
    """Discover valid manifests while isolating and describing invalid ones."""
    base_path = Path(skills_dir)
    if not base_path.is_dir():
        return ManifestDiscovery()

    candidates: list[tuple[Path, CapabilityManifest]] = []
    diagnostics: list[ManifestDiagnostic] = []

    for skill_path in sorted(base_path.iterdir()):
        if not skill_path.is_dir():
            continue
        manifest_file = skill_path / "manifest.json"
        if not manifest_file.is_file():
            continue
        try:
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            diagnostics.append(
                ManifestDiagnostic(
                    manifest_file,
                    "invalid_json",
                    f"Manifest is not valid JSON: {exc.msg}.",
                )
            )
            continue
        except OSError as exc:
            diagnostics.append(
                ManifestDiagnostic(
                    manifest_file,
                    "unreadable",
                    f"Manifest could not be read: {exc}.",
                )
            )
            continue

        try:
            parse = parse_manifest(data, manifest_file)
        except Exception as exc:  # pragma: no cover - parser defect containment
            diagnostics.append(
                ManifestDiagnostic(
                    manifest_file,
                    "parser_error",
                    f"Manifest parser raised {type(exc).__name__}: {exc}.",
                )
            )
            continue

        match parse:
            case ManifestParsed(manifest):
                candidates.append((manifest_file, manifest))
            case ManifestRejected(issues):
                diagnostics.extend(issues)
            case _ as unmatched:
                assert_never(unmatched)

    name_counts = Counter(manifest.name for _, manifest in candidates)
    manifests: list[CapabilityManifest] = []
    for manifest_path, manifest in candidates:
        if name_counts[manifest.name] > 1:
            diagnostics.append(
                ManifestDiagnostic(
                    manifest_path,
                    "duplicate_name",
                    f"Capability name '{manifest.name}' is declared more than once.",
                )
            )
            continue
        manifests.append(manifest)

    return ManifestDiscovery(tuple(manifests), tuple(diagnostics))


def discovered_capabilities(skills_dir: str | Path) -> tuple[CapabilityManifest, ...]:
    """The typed discovery API: valid capabilities, with diagnostics logged."""
    discovery = discover_manifests(skills_dir)
    for diagnostic in discovery.diagnostics:
        logger.warning(
            "ignored capability manifest %s [%s]: %s",
            diagnostic.path,
            diagnostic.code,
            diagnostic.message,
        )
    return discovery.manifests


def capabilities_by_name(skills_dir: str | Path) -> dict[str, CapabilityManifest]:
    """The typed discovery API, keyed by capability name."""
    return {manifest.name: manifest for manifest in discovered_capabilities(skills_dir)}


def read_manifests(skills_dir: str | Path) -> list[dict[str, Any]]:
    """Compatibility view of the valid manifests discovered under ``skills_dir``.

    Returns manifest bodies, the shape this wrapper has always returned and the
    one the accepted specification fixes. Callers wanting the parsed contracts
    use :func:`discovered_capabilities`.
    """
    return [dict(manifest.wire) for manifest in discovered_capabilities(skills_dir)]


def manifest_by_name(skills_dir: str | Path) -> dict[str, dict[str, Any]]:
    """Compatibility view keyed by capability name."""
    return {
        manifest.name: dict(manifest.wire)
        for manifest in discovered_capabilities(skills_dir)
    }


def load_skill_instructions(skills_dir: str | Path, skill_name: str) -> str:
    skill_md = Path(skills_dir) / skill_name / "SKILL.md"
    if not skill_md.is_file():
        raise SkillAssetMissing(f"Missing SKILL.md for skill '{skill_name}'")
    return skill_md.read_text(encoding="utf-8")
