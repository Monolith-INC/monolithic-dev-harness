from __future__ import annotations

from dataclasses import dataclass

from .config import CalibrationSettings

# Halstead's Stroud number: elementary mental discriminations per second.
# Halstead, "Elements of Software Science" (1977): T = E / S seconds.
STROUD_NUMBER = 18.0


@dataclass(frozen=True)
class CompletedItem:
    """One delivered work item with both its estimate and what it actually cost."""

    points: float
    actual_hours: float
    iteration: str | None = None
    item_id: str | None = None


@dataclass(frozen=True)
class Calibration:
    """An empirically derived hours-per-point figure, or the absence of one."""

    hours_per_point: float | None
    sample_size: int
    confidence: str
    """"high" | "low" | "none" -- "none" means there is no usable figure."""
    detail: str = ""

    @property
    def usable(self) -> bool:
        return self.hours_per_point is not None and self.hours_per_point > 0


def _usable_items(items: list[CompletedItem]) -> list[CompletedItem]:
    return [i for i in items if i.points > 0 and i.actual_hours > 0]


def _window(items: list[CompletedItem], window_iterations: int) -> list[CompletedItem]:
    """Keep only items from the most recent N iterations, preserving order.

    Items with no iteration are always kept -- absent grouping information, dropping
    them would silently shrink the sample.
    """
    seen: list[str] = []
    for item in items:
        if item.iteration and item.iteration not in seen:
            seen.append(item.iteration)
    if len(seen) <= window_iterations:
        return items
    keep = set(seen[-window_iterations:])
    return [i for i in items if not i.iteration or i.iteration in keep]


def calibrate(
    items: list[CompletedItem],
    *,
    settings: CalibrationSettings | None = None,
) -> Calibration:
    """Derive hours-per-point from completed work.

    Uses the ratio of summed hours to summed points rather than the mean of per-item
    ratios, so a large item carries proportionally more weight than a small one.
    """
    settings = settings or CalibrationSettings()
    if not settings.enabled:
        return Calibration(None, 0, "none", "calibration disabled in config")

    usable = _usable_items(_window(_usable_items(items), settings.window_iterations))
    if not usable:
        return Calibration(None, 0, "none", "no completed items with both points and hours")

    total_points = sum(i.points for i in usable)
    total_hours = sum(i.actual_hours for i in usable)
    if total_points <= 0:
        return Calibration(None, len(usable), "none", "completed points sum to zero")

    ratio = total_hours / total_points
    sample = len(usable)
    if sample < settings.min_sample:
        return Calibration(
            ratio,
            sample,
            "low",
            f"{sample} completed items, below min_sample={settings.min_sample}",
        )
    return Calibration(ratio, sample, "high", f"{sample} completed items over {total_points:g} points")


def halstead_hours(effort: float) -> float | None:
    """Halstead time-to-program, in hours. Returns None for a non-positive effort.

    This estimates from code that already exists, so it can only ever be a retrospective
    cross-check -- never a forward estimate for unwritten work.
    """
    if effort <= 0:
        return None
    return effort / STROUD_NUMBER / 3600.0


@dataclass(frozen=True)
class Divergence:
    """How far a point-based estimate sits from an independent code-derived one."""

    estimated_hours: float
    derived_hours: float
    ratio: float
    verdict: str
    """"aligned" | "under-estimated" | "over-estimated"."""


def compare_to_halstead(
    estimated_hours: float,
    *,
    effort: float,
    tolerance: float = 2.0,
) -> Divergence | None:
    """Report divergence between a point estimate and Halstead's derived time.

    Reports only -- never overrides the point estimate. `tolerance` is a multiplicative
    band: within a factor of 2 in either direction counts as aligned, because the two
    methods measure genuinely different things.
    """
    derived = halstead_hours(effort)
    if derived is None or estimated_hours <= 0:
        return None
    ratio = estimated_hours / derived
    if ratio > tolerance:
        verdict = "over-estimated"
    elif ratio < 1.0 / tolerance:
        verdict = "under-estimated"
    else:
        verdict = "aligned"
    return Divergence(
        estimated_hours=estimated_hours,
        derived_hours=derived,
        ratio=ratio,
        verdict=verdict,
    )
