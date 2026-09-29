"""The selected tracker as a capacity source, through the planning operations of its contract.

The translation from provider replies lives in the tracker's own folder (`read_iteration` and
`iteration_items` in its `TrackerOps`); this only adapts their `Ok`/`Err` answers to the
planner's `ProviderResult`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from integrations.contracts import TrackerOps

from .base import ProviderResult


class TrackerProvider:
    name = "tracker"

    def __init__(self, tracker: TrackerOps, replies: Mapping[str, Any]) -> None:
        self.tracker = tracker
        self.replies = replies

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        return ProviderResult.of(
            self.tracker.read_iteration(self.replies, iteration_ref),
            lambda reading: reading.capacity,
            lambda reading: reading.warnings,
        )

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        return ProviderResult.of(
            self.tracker.iteration_items(self.replies, iteration_ref), list
        )
