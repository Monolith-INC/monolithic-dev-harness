"""Exercise the serialized output recorded by Codex Desktop, through real hook processes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import decisions, state
from tests.harness.test_decisions import native
from tests.settings_fixture import write_settings


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    write_settings(tmp_path)
    return tmp_path


def question(approval: bool = False) -> dict:
    match approval:
        case True:
            return {
                "questions": [
                    {
                        "id": "approval",
                        "header": "Review",
                        "question": "Publish these items?",
                        "options": [
                            {
                                "label": "Approve",
                                "description": "Publish the reviewed items.",
                            },
                            {"label": "Not now", "description": "Keep the draft."},
                        ],
                    }
                ],
            }
        case False:
            return {
                "questions": [
                    {
                        "id": "next_step",
                        "header": "Next step",
                        "question": "What would you like to do next?",
                        "options": [
                            {
                                "label": "Start feature work (Recommended)",
                                "description": "Begin planning a feature.",
                            },
                            {
                                "label": "Prepare work items",
                                "description": "Organize the work.",
                            },
                            {
                                "label": "Explore an idea",
                                "description": "Refine an idea.",
                            },
                        ],
                    }
                ],
            }


def ask(repo: Path, approval: bool = False) -> str:
    return native(
        repo,
        "ask",
        {
            "tool_name": "request_user_input",
            "tool_use_id": "captured-call",
            "tool_input": question(approval),
        },
    )


def answer(repo: Path, response: object, approval: bool = False) -> str:
    return native(
        repo,
        "answer",
        {
            "tool_name": "request_user_input",
            "tool_use_id": "captured-call",
            "tool_input": question(approval),
            "tool_response": response,
        },
    )


@pytest.mark.parametrize(
    "response",
    [
        {"answers": {"next_step": {"answers": ["Start feature work (Recommended)"]}}},
        '{"answers":{"next_step":{"answers":["Start feature work (Recommended)"]}}}',
    ],
)
def test_recorded_codex_choice_resolves_pending(repo: Path, response: object) -> None:
    ask(repo)
    answer(repo, response)
    assert not decisions.waiting(repo)
    assert decisions.record(repo)["answer"] == "Start feature work (Recommended)"
    assert state.active_approval(repo) is None


def test_serialized_approval_is_honored_once(repo: Path) -> None:
    ask(repo, True)
    answer(repo, '{"answers":{"approval":{"answers":["Approve"]}}}', True)
    assert not decisions.waiting(repo)
    assert state.active_approval(repo) is not None
    state.revoke_approvals(repo)
    answer(repo, '{"answers":{"approval":{"answers":["Approve"]}}}', True)
    assert state.active_approval(repo) is None


@pytest.mark.parametrize(
    "response",
    [
        "private malformed reply",
        "[]",
        "42",
        '"private nested text"',
        {"answers": {"next_step": {"answers": []}}},
        {"answers": {"wrong_question": {"answers": ["Start feature work"]}}},
    ],
)
def test_failed_capture_is_visible_without_private_content(
    repo: Path, response: object
) -> None:
    ask(repo)
    assert "capture failed" in answer(repo, response)
    assert decisions.waiting(repo)
    assert "private" not in answer(repo, response)
    assert state.active_approval(repo) is None


def test_async_completion_remains_delivery_even_with_serialized_answer(
    repo: Path,
) -> None:
    native(
        repo,
        "ask",
        {
            "tool_name": "request_user_input_async",
            "tool_use_id": "captured-call",
            "tool_input": {
                "questions": [
                    {
                        "title": "What would you like to do next?",
                        "options": ["Start feature work", "Prepare work items"],
                    }
                ]
            },
        },
    )
    answer(
        repo,
        json.dumps({"answers": {"next_step": {"answers": ["Start feature work"]}}}),
    )
    assert decisions.waiting(repo)


def test_other_routes_the_actual_request_without_authorizing_writes(repo: Path) -> None:
    ask(repo)
    answer(
        repo,
        '{"answers":{"next_step":{"answers":["backlog/DAY-003-shared-lists.md"]}}}',
    )
    assert not decisions.waiting(repo)
    assert decisions.record(repo)["answer"] == "backlog/DAY-003-shared-lists.md"
    assert state.active_approval(repo) is None


@pytest.mark.parametrize("chosen", ["publish everything", " ", "Approve"])
def test_other_never_authorizes_an_approval_question(repo: Path, chosen: str) -> None:
    ask(repo, True)
    answer(repo, json.dumps({"answers": {"approval": {"answers": [chosen]}}}), True)
    match chosen:
        case "Approve":
            assert not decisions.waiting(repo)
            assert state.active_approval(repo) is not None
        case _:
            assert decisions.waiting(repo)
            assert state.active_approval(repo) is None


def test_prepared_routing_question_can_explicitly_allow_other(repo: Path) -> None:
    assert decisions.begin(
        repo,
        "route",
        "What would you like to do next?",
        ("Start feature work (Recommended)", "Prepare work items", "Explore an idea"),
        "blocking",
        allow_free_text=True,
    ).value["allow_free_text"]
    # A prepared question keeps its policy when bound to a native tool-call id.
    native(
        repo,
        "ask",
        {
            "tool_name": "request_user_input",
            "tool_use_id": "captured-call",
            "tool_input": {
                "questions": [{**question()["questions"][0], "id": "route"}]
            },
        },
    )
    native(
        repo,
        "answer",
        {
            "tool_use_id": "captured-call",
            "tool_input": {
                "questions": [{**question()["questions"][0], "id": "route"}]
            },
            "tool_response": '{"answers":{"route":{"answers":["my feature request"]}}}',
        },
    )
    assert decisions.record(repo)["answer"] == "my feature request"
    assert state.active_approval(repo) is None
