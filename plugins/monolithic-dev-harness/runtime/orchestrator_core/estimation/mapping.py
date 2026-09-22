from __future__ import annotations

from dataclasses import dataclass

from .calibration import Calibration
from .config import EstimationConfig

PROVENANCE_CALIBRATED = "calibrated"
PROVENANCE_CONFIG = "config"
PROVENANCE_SEED = "seed-default"


@dataclass(frozen=True)
class HourEstimate:
    """A suggested duration, carrying enough context to judge how much to trust it."""

    points: float
    hours: float
    low: float
    high: float
    provenance: str
    """"calibrated" | "config" | "seed-default"."""
    sample_size: int = 0
    confidence: str = "none"
    """"high" | "low" | "none"."""
    detail: str = ""

    @property
    def is_suggestion_only(self) -> bool:
        """True when nothing but a default stands behind this number."""
        return self.provenance == PROVENANCE_SEED or self.confidence == "none"

    def describe(self) -> str:
        """One line a human can read before accepting or rejecting the number."""
        band = f"{self.low:g}-{self.high:g}h"
        label = {
            PROVENANCE_CALIBRATED: f"calibrated from {self.sample_size} completed items",
            PROVENANCE_CONFIG: "from team config",
            PROVENANCE_SEED: "seed default -- NOT calibrated, confirm before use",
        }.get(self.provenance, self.provenance)
        return f"{self.points:g} pts -> {self.hours:g}h ({band}, {label})"


def _band_midpoint(low: float, high: float) -> float:
    return round((low + high) / 2.0, 2)


def estimate_hours(
    points: float | None,
    *,
    config: EstimationConfig,
    calibration: Calibration | None = None,
) -> HourEstimate | None:
    """Suggest a duration for a point value.

    Prefers an empirically calibrated rate; falls back to the configured band; falls back
    again to the seed default. Returns None when there is nothing to work from -- an absent
    estimate is honest, a fabricated one is not.
    """
    if points is None or points <= 0:
        return None

    if calibration is not None and calibration.usable:
        rate = calibration.hours_per_point or 0.0
        hours = round(points * rate, 2)
        spread = 0.25 if calibration.confidence == "high" else 0.5
        return HourEstimate(
            points=points,
            hours=hours,
            low=round(hours * (1 - spread), 2),
            high=round(hours * (1 + spread), 2),
            provenance=PROVENANCE_CALIBRATED,
            sample_size=calibration.sample_size,
            confidence=calibration.confidence,
            detail=calibration.detail,
        )

    band = config.band_for(points)
    if band is None:
        band = _interpolate_band(points, config)
    if band is None:
        return None

    low, high = band
    provenance = PROVENANCE_SEED if config.source == "seed-default" else PROVENANCE_CONFIG
    return HourEstimate(
        points=points,
        hours=_band_midpoint(low, high),
        low=low,
        high=high,
        provenance=provenance,
        sample_size=0,
        confidence="none",
        detail="no calibration data; band lookup only",
    )


def _interpolate_band(points: float, config: EstimationConfig) -> tuple[float, float] | None:
    """Derive a band for an off-scale point value from the nearest configured neighbour.

    Scales the neighbouring band linearly. This is a fallback for values the team's own
    table does not cover, and it inherits that table's provenance -- it invents no new rate.
    """
    if not config.bands:
        return None
    nearest = min(config.bands, key=lambda p: (abs(p - points), p))
    if nearest <= 0:
        return None
    low, high = config.bands[nearest]
    factor = points / nearest
    return round(low * factor, 2), round(high * factor, 2)


def distribute_hours(total_hours: float, weights: list[float | None]) -> list[float]:
    """Split a story's hours across its tasks, preserving the total.

    A zero weight means zero hours, and stays zero: a marker task that carries no work must
    not pick up rounding drift. Drift lands on the largest share instead, where it is
    proportionally smallest.

    `None` means "no information" and falls back to an equal share. That is deliberately
    distinct from `0`, which is a decision -- a list of nothing but zero weights yields all
    zeros rather than silently handing a marker task the whole story.
    """
    if not weights or total_hours <= 0:
        return [0.0] * len(weights) if weights else []

    if all(w is None for w in weights):
        positive = [1.0] * len(weights)
    else:
        positive = [max(0.0, w) if w is not None else 1.0 for w in weights]

    total_weight = sum(positive)
    if total_weight <= 0:
        # Every supplied weight was zero: an explicit decision, so honour it.
        return [0.0] * len(weights)

    out = [round(total_hours * w / total_weight, 2) for w in positive]
    drift = round(total_hours - sum(out), 2)
    if drift:
        # Largest non-zero share absorbs it; never a task weighted out of the split.
        target = max(
            (i for i, w in enumerate(positive) if w > 0),
            key=lambda i: out[i],
            default=None,
        )
        if target is not None:
            out[target] = round(out[target] + drift, 2)
    return out
