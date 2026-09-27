"""What the capacity planner reads from: a source of sprint shape and sprint contents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


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
    """Reads sprint shape and contents."""

    name: str

    def fetch_iteration(self, iteration_ref: str) -> ProviderResult:
        """A ProviderResult carrying an IterationCapacity."""
        ...

    def fetch_work_items(self, iteration_ref: str) -> ProviderResult:
        """A ProviderResult carrying a list of EstimableItem."""
        ...


__all__ = ["CapacityProvider", "ProviderResult"]
