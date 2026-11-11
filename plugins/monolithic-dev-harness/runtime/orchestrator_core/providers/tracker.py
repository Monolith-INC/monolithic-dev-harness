"""The selected tracker as a capacity source, through the sprint operations of its contract.

The tracker's adapter reads the sprint from its tracker (`sprint_capacity` and `sprint_items` in
its `TrackerOps`); this only adapts their `Ok`/`Err` answers to the planner's `ProviderResult`.
"""

from __future__ import annotations

from integrations.contracts import TrackerOps

from .base import ProviderResult


class TrackerProvider:
    name = "tracker"

    def __init__(self, tracker: TrackerOps) -> None:
        self.tracker = tracker

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        return ProviderResult.of(
            self.tracker.sprint_capacity(iteration_ref),
            lambda reading: reading.capacity,
            lambda reading: reading.warnings,
        )

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        return ProviderResult.of(self.tracker.sprint_items(iteration_ref), list)
