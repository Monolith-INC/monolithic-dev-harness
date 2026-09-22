"""Azure DevOps adapter for the estimation and capacity core.

Reads sprint capacity and work items; plans Task-hour writes but never performs them, and
never touches anyone's capacity settings.
"""

from __future__ import annotations

from typing import Any

from ...capacity.model import EstimableItem, IterationCapacity
from ..base import ProviderResult, WriteOp
from . import fields as f
from .client import AzureCapacityClient
from .mapping import map_capacities, map_iteration, map_work_items, reported_daily_total

__all__ = [
    "AzureCapacityClient",
    "AzureDevOpsProvider",
    "f",
    "map_iteration",
    "map_work_items",
]


class AzureDevOpsProvider:
    """Two ways in: injected payloads (primary) or a live client (fallback).

    Injection matches how the rest of this plugin reaches Azure -- a skill fetches through
    MCP and hands the JSON over -- and keeps the logic pure. The client is there for the
    capacity endpoints the MCP server does not expose.
    """

    name = "azure-devops"

    def __init__(
        self,
        *,
        client: AzureCapacityClient | None = None,
        process: str | None = None,
        payloads: dict[str, Any] | None = None,
    ) -> None:
        self.client = client
        self.process = f.normalize_process(process)
        self.payloads = payloads or {}

    # -- reads -------------------------------------------------------------

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        if self.payloads:
            capacities = self.payloads.get("capacities")
            return ProviderResult.success(
                map_iteration(
                    iteration_ref,
                    iteration=self.payloads.get("iteration"),
                    capacities=capacities,
                    team_settings=self.payloads.get("team_settings"),
                ),
                warnings=_capacity_cross_check(capacities),
            )

        if self.client is None:
            return ProviderResult.failure("no payloads injected and no Azure client configured")

        capacities, error = self.client.get_capacities(iteration_ref)
        if error:
            return ProviderResult.failure(error)

        warnings: list[str] = []
        iteration, iteration_error = self.client.get_iteration(iteration_ref)
        if iteration_error:
            warnings.append(f"iteration dates unavailable: {iteration_error}")
        settings, settings_error = self.client.get_team_settings()
        if settings_error:
            warnings.append(f"team settings unavailable: {settings_error}")

        warnings.extend(_capacity_cross_check(capacities))
        return ProviderResult.success(
            map_iteration(
                iteration_ref,
                iteration=iteration,
                capacities=capacities,
                team_settings=settings,
            ),
            warnings=tuple(warnings),
        )

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        if self.payloads:
            return ProviderResult.success(
                map_work_items(self.payloads.get("work_items"), process=self.process)
            )

        if self.client is None:
            return ProviderResult.failure("no payloads injected and no Azure client configured")

        listing, error = self.client.get_iteration_work_items(iteration_ref)
        if error:
            return ProviderResult.failure(error)

        ids = _extract_ids(listing)
        if not ids:
            return ProviderResult.success([], warnings=("iteration contains no work items",))

        detail, detail_error = self.client.get_work_items(ids)
        if detail_error:
            return ProviderResult.failure(detail_error)
        return ProviderResult.success(map_work_items(detail, process=self.process))

    # -- writes (planned, never performed) ---------------------------------

    def plan_hour_write(
        self,
        item_id: str,
        hours: float,
        *,
        activity: str | None = None,
        provenance: str = "",
    ) -> list[WriteOp]:
        """Plan the fields that make a Task visible to capacity bars and the burndown.

        Remaining Work is written on every process. Original Estimate is written only where
        it exists -- on Scrum it does not, and writing it there fails silently.
        """
        ops = [
            WriteOp(
                item_id=item_id,
                field_path=f.field_ref(f.REMAINING_WORK),
                value=hours,
                reason="drives sprint capacity bars and the burndown chart",
                provenance=provenance,
            )
        ]
        if f.supports_original_estimate(self.process):
            ops.append(
                WriteOp(
                    item_id=item_id,
                    field_path=f.field_ref(f.ORIGINAL_ESTIMATE),
                    value=hours,
                    reason="baseline estimate, set once",
                    provenance=provenance,
                )
            )
        if activity:
            ops.append(
                WriteOp(
                    item_id=item_id,
                    field_path=f.field_ref(f.activity_field(self.process)),
                    value=activity,
                    reason="allocates the hours to a capacity activity bucket",
                    provenance=provenance,
                )
            )
        return ops


def _capacity_cross_check(capacities: Any) -> tuple[str, ...]:
    """Compare the mapped per-member sum against Azure's own reported daily total.

    Free verification: a disagreement means the mapping dropped or misread somebody, which
    would otherwise show up only as a quietly understated sprint.
    """
    reported = reported_daily_total(capacities)
    if reported is None:
        return ()
    mapped = round(sum(m.daily_hours for m in map_capacities(capacities)), 2)
    if abs(mapped - reported) < 0.01:
        return ()
    return (
        f"capacity mismatch: mapped {mapped:g}h/day but Azure reports {reported:g}h/day — "
        "some members or activities could not be read, so availability is understated",
    )


def _extract_ids(payload: Any) -> list[str]:
    """Pull work-item ids out of the iteration workitems response."""
    if not isinstance(payload, dict):
        return []
    relations = payload.get("workItemRelations")
    if not isinstance(relations, list):
        return []
    ids: list[str] = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        target = relation.get("target")
        if isinstance(target, dict) and target.get("id") is not None:
            ids.append(str(target["id"]))
    return ids
