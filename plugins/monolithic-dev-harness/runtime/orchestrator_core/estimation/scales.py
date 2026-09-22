from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PointScale:
    """An ordered set of allowed story-point values plus the split ceiling."""

    name: str
    values: tuple[float, ...]
    ceiling: float

    def is_valid(self, points: float) -> bool:
        return points in self.values

    def normalize(self, points: float) -> float:
        """Snap an arbitrary number to the nearest allowed value on this scale.

        Ties round up: a story that lands between two sizes is the larger one.
        """
        if not self.values:
            return points
        best = self.values[0]
        best_gap = abs(points - best)
        for value in self.values[1:]:
            gap = abs(points - value)
            if gap < best_gap or (gap == best_gap and value > best):
                best = value
                best_gap = gap
        return best

    def exceeds_ceiling(self, points: float) -> bool:
        return points > self.ceiling

    def split_count(self, points: float) -> int:
        """Number of sub-stories needed to bring `points` under the ceiling.

        Works in floats: truncating first would report "no split needed" for a 5.5-point
        story against a ceiling of 5, and a fractional ceiling would divide by zero.
        """
        if self.ceiling <= 0 or not self.exceeds_ceiling(points):
            return 1
        return math.ceil(points / self.ceiling)


FIBONACCI = PointScale(name="fibonacci", values=(1.0, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0), ceiling=5.0)

# The per-driver scale scored by the 6-driver heuristic. A Story's points are the MAX across
# drivers, with no exceptions -- two drivers at 5 is a 5-point Story, not an 8-point one. Two
# hard dimensions show up in the split decision, not by inflating the score.
DRIVER_MAX = PointScale(name="driver-max", values=(1.0, 2.0, 3.0, 5.0, 8.0), ceiling=5.0)

LINEAR = PointScale(name="linear", values=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0), ceiling=5.0)

SCALES: dict[str, PointScale] = {
    FIBONACCI.name: FIBONACCI,
    DRIVER_MAX.name: DRIVER_MAX,
    LINEAR.name: LINEAR,
}

DEFAULT_SCALE = FIBONACCI


def get_scale(name: str | None) -> PointScale:
    """Resolve a scale by name, degrading to the default when unknown."""
    if not name:
        return DEFAULT_SCALE
    return SCALES.get(name.strip().lower(), DEFAULT_SCALE)


DRIVERS = ("escopo", "incerteza", "integracoes", "dados", "qa", "rollout")


def story_points_from_drivers(scores: dict[str, float] | list[float]) -> float | None:
    """A Story's points are the MAX across its drivers -- never the sum, and with no exceptions.

    Two drivers at 5 make a 5-point Story, not an 8-point one. Where two dimensions are both
    hard, that belongs in the split decision rather than in an inflated score.

    Returns None for an empty or unusable set of scores.
    """
    values = list(scores.values()) if isinstance(scores, dict) else list(scores)
    usable = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
    return max(usable) if usable else None


def dominant_drivers(scores: dict[str, float]) -> list[str]:
    """Names of the drivers sitting at the MAX -- what a Complexity note must record."""
    top = story_points_from_drivers(scores)
    if top is None:
        return []
    return [name for name, value in scores.items() if isinstance(value, (int, float)) and value == top]
