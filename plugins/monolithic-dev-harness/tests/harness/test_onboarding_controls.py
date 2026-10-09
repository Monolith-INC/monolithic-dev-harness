"""Sessionless controls never release hard decisions or governance checks."""

import json
import subprocess
from pathlib import Path

import pytest

from core.result import Err, Failure, Ok
from harness import cli, decisions, hook, onboarding, rules, state, work_sessions
from tests.settings_fixture import write_settings

HARNESS = Path(__file__).resolve().parents[2] / "bin/harness"
CONTROLS = (
    ("onboarding", "status"),
    ("onboarding", "skip"),
    ("onboarding", "dismiss"),
    ("onboarding", "restart"),
    ("mode", "status"),
    ("mode", "free"),
    ("mode", "structured"),
)


def _pending(repo, kind):
    return decisions.begin(
        repo,
        "HD-onboarding",
        "Which language?",
        ("English", "Portuguese"),
        "chat",
        approval=kind == "approval",
        kind=kind,
    )


def _call(repo, command):
    return rules.make_call(
        "Bash", {"command": command}, cwd=str(repo), kind="shell", command=command
    )


@pytest.mark.parametrize("family,operation", CONTROLS)
def test_controls_without_settings_or_sessions(tmp_path, capsys, family, operation):
    assert cli.main([family, operation, "--repo", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] in ("free", "structured")
    assert work_sessions.list_sessions(tmp_path) == Ok(())
    assert not (tmp_path / ".harness/settings.json").exists()
    assert not (tmp_path / ".harness/state/suspension.json").exists()
    assert not (tmp_path / ".harness/state/workflow.json").exists()


@pytest.mark.parametrize("operation", ("skip", "dismiss", "free"))
def test_optional_pending_is_dismissed_without_an_answer(tmp_path, operation):
    assert isinstance(_pending(tmp_path, "preference"), Ok)
    assert isinstance(
        onboarding.control(
            tmp_path,
            {"free": "mode"}.get(operation, "onboarding"),
            operation,
        ),
        Ok,
    )
    assert onboarding.mode(tmp_path) == "free"
    assert decisions.record(tmp_path)["status"] == "dismissed"
    assert not decisions.record(tmp_path).get("answer")
    assert (
        state.read_json(
            tmp_path / decisions.RELATIVE_PATH.with_name(decisions.HISTORY)
        )["answers"][-1]["status"]
        == "dismissed"
    )
    assert not decisions.blocking(tmp_path, None)
    assert work_sessions.list_sessions(tmp_path) == Ok(())


@pytest.mark.parametrize("kind", ("required", "approval"))
@pytest.mark.parametrize("family,operation", CONTROLS)
def test_hard_pending_controls_preserve_decision(tmp_path, kind, family, operation):
    assert isinstance(_pending(tmp_path, kind), Ok)
    match (tmp_path / decisions.RELATIVE_PATH).read_bytes():
        case original:
            assert onboarding.recovery_command(
                f"{HARNESS} {family} {operation} --repo {tmp_path}", tmp_path, tmp_path
            )
            assert (
                hook._held(
                    tmp_path,
                    _call(
                        tmp_path, f"{HARNESS} {family} {operation} --repo {tmp_path}"
                    ),
                    Ok(None),
                    None,
                )
                is None
            )
            assert isinstance(onboarding.control(tmp_path, family, operation), Ok)
            assert (tmp_path / decisions.RELATIVE_PATH).read_bytes() == original
    assert decisions.blocking(tmp_path, None)
    assert (
        hook._held(tmp_path, _call(tmp_path, "touch result.txt"), Ok(None), None).rule
        == "decision-pending"
    )
    assert not (tmp_path / ".harness/state/approvals").exists()
    assert work_sessions.list_sessions(tmp_path) == Ok(())


@pytest.mark.parametrize(
    "suffix",
    (
        "; touch result.txt",
        " && touch result.txt",
        " | cat",
        " > result.txt",
        " $(touch result.txt)",
        " --session-id WS-other",
        " --answer English",
        " --repo /tmp",
        "\ntouch result.txt",
    ),
)
def test_recovery_rejects_compounds_and_extra_options(tmp_path, suffix):
    assert isinstance(_pending(tmp_path, "approval"), Ok)
    assert not onboarding.recovery_command(
        f"{HARNESS} mode free --repo {tmp_path}{suffix}", tmp_path, tmp_path
    )
    assert (
        hook._held(
            tmp_path,
            _call(tmp_path, f"{HARNESS} mode free --repo {tmp_path}{suffix}"),
            Ok(None),
            None,
        )
        is not None
    )


@pytest.mark.parametrize(
    "value",
    (
        {},
        {"mode": "free"},
        {"mode": "free", "status": "nonsense"},
        {"mode": "unknown", "status": "pending"},
        ["free"],
    ),
)
def test_malformed_state_defaults_structured(tmp_path, value):
    (tmp_path / onboarding.RELATIVE_PATH).parent.mkdir(parents=True)
    (tmp_path / onboarding.RELATIVE_PATH).write_text(json.dumps(value))
    assert onboarding.mode(tmp_path) == "structured"


def test_absent_and_broken_state_default_structured(tmp_path):
    assert onboarding.mode(tmp_path) == "structured"
    assert not (tmp_path / onboarding.RELATIVE_PATH).exists()
    (tmp_path / onboarding.RELATIVE_PATH).parent.mkdir(parents=True)
    (tmp_path / onboarding.RELATIVE_PATH).write_text("broken JSON")
    assert onboarding.mode(tmp_path) == "structured"


def test_restart_resets_only_onboarding(tmp_path):
    state.write_json(
        tmp_path / onboarding.RELATIVE_PATH,
        {"mode": "free", "status": "dismissed", "extra": "old step"},
    )
    state.write_json(tmp_path / ".harness/state/suspension.json", {"mode": "suspended"})
    assert isinstance(_pending(tmp_path, "approval"), Ok)
    assert isinstance(onboarding.control(tmp_path, "onboarding", "restart"), Ok)
    assert state.read_json(tmp_path / onboarding.RELATIVE_PATH) == {
        "mode": "structured",
        "status": "pending",
    }
    assert state.harness_mode(tmp_path) == "suspended"
    assert decisions.blocking(tmp_path, None)


def test_free_payload_is_sessionless(tmp_path):
    assert isinstance(onboarding.control(tmp_path, "mode", "free"), Ok)
    assert onboarding.free_payload(tmp_path, "Explain this code")["session_id"] is None
    assert "without creating" in onboarding.guidance(tmp_path)
    assert work_sessions.list_sessions(tmp_path) == Ok(())


def test_recovery_does_not_need_a_valid_session_context(tmp_path):
    assert (
        hook._held(
            tmp_path,
            _call(tmp_path, f"{HARNESS} onboarding restart --repo {tmp_path}"),
            Err(Failure("bad_session", "broken link")),
            None,
        )
        is None
    )


def test_other_repo_and_fake_executable_are_not_recovery(tmp_path):
    assert not onboarding.recovery_command(
        f"{HARNESS} mode free --repo /other", tmp_path, tmp_path
    )
    assert not onboarding.recovery_command("echo harness mode free", tmp_path, tmp_path)


def test_recovery_runs_governance(tmp_path, monkeypatch, capsys):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    assert isinstance(_pending(tmp_path, "approval"), Ok)
    monkeypatch.setattr(
        rules,
        "evaluate",
        lambda *_: rules.Decision.deny("test-governance", "still enforced"),
    )
    assert (
        hook.handle_pre_tool(
            "codex",
            "pre-tool",
            {
                "cwd": str(tmp_path),
                "tool_name": "Bash",
                "tool_input": {"command": f"{HARNESS} mode free --repo {tmp_path}"},
            },
        )
        == 0
    )
    assert "test-governance" in capsys.readouterr().out
    assert onboarding.mode(tmp_path) == "structured"


def test_optional_dismissal_failure_does_not_claim_free(tmp_path, monkeypatch):
    assert isinstance(_pending(tmp_path, "preference"), Ok)
    monkeypatch.setattr(
        decisions,
        "dismiss_optional",
        lambda *_args, **_kw: Err(Failure("decision_invalid", "storage unavailable")),
    )
    assert isinstance(onboarding.control(tmp_path, "mode", "free"), Err)
    assert onboarding.mode(tmp_path) == "structured"


@pytest.mark.parametrize("kind", ("required", "approval"))
def test_cli_free_with_hard_pending_keeps_native_hook_blocked(tmp_path, capsys, kind):
    from tests.harness.test_hook_security import bash

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_settings(tmp_path)
    assert isinstance(_pending(tmp_path, kind), Ok)
    match (tmp_path / decisions.RELATIVE_PATH).read_bytes():
        case original:
            assert "deny" not in bash(
                tmp_path, f"{HARNESS} mode free --repo {tmp_path}"
            )
            assert cli.main(["mode", "free", "--repo", str(tmp_path)]) == 0
            assert json.loads(capsys.readouterr().out)["mode"] == "free"
            assert (tmp_path / decisions.RELATIVE_PATH).read_bytes() == original
    assert "decision-pending" in bash(tmp_path, "touch escaped.txt")
    assert work_sessions.list_sessions(tmp_path) == Ok(())
    assert not (tmp_path / ".harness/state/approvals").exists()


@pytest.mark.parametrize("family,operation", CONTROLS)
def test_all_controls_with_pending_preference(tmp_path, family, operation):
    assert isinstance(_pending(tmp_path, "preference"), Ok)
    assert (
        hook._held(
            tmp_path,
            _call(tmp_path, f"{HARNESS} {family} {operation} --repo {tmp_path}"),
            Ok(None),
            None,
        )
        is None
    )
    assert isinstance(onboarding.control(tmp_path, family, operation), Ok)
    assert not decisions.record(tmp_path).get("answer")
    assert work_sessions.list_sessions(tmp_path) == Ok(())


def test_free_startup_without_settings_needs_no_structured_dependencies(
    tmp_path, monkeypatch
):
    from harness import startup

    assert isinstance(onboarding.control(tmp_path, "mode", "free"), Ok)
    monkeypatch.setattr(
        startup.setup,
        "onboarding_status",
        lambda *_: pytest.fail("free startup must not inspect setup"),
    )
    monkeypatch.setattr(
        work_sessions,
        "route",
        lambda *_: pytest.fail("free startup must not route a session"),
    )
    assert startup.begin(tmp_path, "Explain this code").value["state"] == "free"
    assert work_sessions.list_sessions(tmp_path) == Ok(())
    assert not (tmp_path / ".harness/settings.json").exists()


@pytest.mark.parametrize(
    "gate", ("language", "setup-confirm", "next-step", "starting-point")
)
@pytest.mark.parametrize("operation", ("skip", "dismiss", "restart"))
def test_onboarding_controls_cancel_only_the_abandoned_onboarding_question(
    tmp_path, gate, operation
):
    assert isinstance(
        decisions.begin(
            tmp_path, "HD-gate", "Continue?", ("Yes", "No"), "chat", gate=gate
        ),
        Ok,
    )
    assert isinstance(onboarding.control(tmp_path, "onboarding", operation), Ok)
    assert decisions.record(tmp_path)["status"] == "cancelled"
    assert decisions.record(tmp_path)["answer"] == ""
    assert not decisions.waiting(tmp_path)
    assert decisions.pending(tmp_path) is None
    assert state.active_approval(tmp_path) is None
    assert isinstance(
        decisions.begin(
            tmp_path, "HD-fresh", "A fresh question?", ("Continue", "Stop"), "chat"
        ),
        Ok,
    )


def test_onboarding_gate_cannot_disguise_an_approval(tmp_path):
    assert isinstance(
        decisions.begin(
            tmp_path,
            "HD-approval",
            "Approve?",
            ("Approve", "Reject"),
            "chat",
            gate="setup-confirm",
            approval=True,
            kind="preference",
        ),
        Ok,
    )
    assert isinstance(onboarding.control(tmp_path, "onboarding", "dismiss"), Ok)
    assert decisions.record(tmp_path)["status"] == "pending"
    assert decisions.waiting(tmp_path)


def test_cancelled_settings_proposal_cannot_be_applied(tmp_path):
    from harness import setup

    assert isinstance(
        decisions.begin(
            tmp_path,
            "HD-settings",
            "Use these settings?",
            ("Yes", "No"),
            "chat",
            gate="setup-confirm",
        ),
        Ok,
    )
    assert isinstance(onboarding.control(tmp_path, "onboarding", "dismiss"), Ok)
    assert (
        setup.apply(tmp_path, {}, "old-digest", "old-source").failure.code
        == "setup_cancelled"
    )
    assert not (tmp_path / ".harness/settings.json").exists()


def test_cancelled_setup_survives_unrelated_question_and_needs_exact_fresh_review(
    tmp_path,
):
    from harness import setup
    from tests.harness.test_decisions import native

    proposal = setup.review(
        tmp_path, tracker_name="local", artifacts_path="docs/planning"
    ).value
    assert isinstance(
        decisions.begin(
            tmp_path,
            "old-setup",
            "Use these settings?",
            ("Yes", "No"),
            "chat",
            gate="setup-confirm",
        ),
        Ok,
    )
    assert isinstance(onboarding.control(tmp_path, "onboarding", "dismiss"), Ok)
    assert isinstance(
        decisions.begin(
            tmp_path,
            "unrelated",
            "Which language?",
            ("English",),
            "chat",
            gate="language",
        ),
        Ok,
    )
    assert (
        setup.apply(
            tmp_path,
            proposal["candidate"],
            proposal["digest"],
            proposal["source_digest"],
        ).failure.code
        == "setup_cancelled"
    )
    assert not (tmp_path / ".harness/settings.json").exists()
    assert isinstance(
        setup.review(tmp_path, tracker_name="local", artifacts_path="docs/planning"), Ok
    )
    assert isinstance(
        decisions.begin(
            tmp_path,
            "fresh-setup",
            "Use these settings?",
            ("Yes", "No"),
            "chat",
            gate="setup-confirm",
        ),
        Ok,
    )
    native(tmp_path, "prompt", {"prompt": "Yes"})
    assert isinstance(
        decisions.begin(
            tmp_path,
            "after-confirmation",
            "Language?",
            ("English",),
            "chat",
            gate="language",
        ),
        Ok,
    )
    assert (
        setup.apply(
            tmp_path, proposal["candidate"], "different", proposal["source_digest"]
        ).failure.code
        == "setup_cancelled"
    )
    assert isinstance(
        setup.apply(
            tmp_path,
            proposal["candidate"],
            proposal["digest"],
            proposal["source_digest"],
        ),
        Ok,
    )


def test_skip_restart_and_repeated_dismissal_are_idempotent(tmp_path):
    assert isinstance(
        decisions.begin(
            tmp_path, "language", "Language?", ("English",), "chat", gate="language"
        ),
        Ok,
    )
    assert isinstance(onboarding.control(tmp_path, "onboarding", "skip"), Ok)
    assert isinstance(onboarding.control(tmp_path, "onboarding", "restart"), Ok)
    assert onboarding.mode(tmp_path) == "structured"
    assert isinstance(onboarding.control(tmp_path, "onboarding", "dismiss"), Ok)
    assert isinstance(onboarding.control(tmp_path, "onboarding", "dismiss"), Ok)
    assert onboarding.mode(tmp_path) == "free"
    assert decisions.record(tmp_path)["answer"] == ""


def test_cancel_completes_interrupted_checkpoint_before_changing_status(
    tmp_path, monkeypatch
):
    from harness import review_decisions, workflow

    assert isinstance(
        workflow.save(tmp_path, workflow.start("Review setup", "en").value), Ok
    )
    original = state.write_json

    def fail_workflow(path, value):
        match path.name:
            case "workflow.json":
                raise OSError("interrupted projection")
            case _:
                return original(path, value)

    with monkeypatch.context() as fault:
        fault.setattr(state, "write_json", fail_workflow)
        assert isinstance(
            review_decisions.begin(
                tmp_path,
                "setup",
                "Use these settings?",
                ("Yes", "No"),
                "chat",
                (("plan.md", "digest"),),
                gate="setup-confirm",
            ),
            Err,
        )
        assert isinstance(onboarding.control(tmp_path, "onboarding", "restart"), Err)
        assert decisions.record(tmp_path)["status"] == "pending"
    assert isinstance(onboarding.control(tmp_path, "onboarding", "restart"), Ok)
    assert decisions.record(tmp_path)["status"] == "cancelled"
    assert "review_checkpoint" not in decisions.record(tmp_path)
    assert len(workflow.load(tmp_path).value.points) == 1
    assert workflow.load(tmp_path).value.current.stage == "discovery"
    assert any(
        len((state.read_json(path) or {}).get("points", ())) == 2
        for path in (tmp_path / ".harness/state/workflows").glob("*.json")
    )
    assert isinstance(
        decisions.begin(tmp_path, "new", "Continue?", ("Yes", "No"), "chat"), Ok
    )
