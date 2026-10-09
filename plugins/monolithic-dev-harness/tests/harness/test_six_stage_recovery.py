"""Regression evidence for recovery boundaries from the interrupted live trial."""

import json
from pathlib import Path

from core.result import Ok
from harness import (
    cli,
    decisions,
    harness_controls,
    hook,
    onboarding,
    question_observation,
    rules,
    shellscan,
    startup,
    state,
    work_sessions,
    workflow,
)
from host_adapters import work_session_context
from policy.commands import is_code
from tests.harness.test_hook_security import HARNESS, run_hook
from tests.settings_fixture import write_settings


def test_literal_report_does_not_execute_its_backticked_commands() -> None:
    command = (
        "cat > result.md <<'EOF'\nUse `git push` and $(touch lib/main.dart) later.\nEOF"
    )
    assert [call.name for call in shellscan.invocations(command)] == ["cat"]
    assert [
        call.name for call in shellscan.invocations(command.replace("'EOF'", '"EOF"'))
    ] == ["cat"]
    assert any(
        call.name == "touch"
        for call in shellscan.invocations(command.replace("'EOF'", "EOF"))
    )
    assert any(
        call.name == "git"
        for call in shellscan.invocations("sh <<'EOF'\ngit push\nEOF")
    )


def test_quoted_argument_or_comment_cannot_hide_executable_substitution() -> None:
    for header in ("echo \" <<'EOF'\"", "echo ok # <<'EOF'"):
        assert any(
            call.name == "touch"
            for call in shellscan.invocations(header + "\n$(touch lib/main.dart)\nEOF")
        )

    assert any(
        call.name == "touch"
        for call in shellscan.invocations("((1 << 'EOF'))\n$(touch lib/main.dart)\nEOF")
    )


def test_evidence_data_is_not_source_but_explicit_source_patterns_win() -> None:
    assert not is_code(
        "docs/planning/acceptance-evidence/reply.jsonl", None, planning="docs/planning"
    )
    assert is_code(
        "docs/planning/acceptance-evidence/reply.jsonl",
        ["**/*.jsonl"],
        planning="docs/planning",
    )


def test_multiple_delimiters_and_carriage_returns_do_not_hide_execution() -> None:
    for command in (
        "cat <<A-B <<'EOF'\n\"$(git push origin HEAD)\"\nA-B\nsafe\nEOF",
        "cat <<FIRST <<'SECOND'\nFIRST\r\n\"$(git push origin HEAD)\"\nFIRST\nsafe\nSECOND",
        "cat <<$(echo) <<'SECOND'\n$\n\"$(git push origin HEAD)\"\n$(echo)\nsafe\nSECOND",
        "cat <<FIRST\r <<'SECOND'\nFIRST\n\"$(git push origin HEAD)\"\nFIRST\r\nsafe\nSECOND",
        "cat <<REAL # ((\n<<'FAKE'\n\"$(git push origin HEAD)\"\nFAKE\nREAL",
    ):
        assert shellscan.git_commands(command)
    assert is_code("docs/planning/source.json", None, planning="docs/planning")
    assert is_code(
        "docs/planning/acceptance-evidence/run.py", None, planning="docs/planning"
    )


def test_suspended_observation_preserves_foreign_answer_without_approving(
    tmp_path: Path,
) -> None:
    decisions.begin(tmp_path, "A", "Existing choice?", ("Continue", "Stop"), "blocking")
    question = {
        "questions": [
            {
                "id": "B",
                "question": "New choice?",
                "options": [{"label": "Continue", "description": "Move on"}],
            }
        ]
    }
    payload = {"tool_use_id": "B", "tool_input": question}
    assert isinstance(question_observation.ask(tmp_path, "codex", payload), Ok)
    assert isinstance(
        question_observation.answer(
            tmp_path,
            "codex",
            {**payload, "tool_response": {"answers": {"B": {"answers": ["Continue"]}}}},
        ),
        Ok,
    )
    observed = state.read_json(tmp_path / ".harness/state/question-observations/B.json")
    assert observed["answer"] == "Continue"
    assert observed["approval"] is False
    assert decisions.pending(tmp_path).id == "A"
    assert state.active_approval(tmp_path) is None


