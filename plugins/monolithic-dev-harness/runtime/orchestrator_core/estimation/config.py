from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .scales import DEFAULT_SCALE, PointScale, get_scale

CONFIG_RELPATH = Path("estimation.json")

# Seed bands. THIS IS A STARTING-POINT REFERENCE, NOT A METRIC.
#
# There is no published algorithm converting story points to hours -- points are
# deliberately unitless and team-relative. These bands exist only so a team has
# something to react to on day one. Every estimate derived from them is stamped
# provenance="seed-default" so a reader can tell it apart from a calibrated figure.
# Replace them by editing .agile-backlog-toolkit/estimation.json, or let calibration take over
# once enough completed work exists.
SEED_BANDS: dict[float, tuple[float, float]] = {
    1.0: (1.0, 2.0),
    2.0: (2.0, 4.0),
    3.0: (4.0, 6.0),
    5.0: (8.0, 16.0),
    8.0: (24.0, 40.0),
    13.0: (40.0, 80.0),
    21.0: (80.0, 160.0),
}

DEFAULT_MIN_SAMPLE = 8
DEFAULT_WINDOW_ITERATIONS = 6


@dataclass(frozen=True)
class CalibrationSettings:
    enabled: bool = True
    min_sample: int = DEFAULT_MIN_SAMPLE
    window_iterations: int = DEFAULT_WINDOW_ITERATIONS


@dataclass(frozen=True)
class EstimationConfig:
    scale: PointScale = DEFAULT_SCALE
    bands: dict[float, tuple[float, float]] = field(default_factory=lambda: dict(SEED_BANDS))
    calibration: CalibrationSettings = field(default_factory=CalibrationSettings)
    hours_per_day: float = 6.0
    source: str = "seed-default"
    """Where the bands came from: "seed-default" or the config path that supplied them."""

    rejected_bands: tuple[str, ...] = ()
    """Band keys the config file declared but that could not be read. Never silently ignored."""

    def band_for(self, points: float) -> tuple[float, float] | None:
        return self.bands.get(points)


def _coerce_band(value: Any) -> tuple[float, float] | None:
    if isinstance(value, dict):
        low = value.get("low")
        high = value.get("high")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        low, high = value
    else:
        return None
    try:
        low_f = float(low)
        high_f = float(high)
    except (TypeError, ValueError):
        return None
    if low_f > high_f:
        low_f, high_f = high_f, low_f
    return low_f, high_f


def _parse_bands(raw: Any) -> tuple[dict[float, tuple[float, float]] | None, list[str]]:
    """Parse the band table, reporting entries that could not be read.

    A partial parse must not be presented as the team's configuration: an entry nobody could
    read is a misconfiguration the team should hear about, not a gap to quietly interpolate.
    """
    if not isinstance(raw, dict) or not raw:
        return None, []
    bands: dict[float, tuple[float, float]] = {}
    rejected: list[str] = []
    for key, value in raw.items():
        try:
            points = float(key)
        except (TypeError, ValueError):
            rejected.append(str(key))
            continue
        band = _coerce_band(value)
        if band is None:
            rejected.append(str(key))
            continue
        bands[points] = band
    return ((bands or None) if not rejected else None), rejected


def config_diagnostics(config: EstimationConfig) -> tuple[str, ...]:
    """Return actionable diagnostics for estimation configuration that was rejected."""
    if not config.rejected_bands:
        return ()
    keys = ", ".join(config.rejected_bands)
    return (f"invalid estimation bands ignored ({keys}); using seed defaults",)


def _parse_calibration(raw: Any) -> CalibrationSettings:
    if not isinstance(raw, dict):
        return CalibrationSettings()

    def _int(key: str, fallback: int) -> int:
        try:
            return int(raw.get(key, fallback))
        except (TypeError, ValueError):
            return fallback

    return CalibrationSettings(
        enabled=bool(raw.get("enabled", True)),
        min_sample=max(1, _int("min_sample", DEFAULT_MIN_SAMPLE)),
        window_iterations=max(1, _int("window_iterations", DEFAULT_WINDOW_ITERATIONS)),
    )


def config_path(state_dir: Path) -> Path:
    return state_dir / CONFIG_RELPATH


def parse_config(data: dict[str, Any], *, source: str = "config") -> EstimationConfig:
    """Build a config from an already-decoded mapping. Unknown values fall back to defaults."""
    scale = get_scale(data.get("scale") if isinstance(data.get("scale"), str) else None)
    ceiling = data.get("ceiling")
    if isinstance(ceiling, (int, float)) and ceiling > 0:
        scale = PointScale(name=scale.name, values=scale.values, ceiling=float(ceiling))

    bands, rejected = _parse_bands(data.get("bands"))
    hours_per_day = data.get("hours_per_day")
    try:
        hours_per_day_f = float(hours_per_day) if hours_per_day is not None else 6.0
    except (TypeError, ValueError):
        hours_per_day_f = 6.0

    return EstimationConfig(
        scale=scale,
        bands=bands if bands is not None else dict(SEED_BANDS),
        calibration=_parse_calibration(data.get("calibration")),
        hours_per_day=hours_per_day_f if hours_per_day_f > 0 else 6.0,
        source=source if bands is not None else "seed-default",
        rejected_bands=tuple(rejected),
    )


def load_config(state_dir: Path) -> EstimationConfig:
    """Read .agile-backlog-toolkit/estimation.json, degrading to seed defaults when absent or malformed."""
    path = config_path(state_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return EstimationConfig()
    if not isinstance(data, dict):
        return EstimationConfig()
    return parse_config(data, source=str(path))
