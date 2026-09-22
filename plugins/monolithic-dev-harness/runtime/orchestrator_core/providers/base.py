from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..capacity.model import EstimableItem, IterationCapacity


@dataclass(frozen=True)
class WriteOp:
    """A write that has been worked out but not performed.

    Providers return these instead of mutating anything. The caller shows them to a human,
    and only a confirmed op is ever executed. This is what keeps a suggested hour figure
    from silently becoming a recorded one -- an estimate nobody agreed to is worse than an
    empty field, because the burndown then charts fiction while looking correct.
    """

    item_id: str
    field_path: str
    value: Any
    reason: str = ""
    provenance: str = ""
    requires_confirmation: bool = True

    def describe(self) -> str:
        note = f" [{self.provenance}]" if self.provenance else ""
        return f"{self.item_id}: {self.field_path} = {self.value}{note}"


@dataclass(frozen=True)
class ProviderResult:
    """Outcome wrapper following the never-raise idiom used across orchestrator_core."""

    ok: bool
    data: Any = None
    error: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def failure(cls, error: str) -> ProviderResult:
        return cls(ok=False, data=None, error=error)

    @classmethod
    def success(cls, data: Any, *, warnings: tuple[str, ...] = ()) -> ProviderResult:
        return cls(ok=True, data=data, warnings=warnings)


@runtime_checkable
class CapacityProvider(Protocol):
    """Reads sprint shape and contents from a backlog system."""

    name: str

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        """Return a ProviderResult carrying an IterationCapacity."""
        ...

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        """Return a ProviderResult carrying a list of EstimableItem."""
        ...


@runtime_checkable
class WorkItemWriter(Protocol):
    """Plans writes back to a backlog system. Planning is not performing."""

    name: str

    def plan_hour_write(
        self,
        item_id: str,
        hours: float,
        *,
        activity: str | None = None,
        provenance: str = "",
    ) -> list[WriteOp]:
        ...


__all__ = [
    "CapacityProvider",
    "EstimableItem",
    "IterationCapacity",
    "ProviderResult",
    "WorkItemWriter",
    "WriteOp",
]
