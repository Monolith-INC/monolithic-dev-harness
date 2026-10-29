"""A project's paths come from the project, never from a repository around it (Article 10)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness import gitstate, local_tracker, state


@pytest.fixture
def nested(tmp_path: Path) -> tuple[Path, Path]:
    """An unversioned project with an empty `.git` folder, inside another repository."""
    outer = tmp_path / "outer"
    project = outer / "temp" / "project"
    (project / ".git").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(outer)], check=True)
    return outer, project


def test_the_tracker_lives_in_the_project(nested) -> None:
    _, project = nested
    assert local_tracker.storage_root(project) == project / "Tickets"


def test_nothing_is_excluded_in_a_repository_around_the_project(nested) -> None:
    outer, project = nested
    exclude = outer / ".git/info/exclude"
    before = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    assert gitstate.own_exclude(project) is None
    assert state.ensure_local_exclude(project) == ()
    assert (exclude.read_text(encoding="utf-8") if exclude.exists() else "") == before


def test_a_project_that_is_its_own_repository_keeps_its_records_out_of_it(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert gitstate.own_exclude(tmp_path) == (tmp_path / ".git/info/exclude").resolve()
    assert state.ensure_local_exclude(tmp_path) == state.LOCAL_ONLY_PATHS