def test_lifecycle_presentations_are_isolated_between_conversations(
    tmp_path: Path,
) -> None:
    question = "How would you like to control the harness?"
    choices = ("Suspend harness", "Resume harness", "Free mode")
    harness_controls.stage_chat(tmp_path, "A", question, choices, "chat-a")
    assert harness_controls.waiting(tmp_path, "chat-a")
    assert not harness_controls.waiting(tmp_path, "chat-b")
    payload = {
        "session_id": "chat-b",
        "tool_use_id": "B",
        "tool_name": "functions.request_user_input",
        "tool_input": {
            "questions": [
                {
                    "id": "B",
                    "question": question,
                    "options": [{"label": label} for label in choices],
                }
            ]
        },
    }
    assert harness_controls.observe(tmp_path, "codex", payload)
    assert harness_controls.pending_native(tmp_path, "chat-b")

    assert harness_controls.prompt_operation(tmp_path, "1", "chat-a") == "suspend"
    harness_controls.prompt(tmp_path, "1", "chat-a")
    assert not harness_controls.waiting(tmp_path, "chat-a")
    assert harness_controls.pending_native(tmp_path, "chat-b")
    assert (
        harness_controls.answer(
            tmp_path,
            {
                **payload,
                "session_id": "chat-a",
                "tool_response": {"answers": {"B": {"answers": ["Suspend harness"]}}},
            },
        )
        is None
    )
    assert harness_controls.pending_native(tmp_path, "chat-b")


def test_agents_cannot_forge_control_or_observation_records(tmp_path: Path) -> None:
    for folder in ("control-questions", "question-observations"):
        path = tmp_path / ".harness/state" / folder / "fake.json"
        assert rules.is_human_owned(str(path.relative_to(tmp_path)))
        assert not rules.rule_human_owned(
            rules.ToolCall(kind="edit", name="edit", file_paths=(str(path),)), tmp_path
        ).allowed


def test_foreign_async_reply_is_evidence_not_an_older_decision(tmp_path: Path) -> None:
    decisions.begin(tmp_path, "A", "Existing choice?", ("Continue", "Stop"), "chat")
    question_observation.ask(
        tmp_path,
        "codex",
        {
            "tool_use_id": "B",
            "tool_name": "functions.request_user_input_async",
            "tool_input": {
                "questions": [{"title": "New choice?", "options": ["Continue", "Stop"]}]
            },
        },
    )
    assert question_observation.foreign_prompt(tmp_path, "A", "Continue")
    assert decisions.pending(tmp_path).id == "A"
    assert state.active_approval(tmp_path) is None
    assert (
        state.read_json(tmp_path / ".harness/state/question-observations/B.json")[
            "reply"
        ]
        == "Continue"
    )


def test_controls_cannot_target_another_project_or_repeat_repo(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / ".harness").mkdir()
    (second / ".harness").mkdir()
    monkeypatch.chdir(first)
    assert not onboarding.recovery_command(
        f"{HARNESS} decision present --gate harness-controls --repo {first} --repo {second}",
        first,
        first,
    )
    assert not hook._progress_control(
        rules.ToolCall(
            name="exec_command",
            kind="shell",
            cwd=str(first),
            command=f"{HARNESS} workflow cancel --repo {first} --repo {second}",
        ),
        first,
    )
    assert not hook._progress_control(
        rules.ToolCall(
            name="exec_command",
            kind="shell",
            cwd=str(first),
            command=f"{HARNESS} workflow cancel --session-id A --session-id B --repo {first}",
        ),
        first,
    )
    assert (
        cli.main(
            ["decision", "present", "--gate", "harness-controls", "--repo", str(second)]
        )
        != 0
    )
    assert "target project's workspace" in capsys.readouterr().err
    assert state.harness_mode(first) == "active"
    assert state.harness_mode(second) == "active"
    assert (
        cli.main(
            ["decision", "present", "--gate", "harness-controls", "--repo", str(first)]
        )
        == 0
    )


def test_onboarding_controls_are_sessionless_and_preserve_work(tmp_path: Path) -> None:
    saved = workflow.add_point(
        workflow.start("Original request").value,
        "Prepared",
        "preparation",
        completed_writes=("published-once",),
    ).value
    workflow.save(tmp_path, saved)
    assert isinstance(onboarding.control(tmp_path, "onboarding", "pause"), Ok)
    assert startup.begin(tmp_path, "Original request").value["state"] == "paused"
    assert isinstance(onboarding.control(tmp_path, "onboarding", "resume"), Ok)
    assert isinstance(onboarding.control(tmp_path, "onboarding", "reset"), Ok)
    reset = workflow.load(tmp_path).value
    assert reset.current.stage == "discovery"
    assert reset.current.completed_writes == ("published-once",)
    assert len(reset.points) == 1
    assert list((tmp_path / ".harness/state/workflows").glob("*.json"))
    assert isinstance(onboarding.control(tmp_path, "onboarding", "drop"), Ok)
    assert onboarding.mode(tmp_path) == "free"
    assert workflow.load(tmp_path).value == reset


