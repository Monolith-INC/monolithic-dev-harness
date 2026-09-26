"""What the rules need to know about trackers, built once per hook call from the tracker folders.

Which calls write to a tracker comes from every usable tracker (shipped, or onboarded and trusted),
not only the selected one: the Azure DevOps server is registered with the host whichever tracker a
repository selects, and its writes need approval all the same. Protected ids are found the same
way. When the selected tracker is missing or invalid, `problem` says why and the rules refuse
tracker writes until a person fixes it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from core.result import Ok, Result
from integrations import registry
from integrations.contracts import Manifest, WriteRules

from .settings import Settings


@dataclass(frozen=True)
class TrackerPolicy:
    writes: tuple[WriteRules, ...]
    ids: tuple[re.Pattern[str], ...]
    mentions: tuple[re.Pattern[str], ...]
    protected: frozenset[str]
    problem: str


def build(repo: Path, settings: Result[Settings]) -> TrackerPolicy:
    manifests = registry.usable(repo)
    return TrackerPolicy(
        writes=tuple(manifest.writes for manifest in manifests),
        ids=tuple(re.compile(manifest.ids.pattern) for manifest in manifests),
        mentions=tuple(_mentions(manifests)),
        protected=frozenset(item.upper() for item in _protected(settings)),
        problem=_problem(registry.resolve(repo, settings)),
    )


def _mentions(manifests: Iterable[Manifest]) -> Iterable[re.Pattern[str]]:
    return (
        re.compile(
            registry.mention_expression(template, manifest.ids.pattern), re.IGNORECASE
        )
        for manifest in manifests
        if manifest.ids.mentions_link
        for template in manifest.ids.mention
    )


def _protected(settings: Result[Settings]) -> frozenset[str]:
    match settings:
        case Ok(chosen):
            return chosen.protected_work_items
        case _:
            return frozenset()


def _problem(resolution: registry.Resolution) -> str:
    match resolution:
        case registry.Invalid(failure):
            return failure.message
        case registry.NotConfigured(reason):
            return reason
        case _:
            return ""


def writes_to_tracker(policy: TrackerPolicy, server: str, tool: str) -> bool:
    """Whether a host MCP call is one a tracker declares as a write.

    A call whose server the host did not name is judged by the tool name alone.
    """
    return any(
        (not server or (rules.server and rules.server in server))
        and any(fnmatchcase(tool, pattern) for pattern in rules.tools)
        for rules in policy.writes
    )


def ids_in(policy: TrackerPolicy, value: str) -> frozenset[str]:
    """Every tracker id the value holds, in any usable tracker's id format, upper-cased."""
    return frozenset(
        match.group(0).upper()
        for pattern in policy.ids
        for match in pattern.finditer(value)
    )


def mentioned_in(policy: TrackerPolicy, text: str) -> frozenset[str]:
    """Ids that text links when a tracker saves it, upper-cased."""
    return frozenset(
        next(group for group in match.groups() if group).upper()
        for pattern in policy.mentions
        for match in pattern.finditer(text)
    )
