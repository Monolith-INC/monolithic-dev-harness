"""Build a parsed capability the same way discovery does.

Tests must not hand-roll a manifest value: the parse is the contract, so a
fixture that bypassed it would be testing a shape nothing in production builds.
"""

from typing import Any

from scripts.orchestrator.manifests import (
    CapabilityManifest,
    ManifestParsed,
    ManifestRejected,
    parse_manifest,
)


def capability(data: dict[str, Any]) -> CapabilityManifest:
    match parse_manifest(data, "test/manifest.json"):
        case ManifestParsed(manifest):
            return manifest
        case ManifestRejected(diagnostics):
            raise AssertionError(f"fixture manifest is invalid: {diagnostics}")
        case unexpected:  # pragma: no cover - exhaustiveness guard
            raise AssertionError(f"non-exhaustive ManifestParse: {unexpected!r}")
