"""Reproduce the missed language capture and session-free startup boundaries."""

import pytest

from core.result import Ok
from harness import onboarding, preferences, startup, state, work_sessions
from tests.harness.test_discovery_render import prepare


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    return prepare(tmp_path / "project")


def test_uncaptured_legacy_language_does_not_stop_structured_startup(project):
    (project / preferences.LANGUAGE_STATE).unlink()
    preferences.path().unlink()
    state.write_json(
        project / ".harness/state/decision.json",
        {
            "id": "missed-language",
            "gate": "language",
            "status": "pending",
            "question": "Which language should this project use?",
            "options": ["English", "Português (Brasil)"],
            "answer": "",
            "transport": "blocking",
            "approval": False,
        },
    )
    assert isinstance(startup.begin(project, "Show both counts"), Ok)
    assert work_sessions.current(project) is not None
    assert preferences.language_for(project) == Ok("en")
    assert preferences.language_confirmed(project) == Ok(False)
    assert state.read_json(project / ".harness/state/decision.json")["answer"] == ""


def test_free_begin_without_configuration_creates_no_session(tmp_path):
    assert isinstance(onboarding.control(tmp_path, "mode", "free"), Ok)
    assert startup.begin(tmp_path, "Help refine this idea").value["state"] == "free"
    assert not work_sessions.root(tmp_path).exists()
    assert not (tmp_path / ".harness/settings.json").exists()


def test_free_begin_preserves_existing_work_selection(project):
    selected = startup.begin(project, "Show both counts").value["session_id"]
    assert isinstance(onboarding.control(project, "mode", "free"), Ok)
    assert startup.begin(project, "Explore an alternative").value["state"] == "free"
    assert work_sessions.current(project) == selected
    assert len(work_sessions.list_sessions(project).value) == 1
    assert isinstance(onboarding.control(project, "mode", "structured"), Ok)
    assert startup.begin(project, "Show both counts").value["session_id"] == selected
