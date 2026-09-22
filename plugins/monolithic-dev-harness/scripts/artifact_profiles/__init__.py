"""Artifact critic profiles (spec / resolution)."""

from __future__ import annotations

import os
import sys

# Bare imports (artifact_reflection, …) need scripts/ on path when loaded as scripts.artifact_profiles.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
