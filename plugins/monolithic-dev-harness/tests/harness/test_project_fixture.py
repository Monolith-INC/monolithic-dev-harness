"""The test-project fixture: fresh copies, an isolated install, and headless runs that stop at
each question and resume with the human's reply."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(REPOSITORY / "scripts"))

import acceptance_trial  # noqa: E402

from core.result import Err, Ok  # noqa: E402
from tools import project_fixture  # noqa: E402
from tools.project_fixture import (  # noqa: E402
    create_test_project,
    discard_test_project,
)


class ProjectFixtureTests(unittest.TestCase):
    def test_missing_configuration_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            result = create_test_project(Path(directory) / "missing.json")

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "missing_configuration")

    def test_invalid_json_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text("{", encoding="utf-8")

            result = create_test_project(configuration, hosts=())

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "invalid_configuration_json")

    def test_non_object_json_returns_error(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text("[]", encoding="utf-8")

            result = create_test_project(configuration, hosts=())

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "invalid_configuration")

    def test_schema_invalid_configuration_returns_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text(json.dumps({"tracker": {"name": "local"}}))

            result = create_test_project(configuration, hosts=())

        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "invalid_settings")

    def test_valid_configuration_creates_configured_copy_that_can_be_discarded(self):
        settings = {
            "schemaVersion": 1,
            "tracker": {"name": "local"},
            "scm": {"name": "local"},
            "branch_template": "{key}-{slug}",
            "artifacts_path": "docs/planning",
        }
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text(json.dumps(settings), encoding="utf-8")

            result = create_test_project(configuration, hosts=())

        self.assertIsInstance(result, Ok)
        project = result.value
        try:
            self.assertEqual(project.parent.parent, REPOSITORY / "temp")
            self.assertTrue(project.parent.name.startswith("test-"))
            applied = json.loads((project / ".harness/settings.json").read_text())
            self.assertEqual(applied, settings)
            self.assertTrue((project / "README.md").is_file())
            self.assertTrue((project / "_bmad/config.toml").is_file())
            self.assertTrue((project / "_bmad/scripts").is_dir())
            self.assertIn(
                "{project-root}/docs/planning",
                (project / "_bmad/custom/config.toml").read_text(),
            )
            self.assertTrue((project / "Tickets/Ready").is_dir())
        finally:
            discarded = discard_test_project(project)

        self.assertIsInstance(discarded, Ok)
        self.assertFalse(project.parent.exists())

    def test_new_fixture_removes_abandoned_test_run_copies(self):
        from acceptance_trial import MARKER_NAME, RUN_PREFIX, prepare

        abandoned = prepare(root_prefix=RUN_PREFIX, kind="run")
        marker_path = abandoned.parent / MARKER_NAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["process_id"] = 2**30
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        configuration = {
            "schemaVersion": 1,
            "tracker": {"name": "local"},
            "scm": {"name": "local"},
            "branch_template": "{key}-{slug}",
        }

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "settings.json"
            config_path.write_text(json.dumps(configuration), encoding="utf-8")
            result = create_test_project(config_path, hosts=())

        self.assertIsInstance(result, Ok)
        self.assertFalse(abandoned.parent.exists())
        discard_test_project(result.value)

    def test_each_call_returns_a_fresh_copy(self):
        settings = {
            "schemaVersion": 1,
            "tracker": {"name": "local"},
            "scm": {"name": "local"},
            "branch_template": "{key}-{slug}",
        }
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "settings.json"
            configuration.write_text(json.dumps(settings), encoding="utf-8")
            first = create_test_project(configuration, hosts=())
            second = create_test_project(configuration, hosts=())

        self.assertIsInstance(first, Ok)
        self.assertIsInstance(second, Ok)
        self.assertNotEqual(first.value, second.value)
        discard_test_project(first.value)
        discard_test_project(second.value)


# A stand-in `claude`: records its arguments, reports a session, and leaves a pending question
# on its first run, as the harness does when it waits for the human.
FAKE_CLAUDE = """#!/usr/bin/env python3
import json, sys
from pathlib import Path
log = Path.cwd().parent / "calls.jsonl"
with log.open("a") as out:
    out.write(json.dumps(sys.argv[1:]) + "\\n")
state = Path.cwd() / ".harness/state"
state.mkdir(parents=True, exist_ok=True)
decision = state / "decision.json"
if "--resume" in sys.argv:
    decision.write_text(json.dumps({"status": "answered"}))
    last = "Done."
else:
    decision.write_text(json.dumps({"id": "d1", "status": "pending",
        "question": "Use the local tracker?", "options": ["Yes", "No"]}))
    last = "Waiting for your choice."
print(json.dumps({"type": "system", "session_id": "s-1"}))
print(json.dumps({"type": "result", "result": last, "session_id": "s-1"}))
"""


@pytest.fixture
def copy(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    fake = tmp_path / "fake-bin"
    fake.mkdir()
    (fake / "claude").write_text(FAKE_CLAUDE)
    (fake / "claude").chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}:{Path(sys.executable).parent}:/usr/bin:/bin")
    project = acceptance_trial.prepare()
    yield project
    acceptance_trial.discard(str(project))


def test_a_headless_run_stops_at_the_question_and_resumes_with_the_reply(copy):
    started = project_fixture.start_run(copy, "claude", "Implement DAY-001.").value
    assert started["state"] == "waiting_for_human"
    assert started["question"]["question"] == "Use the local tracker?"
    assert started["session"] == "s-1"

    resumed = project_fixture.answer(copy, "Yes").value
    assert resumed["state"] == "finished"
    assert resumed["last_message"] == "Done."
    calls = [
        json.loads(line)
        for line in (copy.parent / "calls.jsonl").read_text().splitlines()
    ]
    assert calls[0][-1] == "Implement DAY-001."
    # The session goes to `--resume` as an option; only the reply follows the end of options.
    assert calls[1][calls[1].index("--resume") + 1 :] == ["s-1", "--", "Yes"]
    assert "bypassPermissions" not in calls[0]


def test_answer_without_a_run_is_refused(copy):
    assert project_fixture.answer(copy, "Yes").failure.code == "no_run"


def test_only_claude_and_codex_run_headless(copy):
    assert (
        project_fixture.start_run(copy, "zed", "x").failure.code
        == "unsupported_runtime"
    )


def test_install_puts_this_checkout_into_the_copy_for_each_host(copy, monkeypatch):
    calls = []

    def run(command, **options):
        calls.append((command, options["env"]))
        return type("Done", (), {"returncode": 0})()

    monkeypatch.setattr(project_fixture.subprocess, "run", run)
    assert isinstance(project_fixture.install(copy, None, ("claude", "codex")), Ok)
    (claude, environment), (codex, _) = calls
    assert claude[claude.index("--scope") + 1 : claude.index("--scope") + 4] == [
        "local",
        "--project",
        str(copy),
    ]
    assert claude[claude.index("--source") + 1] == str(project_fixture.REPOSITORY)
    assert codex[codex.index("--host") + 1] == "codex"
    trial = copy.parent
    assert environment["HARNESS_HOME"] == str(trial / "harness-install")
    assert environment["CODEX_HOME"] == str(trial / "codex-home")
    assert "trust_level" in (trial / "codex-home/config.toml").read_text()
