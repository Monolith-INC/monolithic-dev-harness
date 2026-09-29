"""Workflow artifacts stored as tracker comments (or local files): one text format, published once.

An artifact is text that starts with an envelope line naming its kind, title, and revision. The
envelope is how a re-run recognizes an artifact it already published, so a (title, revision) pair
is published once however often the workflow retries.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, err, oks

from .contracts import EMPTY, ArtifactDraft, ArtifactRef, TrackerOps
from .payloads import text

PREFIX = "harness-artifact:v1"
MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Published:
    artifact: ArtifactRef
    outcome: str
    attempts: int


def encode(draft: ArtifactDraft) -> str:
    header = json.dumps(
        {"kind": draft.kind, "title": draft.title, "revision": draft.revision},
        sort_keys=True,
    )
    return f"{PREFIX} {header}\n{draft.content}"


def decode(stored: str) -> Result[ArtifactDraft]:
    """The artifact a text carries, or `Err` when the text is an ordinary comment."""
    header_line, _, body = stored.removeprefix(PREFIX).lstrip().partition("\n")
    return bind(
        Ok(None)
        if stored.startswith(PREFIX)
        else err("not_an_artifact", "the text has no artifact envelope"),
        lambda _: bind(
            attempt(
                lambda: json.loads(header_line),
                "not_an_artifact",
                "the envelope header is not JSON",
                ValueError,
            ),
            lambda header: (
                Ok(
                    ArtifactDraft(
                        str(header.get("kind") or "artifact"),
                        str(header.get("title") or ""),
                        body,
                        str(header.get("revision") or ""),
                    )
                )
                if isinstance(header, dict)
                else err("not_an_artifact", "the envelope header is not an object")
            ),
        ),
    )


def reference(
    identifier: str, url: str, stored: str, provider_data: Mapping[str, Any] = EMPTY
) -> Result[ArtifactRef]:
    """An artifact reference from a stored text, when the text is an artifact."""
    return bind(
        decode(stored),
        lambda draft: Ok(
            ArtifactRef(
                identifier,
                draft.kind,
                draft.title,
                draft.revision,
                url,
                draft.content,
                provider_data,
            )
        ),
    )


def references(
    records: tuple[Mapping[str, Any], ...], *text_keys: str
) -> tuple[ArtifactRef, ...]:
    """The artifacts among stored comments; ordinary comments are left out."""
    return oks(
        reference(text(item, "id"), text(item, "url"), text(item, *text_keys), item)
        for item in records
    )


def added(record: Mapping[str, Any], draft: ArtifactDraft) -> ArtifactRef:
    """The reference to an artifact just stored, from the provider's reply and what was sent."""
    return ArtifactRef(
        text(record, "id"),
        draft.kind,
        draft.title,
        draft.revision,
        text(record, "url"),
        draft.content,
        record,
    )


def of_kind(artifacts: tuple[ArtifactRef, ...], kind: str) -> tuple[ArtifactRef, ...]:
    return tuple(item for item in artifacts if not kind or item.kind == kind)


def publish(
    ops: TrackerOps,
    ref: str,
    draft: ArtifactDraft,
    pause: Callable[[float], None] = time.sleep,
) -> Result[Published]:
    """Reuse the artifact with this title and revision, or add it, retrying what may be retried."""
    return bind(
        ops.list_artifacts(ref),
        lambda existing: _reuse_or_add(ops, ref, draft, existing, 0, pause),
    )


def _same(
    draft: ArtifactDraft, artifacts: tuple[ArtifactRef, ...]
) -> tuple[ArtifactRef, ...]:
    return tuple(
        item
        for item in artifacts
        if item.title == draft.title and item.revision == draft.revision
    )


def _reuse_or_add(
    ops: TrackerOps,
    ref: str,
    draft: ArtifactDraft,
    existing: tuple[ArtifactRef, ...],
    attempts: int,
    pause: Callable[[float], None],
) -> Result[Published]:
    match _same(draft, existing):
        case (found, *_):
            return Ok(Published(found, "reused", attempts))
        case ():
            return _add(ops, ref, draft, attempts + 1, pause)


def _add(
    ops: TrackerOps,
    ref: str,
    draft: ArtifactDraft,
    attempts: int,
    pause: Callable[[float], None],
) -> Result[Published]:
    match ops.add_artifact(ref, draft):
        case Ok(artifact):
            return Ok(Published(_filled(artifact, draft), "created", attempts))
        case Err(failure) if failure.retryable and attempts < MAX_ATTEMPTS:
            # A timed-out add may have landed: look again before adding again.
            pause(0.05 * attempts)
            return bind(
                ops.list_artifacts(ref),
                lambda existing: _reuse_or_add(
                    ops, ref, draft, existing, attempts, pause
                ),
            )
        case Err() as failed:
            return failed


def _filled(artifact: ArtifactRef, draft: ArtifactDraft) -> ArtifactRef:
    return replace(
        artifact,
        kind=artifact.kind or draft.kind,
        title=artifact.title or draft.title,
        revision=artifact.revision or draft.revision,
    )
