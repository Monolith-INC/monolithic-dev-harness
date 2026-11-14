"""The shipped Azure DevOps tracker, driven the way the backlog stage drives it: through TrackerOps.

The adapter reads the sprint itself; these helpers stand a fake Azure DevOps server behind it that
answers with the given replies, and read what comes back. Azure's reply shapes stay private to
`trackers/azure-devops/adapter.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest import mock

import orchestrator_core  # noqa: F401 - puts the plugin's scripts/ on the import path
from integrations.planning import EstimableItem, IterationCapacity, IterationReading
from tests.integrations.fakes import FakeTransport, ops
from tests.settings_fixture import write_settings

AZURE = {"organization": "o", "project": "p"}
REMAINING_WORK = "/fields/Microsoft.VSTS.Scheduling.RemainingWork"
ORIGINAL_ESTIMATE = "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate"
# The team's iteration listing when a test names no `iteration` reply: one sprint, "it1".
SPRINT = {"id": "it1", "name": "it1", "path": "p\\it1"}


def server(**replies: Any) -> FakeTransport:
    """A fake Azure DevOps server answering the sprint reads with `replies`."""

    def work(args: dict[str, Any]) -> Any:
        match args["action"]:
            case "list_team_iterations":
                return replies.get("iteration", [SPRINT])
            case "get_team_capacity":
                return replies.get("capacities", [])
            case "get_team_settings":
                return replies.get("team_settings", {})
        raise AssertionError(args)

    def read(args: dict[str, Any]) -> Any:
        match args["action"]:
            case "list_for_iteration":
                return {"workItemRelations": [{"target": {"id": 1}}]}
            case "get_batch":
                return replies.get("work_items", [])
        raise AssertionError(args)

    return FakeTransport({"work": work, "wit_work_item": read})


def linear_server(cycles: Any = (), issues: Any = ()) -> FakeTransport:
    """A fake Linear server answering the cycle reads."""
    return FakeTransport(
        {
            "list_cycles": lambda args: list(cycles),
            "list_issues": lambda args: list(issues),
        }
    )


@contextmanager
def serving(transport: FakeTransport | None) -> Iterator[None]:
    """The selected tracker, opened by the backlog runtime through the host gateway, is backed
    by `transport`: the gateway's provider server is the fake."""
    if transport is None:
        yield
        return
    import integrations.gateway_client  # noqa: F401 - the patch target must be loaded
    from integrations import registry

    with mock.patch(
        "integrations.gateway_client.open_selected",
        lambda active, repo: registry.build(active, repo, transport),
    ):
        yield


def tracker(process: str = "agile", **replies: Any):
    """The Azure adapter's `TrackerOps`, backed by a fake server answering with `replies`."""
    return ops("azure-devops", {**AZURE, "process": process}, server(**replies))


def reading(ref: str = "it1", **replies: Any) -> IterationReading:
    return tracker(**replies).sprint_capacity(ref).value


def sprint(ref: str = "it1", **replies: Any) -> IterationCapacity:
    return reading(ref, **replies).capacity


def refused(ref: str = "it1", **replies: Any) -> str:
    """Why the tracker refuses to read these replies as a sprint."""
    return tracker(**replies).sprint_capacity(ref).failure.code


def items_refused(work_items: Any) -> str:
    return tracker(work_items=work_items).sprint_items("it1").failure.code


def members(capacities: Any):
    return sprint(capacities=capacities).members


def days_off(payload: Any):
    return sprint(team_settings={"teamDaysOff": payload}).team_days_off


def weekend(team_settings: Any) -> tuple[int, ...]:
    return sprint(team_settings=team_settings).weekend_days


def items(work_items: Any, process: str = "agile") -> tuple[EstimableItem, ...]:
    return tracker(process, work_items=work_items).sprint_items("it1").value


def item(record: Any, process: str = "agile") -> EstimableItem | None:
    return next(iter(items([record], process)), None)


def select_azure(root: Path, process: str = "agile") -> None:
    """Write the repository's settings, selecting Azure DevOps with this process."""
    write_settings(
        root, tracker={"name": "azure-devops", "values": {**AZURE, "process": process}}
    )
