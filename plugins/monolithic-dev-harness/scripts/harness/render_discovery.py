"""Isolated entry to the unchanged vendored BMAD renderer and plugin dependencies."""

import sys
from pathlib import Path

sys.path[:0] = list(
    map(
        str,
        (
            Path(__file__).resolve().parents[2] / "runtime" / "python",
            Path(__file__).resolve().parents[2]
            / "vendor"
            / "bmad"
            / "skills"
            / "bmad"
            / "scripts",
        ),
    )
)

from render_skill import main

match __name__:
    case "__main__":
        raise SystemExit(main())
