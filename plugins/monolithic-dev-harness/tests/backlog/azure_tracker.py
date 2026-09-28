"""The shipped Azure DevOps tracker, driven the way the backlog stage drives it: through TrackerOps.

The translation of Azure's replies stays private to `trackers/azure-devops/adapter.py`; these
helpers only hand replies to `read_iteration` and `iteration_items` and read what comes back.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orchestrator_core  # noqa: F401 - puts the plugin's scripts/ on the import path
from integrations.planning import EstimableItem, IterationCapacity, IterationReading
from tests.integrations.fakes import ops
from tests.settings_fixture import write_settings

AZURE = {"organization": "o", "project": "p"}
REMAINING_WORK = "/fields/Microsoft.VSTS.Scheduling.RemainingWork"
ORIGINAL_ESTIMATE = "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate"


def tracker(process: str = "agile"):
    """The Azure adapter's `TrackerOps`, with no server behind it."""
    return ops("azure-devops", {**AZURE, "process": process})


def reading(ref: str = "it1", **replies: Any) -> IterationReading:
    return tracker().read_iteration(replies, ref).value


def sprint(ref: str = "it1", **replies: Any) -> IterationCapacity:
    return reading(ref, **replies).capacity


def members(capacities: Any):
    return sprint(capacities=capacities).members


def days_off(payload: Any):
    return sprint(team_settings={"teamDaysOff": payload}).team_days_off


def weekend(team_settings: Any) -> tuple[int, ...]:
    return sprint(team_settings=team_settings).weekend_days


def items(work_items: Any, process: str = "agile") -> tuple[EstimableItem, ...]:
    return tracker(process).iteration_items({"work_items": work_items}, "it1").value


def item(record: Any, process: str = "agile") -> EstimableItem | None:
    return next(iter(items([record], process)), None)


def select_azure(root: Path, process: str = "agile") -> None:
    """Write the repository's settings, selecting Azure DevOps with this process."""
    write_settings(
        root, tracker={"name": "azure-devops", "values": {**AZURE, "process": process}}
    )
