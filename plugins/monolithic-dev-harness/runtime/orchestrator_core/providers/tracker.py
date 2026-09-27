"""The selected tracker as a capacity source, through the planning operations of its contract.

The translation from provider replies lives in the tracker's own folder (`read_iteration` and
`iteration_items` in its `TrackerOps`); this only adapts their `Ok`/`Err` answers to the
planner's `ProviderResult`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.result import Err, Ok
from integrations.contracts import TrackerOps

from .base import ProviderResult


class TrackerProvider:
    name = "tracker"

    def __init__(self, tracker: TrackerOps, replies: Mapping[str, Any]) -> None:
        self.tracker = tracker
        self.replies = replies

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        match self.tracker.read_iteration(self.replies, iteration_ref):
            case Ok(reading):
                return ProviderResult.success(
                    reading.capacity, warnings=reading.warnings
                )
            case Err(failure):
                return ProviderResult.failure(failure.message)

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        match self.tracker.iteration_items(self.replies, iteration_ref):
            case Ok(items):
                return ProviderResult.success(list(items))
            case Err(failure):
                return ProviderResult.failure(failure.message)
