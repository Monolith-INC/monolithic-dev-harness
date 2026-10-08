"""Shared single-evaluation draft critic, independent of workflow task authorization."""

from pathlib import Path
from typing import Any

from core.result import Result, attempt

from .handlers import execute_handler


def evaluate(
    name: str, arguments: dict[str, Any], skills_dir: Path, state_dir: Path
) -> Result[dict[str, Any]]:
    return attempt(
        lambda: execute_handler(
            name, arguments, skills_dir=skills_dir, state_dir=state_dir
        ),
        "draft_review_failed",
        "evaluate draft",
        OSError,
        ValueError,
        TypeError,
    )
