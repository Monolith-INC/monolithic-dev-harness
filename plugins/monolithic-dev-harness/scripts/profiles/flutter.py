from __future__ import annotations

from .base import WorkspaceProfile, load_profile


def get_profile() -> WorkspaceProfile:
    return load_profile("flutter")
