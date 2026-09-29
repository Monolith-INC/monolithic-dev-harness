"""Capacity sources for the estimation and capacity core.

Two sources: the user's own planning files (`filesystem`), or the selected tracker through its
planning capability (`tracker`). Everything a tracker knows about its own replies and fields lives
in its folder, `trackers/<name>/`; nothing here names a provider.
"""

from __future__ import annotations

from .base import CapacityProvider, ProviderResult
from .filesystem import FilesystemProvider
from .tracker import TrackerProvider

__all__ = [
    "CapacityProvider",
    "FilesystemProvider",
    "ProviderResult",
    "TrackerProvider",
]
