"""Locate project state without asking a version-control provider to run."""

from pathlib import Path


def root(start: Path) -> Path:
    return next(
        (
            candidate
            for candidate in (start.resolve(), *start.resolve().parents)
            if (candidate / ".harness").is_dir() or (candidate / ".git").exists()
        ),
        start.resolve(),
    )
