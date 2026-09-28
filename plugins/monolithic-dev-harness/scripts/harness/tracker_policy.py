"""What the rules need to know about trackers, built once per hook call from the tracker folders.

Which calls write to a tracker comes from every shipped tracker and every onboarded folder, not only
the selected one: the Azure DevOps server is registered with the host whichever tracker a repository
selects, and its writes need approval all the same. An onboarded folder counts even when it is not
trusted or fails its checks, since that can only ask for more approvals. Protected ids come from
every usable tracker (shipped, or onboarded and trusted). When the selected tracker is missing or invalid, `problem` says why and the rules refuse
tracker writes until a person fixes it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from core.result import Ok, Result, failures, oks
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
    """Every tracker folder is read once here; the selection is resolved among the same reads.

    A shipped tracker that fails its checks means the installation is broken, which is a problem
    as much as a broken selection: which tools write can no longer be known. The same goes for an
    onboarded folder that does not say which tools write. One that says, but is untrusted or
    fails its other checks, still counts toward the writes: that only asks for more approvals.
    """
    results = registry.shipped()
    everything = (*results, *registry.onboarded(repo))
    manifests = oks(everything)
    onboarded_writes = registry.onboarded_writes(repo)
    folder_problem = next(
        (failure.message for failure in failures((*results, *onboarded_writes))), ""
    )
    return TrackerPolicy(
        writes=(
            *(manifest.writes for manifest in oks(results)),
            *oks(onboarded_writes),
        ),
        ids=tuple(re.compile(manifest.ids.pattern) for manifest in manifests),
        mentions=tuple(_mentions(manifests)),
        protected=frozenset(item.upper() for item in _protected(settings)),
        problem=folder_problem
        or _problem(registry.resolve_among(everything, repo, settings)),
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


# The harness's own servers: the gateway lists its writes itself, the orchestrators never write.
HARNESS_SERVERS = (
    "workflow-integrations",
    "backlog-orchestrator",
    "workflow-orchestrator",
)


def writes_to_tracker(policy: TrackerPolicy, server: str, tool: str) -> bool:
    """Whether a host MCP call is one a tracker declares as a write.

    A call whose server the host did not name is judged by the tool name alone. While the tracker
    folders cannot be trusted to say (`problem`), every call to a server that is not the harness's
    own counts as a write, so a broken tracker fails closed.
    """
    unknown = (
        bool(policy.problem)
        and bool(server)
        and not any(name in server for name in HARNESS_SERVERS)
    )
    return unknown or any(
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
