"""Linear work-item adapter.

Network access is supplied by Linear's optional MCP connector. This module stays pure: it maps
neutral artifacts to connector requests and connector results back to the neutral model.
"""

from __future__ import annotations

from typing import Any

from .base import ProviderResult
from .work_items import LinearWorkItemAdapter


class LinearProvider:
    name = "linear"

    def __init__(self, *, payloads: dict[str, Any] | None = None, team: str | None = None) -> None:
        self.payloads = payloads or {}
        self.team = team
        self.work_items = LinearWorkItemAdapter()

    def create_request(self, artifact: Any) -> ProviderResult:
        if not self.team:
            return ProviderResult.failure("Linear team is not configured")
        try:
            return ProviderResult.success(self.work_items.create_request(artifact, container_id=self.team))
        except ValueError as exc:
            return ProviderResult.failure(str(exc))

    def read_result(self, payload: dict[str, Any]) -> ProviderResult:
        try:
            return ProviderResult.success(self.work_items.read_result(payload))
        except ValueError as exc:
            return ProviderResult.failure(str(exc))

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        return ProviderResult.failure(
            "Linear cycle capacity is not part of the backlog artifact adapter; use the filesystem or Azure capacity provider"
        )

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        issues = self.payloads.get("issues")
        if not isinstance(issues, list):
            return ProviderResult.success([])
        records = tuple(self.read_result(issue) for issue in issues if isinstance(issue, dict))
        failures = tuple(result.error or "invalid Linear issue" for result in records if not result.ok)
        if failures:
            return ProviderResult.failure("; ".join(failures))
        return ProviderResult.success([result.data for result in records])
