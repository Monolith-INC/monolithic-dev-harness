"""The test-project fixture: a fresh copy in the checkout's `temp/`, with a release candidate's
own installer run for that copy only."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY))

from core.result import Err, Ok  # noqa: E402
from tools import project_fixture  # noqa: E402


@pytest.fixture
def trials(tmp_path, monkeypatch):
    folder = tmp_path / "temp"
    monkeypatch.setattr(project_fixture, "TRIALS", folder)
    return folder


def test_copy_lands_in_the_next_numbered_folder_under_temp(trials):
    (trials / "test-001").mkdir(parents=True)

    project = project_fixture.copy_template()

    assert project == trials / "test-002"
    assert (project / "backlog" / "DAY-001-task-counts.md").is_file()
    assert not (project / ".harness").exists()
    log = subprocess.run(
        ["git", "log", "--format=%s"], cwd=project, capture_output=True, text=True
    )
    assert log.stdout.strip() == "Starting project"


def test_newest_candidate_skips_finals_and_drafts():
    releases = [
        {"tag_name": "v0.7.0-rc.12", "prerelease": True, "draft": True},
        {"tag_name": "v0.6.0", "prerelease": False},
        {"tag_name": "v0.7.0-rc.11", "prerelease": True},
        {"tag_name": "v0.7.0-rc.10", "prerelease": True},
    ]

    assert project_fixture.latest_candidate(releases) == "0.7.0-rc.11"
    assert project_fixture.latest_candidate([{"tag_name": "v1.0.0"}]) is None


def test_installs_the_release_installer_for_the_copy_only(
    trials, tmp_path, monkeypatch
):
    installer = tmp_path / "install.sh"
    installer.write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setattr(
        project_fixture,
        "_github",
        lambda path: '[{"tag_name": "v0.7.0-rc.11", "prerelease": true}]',
    )
    monkeypatch.setattr(
        project_fixture, "_download_installer", lambda version: Ok(installer)
    )
    calls = []
    real_run = subprocess.run

    def run(command, **options):
        match command:
            case ["bash", *_]:
                calls.append(command)
                return subprocess.CompletedProcess(command, 0)
            case _:
                return real_run(command, **options)

    monkeypatch.setattr(project_fixture.subprocess, "run", run)

    result = project_fixture.create_test_project(hosts=("claude", "codex"))

    assert isinstance(result, Ok)
    project = result.value
    assert project.parent == trials
    assert [command[command.index("--host") + 1] for command in calls] == [
        "claude",
        "codex",
    ]
    for command in calls:
        assert command[1] == str(installer)
        assert command[command.index("--scope") + 1] == "local"
        assert command[command.index("--project") + 1] == str(project)
        assert command[command.index("--version") + 1] == "0.7.0-rc.11"


def test_a_given_version_is_installed_without_a_lookup(monkeypatch):
    monkeypatch.setattr(
        project_fixture, "_github", lambda path: pytest.fail("looked up releases")
    )

    assert project_fixture._version("v0.7.0-rc.9") == Ok("0.7.0-rc.9")


def test_no_candidate_asks_for_a_version(monkeypatch):
    monkeypatch.setattr(project_fixture, "_github", lambda path: "[]")

    result = project_fixture.create_test_project()

    assert isinstance(result, Err)
    assert result.failure.code == "no_candidate"


def test_a_failed_install_names_its_log(trials, tmp_path, monkeypatch):
    monkeypatch.setattr(
        project_fixture,
        "_download_installer",
        lambda version: Ok(tmp_path / "install.sh"),
    )
    real_run = subprocess.run
    monkeypatch.setattr(
        project_fixture.subprocess,
        "run",
        lambda command, **options: (
            subprocess.CompletedProcess(command, 1)
            if command[0] == "bash"
            else real_run(command, **options)
        ),
    )

    result = project_fixture.create_test_project(
        version="0.7.0-rc.11", hosts=("codex",)
    )

    assert isinstance(result, Err)
    assert result.failure.code == "install_failed"
    assert "test-001-install.log" in result.failure.message
