"""The actual desktop async reply must affect only its independently staged control."""

import json

from harness import decisions, harness_controls, hook, state


def envelope(identifier="call-control", question="Como você quer controlar o harness?"):
    return (
        "<send_user_message_question_reply>\n"
        + json.dumps(
            [
                {
                    "questionItemId": json.dumps(
                        ["request_user_input_async", identifier, 0]
                    ),
                    "question": question,
                    "answer": "Suspender harness",
                }
            ]
        )
        + "\n</send_user_message_question_reply>\n"
    )


def stage(repo):
    return harness_controls.observe(
        repo,
        "codex",
        {
            "session_id": "chat-a",
            "tool_use_id": "call-control",
            "tool_name": "request_user_input_async",
            "tool_input": {
                "questions": [
                    {
                        "title": "Como você quer controlar o harness?",
                        "options": [
                            "Suspender harness",
                            "Retomar harness",
                            "Modo livre",
                        ],
                    }
                ]
            },
        },
    )


def test_async_control_reply_suspends_without_answering_pending_work(tmp_path):
    decisions.begin(
        tmp_path,
        "work",
        "Approve the implementation?",
        ("Approve", "Stop"),
        "chat",
        approval=True,
    )
    assert stage(tmp_path)
    hook.handle_prompt(
        "codex", {"session_id": "chat-a", "cwd": str(tmp_path), "prompt": envelope()}
    )
    assert state.harness_mode(tmp_path) == "suspended"
    assert decisions.pending(tmp_path).id == "work"
    assert not harness_controls.waiting(tmp_path, "chat-a")


def test_foreign_or_wrong_presentation_cannot_suspend(tmp_path):
    assert stage(tmp_path)
    assert (
        harness_controls.prompt_operation(tmp_path, envelope("foreign"), "chat-a")
        is None
    )
    assert harness_controls.prompt_operation(tmp_path, envelope(), "chat-b") is None
    assert harness_controls.waiting(tmp_path, "chat-a")


def test_numeric_async_recovery_matches_only_that_conversation(tmp_path):
    assert stage(tmp_path)
    assert harness_controls.prompt_operation(tmp_path, "1", "chat-a") == "suspend"
    assert harness_controls.prompt_operation(tmp_path, "1", "chat-b") is None
