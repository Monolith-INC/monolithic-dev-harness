from collections.abc import Callable, Mapping
from typing import Any

from .contracts import OUTPUT_PROPERTY, check_value
from .manifests import CapabilityManifest

SemanticEvaluator = Callable[[dict[str, Any], Mapping[str, Any]], list[str]]


def skill_validation_critiques(output: dict[str, Any]) -> list[str]:
    """Backward-compatible alias for the legacy semantic output convention."""
    return legacy_semantic_evaluator(output, {})


def legacy_semantic_evaluator(
    output: dict[str, Any], _manifest: Mapping[str, Any]
) -> list[str]:
    """Interpret the version 0.5.x ``mode``/``critiques`` convention.

    This adapter preserves existing handlers. It is deliberately named as
    compatibility behavior: accepting a producer's self-report is not an
    independent semantic verification strategy.
    """
    mode = output.get("mode", "")
    if mode == "completed":
        return []

    raw = output.get("critiques")
    parts: list[str] = []
    if isinstance(raw, str) and raw.strip():
        parts = [segment.strip() for segment in raw.split(";") if segment.strip()]
    elif isinstance(raw, list):
        parts = [str(item) for item in raw if item]

    if mode == "blocked_requires_review" and not parts:
        return ["skill blocked — requires review"]
    return parts


def collect_critiques(
    output: Any,
    manifest: CapabilityManifest,
    *,
    semantic_evaluator: SemanticEvaluator = legacy_semantic_evaluator,
) -> list[str]:
    """Collect structural critiques, then invoke the configured semantic contract."""
    schema_critiques = evaluate_output(output, manifest)
    if schema_critiques:
        return schema_critiques
    if isinstance(output, dict):
        try:
            critiques = semantic_evaluator(output, manifest.wire)
        except Exception as exc:
            return [f"Semantic evaluator raised {type(exc).__name__}: {exc}"]
        if not isinstance(critiques, list):
            return [
                "Semantic evaluator returned "
                f"{type(critiques).__name__}; expected list[str]."
            ]
        return [str(item) for item in critiques if item]
    return []


def evaluate_output(output: Any, manifest: CapabilityManifest) -> list[str]:
    """Check task output against the capability's parsed output contract."""
    return list(
        check_value(
            output,
            manifest.outputs,
            OUTPUT_PROPERTY,
            not_object_message=(
                "Expected output to be a dictionary/object, but got "
                f"{type(output).__name__}."
            ),
        )
    )
