"""Runtime snapshots resolve real context and remain pinned across resume and upgrades."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from core.result import Err, Ok
from harness import bmad, discovery, preferences, work_sessions, workflow

PLUGIN = Path(__file__).resolve().parents[2]
CLI = PLUGIN / "scripts/harness/cli.py"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    return prepare(tmp_path / "project with spaces")


def prepare(repo: Path) -> Path:
    (repo / ".harness").mkdir(parents=True)
    (repo / ".harness/settings.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "tracker": {"name": "local"},
                "scm": {"name": "local"},
                "branch_template": "{key}-{slug}",
                "artifacts_path": "docs/planning",
            }
        )
    )
    from harness import setup

    assert isinstance(setup.prepare_local_tracker(repo), Ok)
    assert isinstance(bmad.prepare(repo, "docs/planning"), Ok)
    assert isinstance(preferences.set_language("en", repo), Ok)
    assert not (repo / ".harness/state/work_sessions").exists()
    return repo


def session(repo: Path, request: str = "Show both counts") -> work_sessions.Session:
    return started(repo, work_sessions.start(repo, request).value)


def started(repo: Path, selected: work_sessions.Session) -> work_sessions.Session:
    assert isinstance(
        workflow.save(repo, workflow.start(selected.request, "en").value, selected.id),
        Ok,
    )
    return selected


def cli(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args, "--repo", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
        env=os.environ.copy(),
    )


def test_resolves_context_absolute_links_and_commands(project: Path) -> None:
    check_resolved(project, session(project))


def check_resolved(project: Path, selected: work_sessions.Session) -> None:
    check_package(project, selected, discovery.render(project, selected.id).value)


def check_package(
    project: Path, selected: work_sessions.Session, package: dict
) -> None:
    entry = Path(package["entry"])
    text = entry.read_text()
    manifest = json.loads((entry.parent / "manifest.json").read_text())
    assert selected.id in text and selected.request in text
    assert str(project.resolve()) in text
    assert str(entry.parent / "step-01-clarify-and-route.md") in text
    assert str(project / "docs/planning") in text
    assert "{{" not in text and "{%" not in text and "{project-root}" not in text
    assert "route_selection" not in text
    memlog = project.resolve() / "_bmad/scripts/memlog.py"
    assert str(memlog) in text and memlog.is_file()
    plan_step = (entry.parent / "step-02-plan.md").read_text()
    assert "2. **Deepen**" in plan_step and "Never ask them one at a time" in plan_step
    assert shlex.split(package["context"]["status_command"])[-2:] == [
        "--session-id",
        selected.id,
    ]
    assert manifest["inputs"]["source_sha256"] and manifest["outputs"]["workflow.md"]
    assert (selected.folder / discovery.PIN).is_file()
    assert not (project / ".harness/state/workflow.json").exists()
    assert discovery.verify(project, selected.id).value == package


def test_same_session_reuses_pin_without_renderer(project: Path) -> None:
    check_reuse(project, session(project))


def check_reuse(project: Path, selected: work_sessions.Session) -> None:
    before = discovery.render(project, selected.id)
    with patch.object(
        discovery, "_invoke", side_effect=AssertionError("must not rerender")
    ):
        assert discovery.render(project, selected.id) == before


def test_different_sessions_get_different_snapshots(project: Path) -> None:
    assert (
        discovery.render(project, session(project, "First request").id).value["entry"]
        != discovery.render(project, session(project, "Second request").id).value[
            "entry"
        ]
    )


@pytest.mark.parametrize("damage", ["edit", "delete", "manifest"])
def test_corruption_is_refused_without_repair(project: Path, damage: str) -> None:
    corrupt_and_check(project, session(project), damage)


def corrupt_and_check(
    project: Path, selected: work_sessions.Session, damage: str
) -> None:
    package = discovery.render(project, selected.id).value
    match damage:
        case "edit":
            Path(package["entry"]).write_text("changed")
        case "delete":
            Path(package["entry"]).unlink()
        case "manifest":
            (Path(package["entry"]).parent / "manifest.json").write_text("{}")
    assert isinstance(discovery.render(project, selected.id), Err)
    assert isinstance(discovery.verify(project, selected.id), Err)
    assert json.loads((selected.folder / discovery.PIN).read_text()) == package


def test_changed_setup_is_not_silently_rerendered(project: Path) -> None:
    change_language(project, session(project))


def change_language(project: Path, selected: work_sessions.Session) -> None:
    assert isinstance(discovery.render(project, selected.id), Ok)
    assert isinstance(preferences.set_language("pt-br", project), Ok)
    assert (
        discovery.render(project, selected.id).failure.code
        == "discovery_snapshot_changed"
    )


@pytest.mark.parametrize(
    "operation",
    ["start", "render", "checkpoint", "back", "pause", "resume", "cancel", "complete"],
)
def test_cli_refuses_missing_session_before_any_workflow_write(
    project: Path, operation: str
) -> None:
    assert "--session-id" in cli(project, "workflow", operation).stderr
    assert not (project / ".harness/state/workflow.json").exists()


def test_no_setup_or_unconfirmed_language_prevents_render(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    tmp_path.mkdir(exist_ok=True)
    check_no_setup(tmp_path, session(tmp_path))


def check_no_setup(project: Path, selected: work_sessions.Session) -> None:
    assert (
        discovery.render(project, selected.id).failure.code == "onboarding_incomplete"
    )
    assert not (selected.folder / discovery.PIN).exists()
    assert not (project / "_bmad/render").exists()


def test_unknown_session_never_creates_snapshot(project: Path) -> None:
    assert isinstance(discovery.render(project, "WS-MISSING"), Err)
    assert not (project / "_bmad/render").exists()


def test_cli_resume_verifies_snapshot_before_changing_workflow(project: Path) -> None:
    check_resume(project, session(project))


def check_resume(project: Path, selected: work_sessions.Session) -> None:
    package = discovery.render(project, selected.id).value
    assert (
        cli(project, "workflow", "pause", "--session-id", selected.id).returncode == 0
    )
    Path(package["entry"]).write_text("changed")
    assert (
        cli(project, "workflow", "resume", "--session-id", selected.id).returncode != 0
    )
    assert workflow.load(project, selected.id).value.status == "paused"


def test_broken_template_fails_before_pin_publication(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "bad-skill").mkdir()
    (tmp_path / "bad-skill/workflow.md").write_text('{{ rendered("missing.md") }}')
    monkeypatch.setattr(discovery, "SKILL", tmp_path / "bad-skill")
    check_bad_template(project, session(project))


def check_bad_template(project: Path, selected: work_sessions.Session) -> None:
    assert isinstance(discovery.render(project, selected.id), Err)
    assert not (selected.folder / discovery.PIN).exists()


def test_cli_render_returns_verified_entry(project: Path) -> None:
    check_cli_render(project, session(project))


def check_cli_render(project: Path, selected: work_sessions.Session) -> None:
    done = cli(
        project,
        "workflow",
        "render",
        "--stage",
        "discover",
        "--session-id",
        selected.id,
    )
    assert done.returncode == 0, done.stderr
    assert Path(json.loads(done.stdout)["entry"]).is_file()


def test_onboarding_repairs_runtime_without_work_session(project: Path) -> None:
    (project / "_bmad/scripts/resolve_config.py").unlink()
    assert not bmad.ready(project)
    assert (
        cli(project, "work-session", "start", "--request", "Count tasks").returncode
        != 0
    )
    assert not (project / ".harness/state/work_sessions").exists()
    assert cli(project, "bootstrap", "--prepare-runtime").returncode == 0
    assert bmad.ready(project)
    assert not (project / ".harness/state/work_sessions").exists()
    assert (
        cli(project, "work-session", "start", "--request", "Count tasks").returncode
        == 0
    )


def test_unconfirmed_project_language_blocks_session(project: Path) -> None:
    (project / preferences.LANGUAGE_STATE).unlink()
    assert preferences.language().value == "en"
    assert (
        cli(project, "work-session", "start", "--request", "Count tasks").returncode
        != 0
    )
    assert not (project / ".harness/state/work_sessions").exists()


def test_changed_bmad_configuration_preserves_pin(project: Path) -> None:
    check_config_change(project, session(project))


def check_config_change(project: Path, selected: work_sessions.Session) -> None:
    before = discovery.render(project, selected.id).value
    (project / "_bmad/custom/config.user.toml").write_text(
        '[core]\nuser_name = "Changed"\n'
    )
    assert (
        discovery.render(project, selected.id).failure.code
        == "discovery_snapshot_changed"
    )
    assert json.loads((selected.folder / discovery.PIN).read_text()) == before


def test_project_session_resume_refuses_changed_snapshot(project: Path) -> None:
    check_session_resume(project, session(project))


def check_session_resume(project: Path, selected: work_sessions.Session) -> None:
    package = discovery.render(project, selected.id).value
    assert cli(project, "work-session", "pause", selected.id).returncode == 0
    Path(package["entry"]).write_text("changed")
    assert cli(project, "work-session", "resume", selected.id).returncode != 0
    assert work_sessions.select(project, selected.id).value.status == "paused"


def test_plugin_template_upgrade_keeps_existing_pin(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    check_upgrade(project, session(project), tmp_path, monkeypatch)


def check_upgrade(
    project: Path,
    selected: work_sessions.Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = discovery.render(project, selected.id)
    monkeypatch.setattr(discovery, "SKILL", tmp_path / "upgraded-plugin")
    monkeypatch.setattr(discovery, "DRIVER", tmp_path / "upgraded-renderer")
    assert discovery.render(project, selected.id) == before
    assert discovery.verify(project, selected.id) == before


def test_undeclared_override_is_rejected_before_publication(project: Path) -> None:
    (project / "_bmad/custom/bmad-build.user.toml").write_text(
        '[workflow]\nmisspelled_option = "value"\n'
    )
    check_bad_template(project, session(project))
    assert not (project / "_bmad/render/bmad-build").exists()


def test_cli_rejects_unknown_render_options(project: Path) -> None:
    assert (
        cli(
            project,
            "workflow",
            "render",
            "--stage",
            "discover",
            "--sessoin-id",
            "WS-MISSING",
        ).returncode
        != 0
    )
    assert not (project / "_bmad/render").exists()


def change_settings(project: Path) -> None:
    settings = json.loads((project / ".harness/settings.json").read_text())
    settings["approvals"] = {"window_minutes": 30}
    (project / ".harness/settings.json").write_text(json.dumps(settings))


def test_a_changed_setup_renders_the_same_steps_again(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = session(project)
    before = discovery.render(project, selected.id).value
    change_settings(project)
    # The same interpreter under another path, as after installing a newer Python.
    current = Path(sys.executable)
    monkeypatch.setattr(
        discovery.sys, "executable", f"{current.parent}/./{current.name}"
    )
    after = discovery.render(project, selected.id).value
    assert after["entry"] != before["entry"]
    assert Path(before["entry"]).is_file()
    assert {"settings_sha256", "python_command"} <= set(after["refreshed"]["changed"])
    assert discovery.verify(project, selected.id).value["entry"] == after["entry"]


def test_changed_steps_keep_the_run_on_its_snapshot(
    project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = session(project)
    before = discovery.render(project, selected.id).value
    upgraded = tmp_path / "upgraded-skill"
    import shutil

    shutil.copytree(discovery.SKILL, upgraded)
    step = upgraded / "step-02-plan.md"
    step.write_text(step.read_text() + "\nA new rule.\n")
    monkeypatch.setattr(discovery, "SKILL", upgraded)
    change_settings(project)
    result = discovery.render(project, selected.id)
    assert result.failure.code == "discovery_snapshot_changed"
    assert "steps changed" in result.failure.message
    assert json.loads((selected.folder / discovery.PIN).read_text()) == before
