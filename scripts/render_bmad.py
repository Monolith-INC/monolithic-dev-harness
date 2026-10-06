#!/usr/bin/env python3
"""Ship BMAD runtime templates; discovery resolves them in the actual project.

render_bmad.py copies the owned Stage 0 templates to the plugin skill.
render_bmad.py --check checks that shipped templates match their canonical source.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "monolithic-dev-harness"
SKILL = PLUGIN / "skills" / "bmad-build"
SOURCES = PLUGIN / "vendor" / "bmad" / "harness" / "bmad-build"
STEPS = (
    "workflow.md",
    "step-01-clarify-and-route.md",
    "step-02-plan.md",
    "plan-template.md",
)


def render() -> dict[str, str]:
    return {name: (SOURCES / name).read_text(encoding="utf-8") for name in STEPS}


def publish(expected: dict[str, str]) -> tuple[int, ...]:
    return tuple(
        (SKILL / name).write_text(text, encoding="utf-8")
        for name, text in expected.items()
    )


def check(expected: dict[str, str]) -> int:
    return int(
        any(
            not (SKILL / name).is_file()
            or (SKILL / name).read_text(encoding="utf-8") != text
            for name, text in expected.items()
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    match parser.parse_args().check:
        case True:
            return check(render())
        case False:
            publish(render())
            return 0


match __name__:
    case "__main__":
        raise SystemExit(main())
