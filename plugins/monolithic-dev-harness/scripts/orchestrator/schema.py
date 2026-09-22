from __future__ import annotations

from typing import Any

from .contracts import ARGUMENT, check_value
from .manifests import CapabilityManifest


def validate_inputs(
    arguments: dict[str, Any], manifest: CapabilityManifest
) -> list[str]:
    """Check tool arguments against the capability's parsed input contract."""
    return list(
        check_value(
            arguments,
            manifest.inputs,
            ARGUMENT,
            not_object_message=f"Expected object arguments for skill '{manifest.name}'",
        )
    )
