"""Generic estimation core.

Turns story points into suggested hours. Provider-agnostic and I/O-free: everything here
is a pure function over dataclasses, so the same engine serves a local draft and an Azure
DevOps work item alike.

The engine never asserts an hour figure as fact. Every `HourEstimate` carries a provenance
and a confidence so a caller can tell a calibrated number from a defaulted one, and callers
are expected to put a human between a suggestion and any write.
"""

from __future__ import annotations

from .breakdown import (
    DEFAULT_ROLE_WEIGHTS,
    BreakdownEstimate,
    TaskEstimate,
    TaskInput,
    estimate_breakdown,
    recompute_breakdown,
    task_role,
)
from .calibration import (
    Calibration,
    CompletedItem,
    Divergence,
    calibrate,
    compare_to_halstead,
    halstead_hours,
)
from .config import EstimationConfig, config_diagnostics, load_config, parse_config
from .mapping import HourEstimate, distribute_hours, estimate_hours
from .scales import (
    DEFAULT_SCALE,
    DRIVERS,
    SCALES,
    PointScale,
    dominant_drivers,
    get_scale,
    story_points_from_drivers,
)

__all__ = [
    "BreakdownEstimate",
    "DEFAULT_ROLE_WEIGHTS",
    "Calibration",
    "CompletedItem",
    "DEFAULT_SCALE",
    "DRIVERS",
    "Divergence",
    "EstimationConfig",
    "HourEstimate",
    "PointScale",
    "SCALES",
    "TaskEstimate",
    "TaskInput",
    "calibrate",
    "compare_to_halstead",
    "config_diagnostics",
    "distribute_hours",
    "dominant_drivers",
    "estimate_breakdown",
    "estimate_hours",
    "estimate_work_item",
    "get_scale",
    "halstead_hours",
    "load_config",
    "parse_config",
    "recompute_breakdown",
    "story_points_from_drivers",
    "task_role",
]


def estimate_work_item(
    points: float | None,
    *,
    config: EstimationConfig | None = None,
    history: list[CompletedItem] | None = None,
) -> HourEstimate | None:
    """Facade: points in, suggested hours out, calibrating from history when available."""
    config = config or EstimationConfig()
    calibration = calibrate(history or [], settings=config.calibration)
    return estimate_hours(points, config=config, calibration=calibration)
