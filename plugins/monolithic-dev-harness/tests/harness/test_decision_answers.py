"""A pending decision is answered only by an offered choice; the user's other commands still work."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness import decisions, questions, state, work_sessions
from host_adapters import work_session_context
from tests.harness.test_hook_security import HARNESS, run_hook
from tests.settings_fixture import write_settings


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    return tmp_path


def type_prompt(repo: Path, prompt: str, host: str = "codex", session: str = "") -> str:
    payload = {"prompt": prompt, **({"session_id": session} if session else {})}
    return run_hook(repo, "prompt", payload, host=host)


def chat_decision(
    repo: Path, session: str | None = None, approval: bool = False
) -> None:
    decisions.begin(
        repo,
        "d1",
        "Continue with this plan?",
        ("Continue", "Stop"),
        "chat",
        approval=approval,
        work_session_id=session,
    )


def test_other_messages_leave_the_decision_pending(repo: Path) -> None:
    chat_decision(repo)
    type_prompt(repo, "What does this plan change?")
    assert decisions.waiting(repo)
    type_prompt(repo, "continue.")
    assert (decisions.record(repo) or {}).get("answer") == "Continue"


def test_suspension_works_before_project_setup(tmp_path: Path) -> None:
    decisions.begin(tmp_path, "language", "Language?", ("English",), "async")
    type_prompt(tmp_path, "harness suspend")
    assert state.harness_mode(tmp_path) == "suspended"
    assert decisions.waiting(tmp_path)


def test_typed_choice_answers_async_question(repo: Path) -> None:
    decisions.begin(repo, "language", "Language?", ("English",), "async")
    type_prompt(repo, "english")
    assert (decisions.record(repo) or {}).get("answer") == "English"
    assert not decisions.waiting(repo)


def test_suspension_works_with_a_broken_conversation_link(repo: Path) -> None:
    work_session_context.bind_session(
        repo, "codex", "broken", work_sessions.start(repo, "DAY-001").value.id
    )
    next((repo / work_session_context.ROOT / "codex").glob("*.json")).write_text(
        "invalid"
    )
    type_prompt(repo, "harness suspend", session="broken")
    assert state.harness_mode(repo) == "suspended"


def test_revoke_suspend_and_typed_approvals_still_work(repo: Path) -> None:
    state.open_approval(repo, "HB-OPEN1", 20)
    chat_decision(repo)
    type_prompt(repo, "harness revoke")
    assert state.active_approval(repo) is None
    type_prompt(repo, "approve HB-TYPED1")
    assert state.active_approval(repo) is not None
    type_prompt(repo, "harness suspend")
    assert state.harness_mode(repo) == "suspended"
    assert decisions.waiting(repo)


def test_cursor_answers_the_one_pending_session_decision(repo: Path) -> None:
    session = work_sessions.start(repo, "DAY-001").value.id
    chat_decision(repo, session)
    type_prompt(repo, "Continue", host="cursor")
    assert (decisions.record(repo, session) or {}).get("answer") == "Continue"


def test_an_approval_covers_the_conversation_that_gave_it(repo: Path) -> None:
    session = work_sessions.start(repo, "DAY-001").value.id
    work_session_context.bind_session(repo, "codex", "native-a", session)
    decisions.begin(
        repo,
        "d1",
        "Publish these items?",
        ("Approve", "Not now"),
        "chat",
        approval=True,
    )
    type_prompt(repo, "Approve", session="native-a")
    assert state.active_approval(repo, session) is not None
    assert state.active_approval(repo) is None


def test_a_wordy_chat_approval_is_refused(repo: Path) -> None:
    result = subprocess.run(
        [
            str(HARNESS),
            "decision",
            "present",
            "--repo",
            str(repo),
            "--host",
            "codex",
            "--approval",
            "--question",
            "Should I edit lib/main.dart and lib/other.dart, and also rename "
            "`FooBarService` in the tracker?",
            "--option",
            "Approve",
            "--option",
            "Not now",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert not decisions.waiting(repo)


ROUTES = ("Start feature work (Recommended)", "Prepare work items", "Explore an idea")


@pytest.mark.parametrize(
    ("reply", "chosen"),
    [
        ("feature", 0),
        ("Start feature work", 0),
        ("1", 0),
        ("option 2", 1),
        ("the first", 0),
        ("3.", 2),
        ("**Explore an idea**", 2),
        ("last", 2),
    ],
)
def test_loose_replies_name_one_option(reply: str, chosen: int) -> None:
    assert questions.match_option(reply, ROUTES) == ROUTES[chosen]


@pytest.mark.parametrize("reply", ["work", "what are the choices", "", "4"])
def test_ambiguous_or_unrelated_replies_name_nothing(reply: str) -> None:
    assert questions.match_option(reply, ROUTES) is None


def test_accents_and_ampersands_do_not_matter() -> None:
    assert questions.match_option("portugues", ("English", "Português (Brasil)")) == (
        "Português (Brasil)"
    )
    assert questions.match_option(
        "Approve & continue", ("Approve and continue", "Deepen")
    ) == ("Approve and continue")


def test_a_loose_reply_never_approves_on_the_users_behalf() -> None:
    gate = ("Approve and continue", "Deepen", "Approve and stop")
    assert questions.match_option("stop", gate) is None
    assert questions.match_option("continue", gate) is None
    assert questions.match_option("approve and stop", gate) == "Approve and stop"
    assert questions.match_option("3", gate) == "Approve and stop"


def test_a_numbered_reply_answers_a_chat_question(repo: Path) -> None:
    decisions.begin(
        repo, "d1", "Which conflict policy?", ("Latest wins", "Ask"), "chat"
    )
    type_prompt(repo, "the first")
    assert (decisions.record(repo) or {}).get("answer") == "Latest wins"


def test_typing_after_a_dismissed_picker_answers_it(repo: Path) -> None:
    decisions.begin(repo, "d1", "Next step?", ROUTES, "blocking")
    type_prompt(repo, "feature", host="claude")
    assert (decisions.record(repo) or {}).get("answer") == ROUTES[0]
