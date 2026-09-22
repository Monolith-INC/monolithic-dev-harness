"""Idempotent artifact publication with bounded retry."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .contracts import ArtifactRef, IntegrationError


def _find_existing(
    artifacts: list[ArtifactRef], *, title: str, revision: str
) -> ArtifactRef | None:
    return next(
        (
            item
            for item in artifacts
            if item.revision == revision and item.title == title
        ),
        None,
    )


def publish_artifact_idempotent(
    *,
    list_fn: Callable[[], list[ArtifactRef]],
    create_fn: Callable[[], ArtifactRef],
    title: str,
    revision: str,
    max_attempts: int = 3,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Reuse an existing title+revision artifact or create one with retries.

    Re-lists before every create attempt so a timed-out create that actually
    succeeded does not duplicate the artifact on retry.
    """
    existing = _find_existing(list_fn(), title=title, revision=revision)
    if existing is not None:
        return {"artifact": existing, "outcome": "reused", "attempts": 0}

    attempts = 0
    last_error: IntegrationError | None = None
    while attempts < max_attempts:
        attempts += 1
        try:
            created = create_fn()
            return {"artifact": created, "outcome": "created", "attempts": attempts}
        except IntegrationError as exc:
            last_error = exc
            if not exc.retryable or attempts >= max_attempts:
                raise
            recovered = _find_existing(list_fn(), title=title, revision=revision)
            if recovered is not None:
                return {
                    "artifact": recovered,
                    "outcome": "reused",
                    "attempts": attempts,
                }
            sleep_fn(0.05 * attempts)
    assert last_error is not None
    raise last_error
