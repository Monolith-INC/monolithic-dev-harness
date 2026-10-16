"""Locate the project by its harness state; version control plays no part."""

from pathlib import Path


def root(start: Path) -> Path:
    """The nearest folder holding `.harness`, or `start` itself before setup created one."""
    return next(
        (
            candidate
            for candidate in (start.resolve(), *start.resolve().parents)
            if (candidate / ".harness").is_dir()
        ),
        start.resolve(),
    )