def test_reset_scoped_preparation_preserves_approval_and_execution(
    tmp_path: Path,
) -> None:
    scope = work_sessions.start(tmp_path, "Original request").value.id
    prepared = workflow.add_point(
        workflow.start("Original request").value, "Prepared", "preparation"
    ).value
    workflow.save(tmp_path, prepared, scope)
    decisions.begin(
        tmp_path,
        "pending",
        "Approve plan?",
        ("Approve", "Revise"),
        "chat",
        work_session_id=scope,
    )
    state.open_approval(
        tmp_path,
        "previous",
        10,
        work_session_id=scope,
        binds={"target": ["tracker", "item-1"]},
    )
    assert isinstance(onboarding.control(tmp_path, "onboarding", "reset"), Ok)
    assert workflow.load(tmp_path, scope).value.current.stage == "discovery"
    assert decisions.pending(tmp_path, scope) is None
    assert state.active_approval(tmp_path, scope) is not None
    executing = workflow.add_point(
        workflow.load(tmp_path, scope).value, "Executing", "execution"
    ).value
    workflow.save(tmp_path, executing, scope)
    onboarding.control(tmp_path, "onboarding", "reset")
    assert workflow.load(tmp_path, scope).value == executing


def test_codex_host_is_detected_without_an_agent_capability_ceremony(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("CODEX_THREAD_ID", "actual-host-thread")
    assert (
        cli.main(
            ["decision", "present", "--gate", "planning-depth", "--repo", str(tmp_path)]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["transport"] == "blocking"


def test_native_suspend_and_resume_work_with_an_unanswered_decision(
    tmp_path: Path,
) -> None:
    decisions.begin(tmp_path, "A", "Required choice?", ("Continue", "Stop"), "chat")
    question = {
        "questions": [
            {
                "id": "control",
                "question": "How would you like to control the harness?",
                "header": "Controls",
                "options": [
                    {"label": "Suspend harness", "description": "Disable all checks"},
                    {"label": "Resume harness", "description": "Restore checks"},
                ],
            }
        ]
    }
    for number, option in enumerate(("Suspend harness", "Resume harness")):
        payload = {
            "tool_use_id": "control" + str(number),
            "tool_name": "functions.request_user_input",
            "tool_input": question,
        }
        run_hook(tmp_path, "ask", payload)
        run_hook(
            tmp_path,
            "answer",
            {
                **payload,
                "tool_response": {"answers": {"control": {"answers": [option]}}},
            },
        )
        assert state.harness_mode(tmp_path) == (
            "suspended" if number == 0 else "active"
        )
        assert decisions.pending(tmp_path).id == "A"
        assert state.active_approval(tmp_path) is None


def test_control_fallback_preserves_work_and_accepts_chat_number(
    tmp_path: Path,
) -> None:
    decisions.begin(tmp_path, "A", "Required choice?", ("Continue", "Stop"), "chat")
    payload = {
        "tool_use_id": "failed",
        "tool_name": "functions.request_user_input",
        "tool_input": {
            "questions": [
                {
                    "question": "How would you like to control the harness?",
                    "options": [
                        {"label": "Suspend harness"},
                        {"label": "Resume harness"},
                    ],
                }
            ]
        },
    }
    assert harness_controls.observe(tmp_path, "codex", payload)
    assert harness_controls.pending_native(tmp_path)
    assert not harness_controls.waiting(tmp_path)
    harness_controls.stage_chat(
        tmp_path,
        "fallback",
        "How would you like to control the harness?",
        ("Suspend harness", "Resume harness", "Free mode"),
    )
    assert not harness_controls.pending_native(tmp_path)
    assert harness_controls.waiting(tmp_path)
    assert harness_controls.prompt_operation(tmp_path, "1") == "suspend"
    assert harness_controls.prompt_operation(tmp_path, "9") is None
    assert harness_controls.prompt_operation(tmp_path, "²") is None
    harness_controls.stage_chat(
        tmp_path,
        "bound",
        "How would you like to control the harness?",
        ("Suspend harness", "Resume harness"),
        "chat-a",
    )
    assert harness_controls.prompt_operation(tmp_path, "1", "chat-b") is None
    assert harness_controls.prompt_operation(tmp_path, "1", "chat-a") == "suspend"
    assert decisions.pending(tmp_path).id == "A"
    assert state.active_approval(tmp_path) is None


def test_progress_control_cannot_cancel_another_conversations_session(
    tmp_path: Path,
) -> None:
    write_settings(tmp_path)
    first = work_sessions.start(tmp_path, "First work").value.id
    second = work_sessions.start(tmp_path, "Second work").value.id
    work_session_context.bind_session(tmp_path, "codex", "chat-a", first)
    decisions.begin(
        tmp_path,
        "required",
        "Continue?",
        ("Continue", "Stop"),
        "chat",
        work_session_id=first,
    )
    output = run_hook(
        tmp_path,
        "pre-tool",
        {
            "session_id": "chat-a",
            "tool_name": "exec_command",
            "tool_input": {
                "cmd": f"{HARNESS} workflow cancel --session-id {second} --repo {tmp_path}"
            },
        },
    )
    assert "work-session-mismatch" in output
    assert (
        work_sessions.select(tmp_path, second).value.status
        == work_sessions.Status.ACTIVE
    )
    assert decisions.pending(tmp_path, first).id == "required"
