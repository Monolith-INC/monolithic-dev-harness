"""Preferences do not authorize writes or hold otherwise-ready work."""

import pytest

from core.result import Err, Ok
from harness import decisions, discovery, gates, preferences, state, work_lifecycle


@pytest.mark.parametrize(
    "record,blocking",
    [
        ({"gate": "language", "status": "pending"}, False),
        ({"status": "pending"}, True),
        ({"kind": "unknown", "status": "pending"}, True),
        ({"kind": "required", "status": "pending"}, True),
        ({"kind": "approval", "status": "pending"}, True),
        ({"kind": "preference", "approval": True, "status": "pending"}, True),
        ({"gate": "language", "approval": True, "status": "pending"}, True),
    ],
)
def test_classification(record, blocking):
    assert decisions.is_blocking(record) is blocking


def test_legacy_language_can_be_superseded_without_answer(tmp_path):
    state.write_json(
        tmp_path / decisions.RELATIVE_PATH,
        {
            "id": "old",
            "gate": "language",
            "status": "pending",
            "answer": "",
            "question": "Language?",
            "options": ["English"],
            "transport": "chat",
        },
    )
    assert not decisions.waiting(tmp_path)
    assert not decisions.any_waiting(tmp_path)
    assert decisions.pending(tmp_path).id == "old"
    assert isinstance(
        decisions.begin(tmp_path, "new", "Continue?", ("Continue",), "chat"), Ok
    )
    assert decisions.waiting(tmp_path)
    assert (
        state.read_json(tmp_path / decisions.RELATIVE_PATH.with_name(decisions.HISTORY))
        or {}
    )["answers"][-1]["status"] == "dismissed"
    assert (
        state.read_json(tmp_path / decisions.RELATIVE_PATH.with_name(decisions.HISTORY))
        or {}
    )["answers"][-1]["answer"] == ""
    assert state.active_approval(tmp_path) is None


@pytest.mark.parametrize(
    "kind,approval", [("required", False), ("approval", False), ("preference", True)]
)
def test_required_and_approval_cannot_be_dismissed(tmp_path, kind, approval):
    assert isinstance(
        decisions.begin(
            tmp_path,
            "d",
            "Continue?",
            ("Continue",),
            "chat",
            kind=kind,
            approval=approval,
        ),
        Ok,
    )
    assert decisions.waiting(tmp_path)
    assert isinstance(decisions.dismiss_optional(tmp_path), Err)
    assert decisions.record(tmp_path)["status"] == "pending"
    assert isinstance(
        decisions.begin(tmp_path, "next", "Next?", ("Next",), "chat"), Err
    )


def test_dismissal_preserves_evidence_and_is_not_reusable(tmp_path):
    assert isinstance(
        decisions.begin(
            tmp_path, "d", "Language?", ("English",), "chat", gate="language"
        ),
        Ok,
    )
    assert decisions.record(tmp_path)["kind"] == "preference"
    assert isinstance(decisions.dismiss_optional(tmp_path), Ok)
    assert decisions.record(tmp_path)["status"] == "dismissed"
    assert decisions.pending(tmp_path) is None
    assert (
        decisions.reusable(
            tmp_path, "Language?", ("English",), (), False, target=("item", "one")
        )
        is None
    )
    assert state.active_approval(tmp_path) is None


def test_language_default_and_saved_choices(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "user"))
    assert preferences.language_for(tmp_path) == Ok("en")
    assert preferences.language_confirmed(tmp_path) == Ok(False)
    assert isinstance(preferences.set_language("pt-br", tmp_path), Ok)
    assert preferences.language_for(tmp_path) == Ok("pt-br")
    assert preferences.language_confirmed(tmp_path) == Ok(True)
    assert preferences.language_for(tmp_path / "other") == Ok("pt-br")
    assert preferences.language_confirmed(tmp_path / "other") == Ok(False)


def test_catalog_kinds():
    assert gates.render("language", "en", {}).value.kind == "preference"
    assert gates.render("setup-confirm", "en", {}).value.kind == "required"
    assert (
        gates.render("publish-branch", "en", {"branch": "main"}).value.kind
        == "approval"
    )


def test_workflow_starts_without_language_capture(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "user"))
    monkeypatch.setattr(
        discovery.setup,
        "onboarding_status",
        lambda _: Ok(
            {
                "status": "ready",
                "language_confirmed": False,
                "waiting_for_answer": False,
                "bmad_ready": True,
            }
        ),
    )
    assert isinstance(discovery.onboarding_ready(tmp_path), Ok)
    assert (
        work_lifecycle.start_workflow(tmp_path, "Build a thing").value.language == "en"
    )
    assert preferences.language_confirmed(tmp_path) == Ok(False)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "incomplete"},
        {"bmad_ready": False},
        {"waiting_for_answer": True},
    ],
)
def test_real_readiness_requirements_remain(tmp_path, monkeypatch, changes):
    monkeypatch.setattr(
        discovery.setup,
        "onboarding_status",
        lambda _: Ok(
            {
                "status": "ready",
                "language_confirmed": False,
                "waiting_for_answer": False,
                "bmad_ready": True,
                **changes,
            }
        ),
    )
    assert isinstance(discovery.onboarding_ready(tmp_path), Err)


def test_hook_captured_language_is_used(tmp_path, monkeypatch):
    from tests.harness.test_decisions import native

    monkeypatch.setenv("HARNESS_USER_STATE_DIR", str(tmp_path / "user"))
    assert isinstance(
        decisions.begin(
            tmp_path,
            "language",
            "Language?",
            ("English", "Português (Brasil)"),
            "chat",
            gate="language",
        ),
        Ok,
    )
    assert preferences.language_confirmed(tmp_path) == Ok(False)
    assert not decisions.waiting(tmp_path)
    native(tmp_path, "prompt", {"prompt": "Português (Brasil)"})
    assert decisions.record(tmp_path)["status"] == "answered"
    assert preferences.language_for(tmp_path) == Ok("pt-br")
    assert preferences.language_confirmed(tmp_path) == Ok(True)


@pytest.mark.parametrize("kind", ["required", "approval", "unknown"])
def test_dismissed_required_state_fails_closed(tmp_path, kind):
    state.write_json(
        tmp_path / decisions.RELATIVE_PATH, {"kind": kind, "status": "dismissed"}
    )
    assert decisions.is_blocking(decisions.record(tmp_path))
    assert decisions.waiting(tmp_path)
    assert isinstance(decisions.dismiss_optional(tmp_path), Err)


def test_corrupt_saved_decision_cannot_be_dismissed(tmp_path):
    (tmp_path / decisions.RELATIVE_PATH).parent.mkdir(parents=True)
    (tmp_path / decisions.RELATIVE_PATH).write_text("{broken")
    assert decisions.waiting(tmp_path)
    assert isinstance(decisions.dismiss_optional(tmp_path), Err)
    assert (tmp_path / decisions.RELATIVE_PATH).read_text() == "{broken"
