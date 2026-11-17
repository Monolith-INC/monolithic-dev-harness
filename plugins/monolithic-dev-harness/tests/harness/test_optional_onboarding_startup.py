"""Reproduce the missed language capture and session-free startup boundaries."""

import pytest

from core.result import Ok
from harness import (
    onboarding,
    preferences,
    session_entry,
    startup,
    state,
    work_sessions,
)
from tests.harness.test_discovery_render import prepare


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "preferences"))
    return prepare(tmp_path / "project")


def choose_saved_work(project, conversation, session_id):
    host = "codex"
    prepared = session_entry.current_offer(project, host, conversation).value
    key = f"continue:{session_id}"
    index = next(i for i, option in enumerate(prepared.options) if option.key == key)
    question = session_entry.question(prepared, "en")
    payload = {
        "session_id": conversation,
        "tool_use_id": "post-free-saved-work-choice",
        "tool_name": "request_user_input",
        "tool_input": {"questions": [question]},
    }
    assert session_entry.observe(project, host, payload).value
    assert (
        session_entry.answer(
            project,
            host,
            {
                **payload,
                "tool_response": {
                    "answers": {
                        question["question"]: question["options"][index]["label"]
                    }
                },
            },
        ).value
        == key
    )
    return session_entry.apply_selection(project, host, conversation)


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
    conversation = "post-free-thread"
    menu = startup.begin(
        project, "Show both counts", host="codex", conversation=conversation
    )
    assert isinstance(menu, Ok) and menu.value["state"] == "choose_session"
    assert choose_saved_work(project, conversation, selected).value == selected
    assert (
        startup.begin(
            project,
            "Show both counts",
            host="codex",
            conversation=conversation,
        ).value["session_id"]
        == selected
    )
