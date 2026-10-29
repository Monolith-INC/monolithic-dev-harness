"""A genuine parent reply can settle a relayed choice, never an approval."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.result import Ok
from harness import decisions, state

# The plugin's own launcher: a bare `harness` is recognized only when it is installed on PATH.
HARNESS = str(Path(__file__).resolve().parents[2] / "bin" / "harness")

CLI = Path(__file__).resolve().parents[2] / "scripts/harness/cli.py"
PARENT = "11111111-1111-4111-8111-111111111111"
CHILD = "22222222-2222-4222-8222-222222222222"
OPTIONS = ("Investigate first (Recommended)", "Draft work items", "Explore the idea")


def row(payload):
    return {"type": "response_item", "payload": payload}


def transcript(home, identifier, metadata, events):
    home.joinpath("sessions/2026/10/27").mkdir(parents=True, exist_ok=True)
    home.joinpath(f"sessions/2026/10/27/rollout-test-{identifier}.jsonl").write_text(
        "\n".join(
            json.dumps(value)
            for value in (
                {"type": "session_meta", "payload": {"id": identifier, **metadata}},
                *events,
            )
        )
    )
    return home


def request(options=OPTIONS):
    return row(
        {
            "type": "function_call",
            "name": "request_user_input_async",
            "call_id": "native-call",
            "arguments": json.dumps(
                {"questions": [{"title": "Choose the next step?", "options": options}]}
            ),
        }
    )


def delivered():
    return row(
        {
            "type": "function_call_output",
            "call_id": "native-call",
            "output": '{"accepted":true}',
        }
    )


def human(text="Investigate first", role="user"):
    return row(
        {
            "type": "message",
            "role": role,
            "id": "human-message",
            "content": [{"type": "input_text", "text": text}],
        }
    )


def observation(repo):
    return row(
        {
            "type": "custom_tool_call_output",
            "output": [
                {
                    "type": "input_text",
                    "text": json.dumps({"output": decisions.status(repo)}),
                }
            ],
        }
    )


def prepare(repo, home, events, *, parent=PARENT, approval=False):
    assert isinstance(
        decisions.begin(
            repo,
            "decision-one",
            "Choose the next step?",
            OPTIONS,
            "chat",
            native_session_id=CHILD,
            approval=approval,
        ),
        Ok,
    )
    transcript(
        home, CHILD, {"parent_thread_id": parent, "thread_source": "subagent"}, ()
    )
    transcript(
        home,
        PARENT,
        {"cwd": str(repo.parent), "thread_source": "user"},
        (observation(repo), *events),
    )
    return repo


def recover(repo, home, *extra):
    return subprocess.run(
        (
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; from host_adapters import codex_relay; "
            "codex_relay._session_home=lambda home=Path(sys.argv.pop(1)):home; "
            "from harness.cli import main; raise SystemExit(main(sys.argv[1:]))",
            str(home),
            "decision",
            "recover",
            "--host",
            "codex",
            "--repo",
            str(repo),
            *extra,
        ),
        env={**os.environ, "CODEX_HOME": str(home), "CODEX_THREAD_ID": PARENT},
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_recover_uses_recorded_parent_reply_not_agent_answer(tmp_path):
    prepare(tmp_path / "project", tmp_path / "home", (request(), delivered(), human()))
    assert recover(tmp_path / "project", tmp_path / "home").returncode == 0
    assert (
        decisions.record(tmp_path / "project")["answer"]
        == "Investigate first (Recommended)"
    )
    assert (
        decisions.record(tmp_path / "project")["human_reply_evidence"]["message_id"]
        == "human-message"
    )
    assert state.active_approval(tmp_path / "project") is None


@pytest.mark.parametrize(
    "events",
    (
        (request(), delivered()),
        (request(), delivered(), human(role="assistant")),
        (request(), human()),
        (human(), request(), delivered()),
        (request(("Changed", "Other")), delivered(), human()),
        (request(), delivered(), human("What happened?")),
    ),
)
def test_unmatched_or_nonhuman_evidence_keeps_gate_pending(tmp_path, events):
    prepare(tmp_path / "project", tmp_path / "home", events)
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")


def test_recreated_pending_instance_cannot_consume_an_old_reply(tmp_path):
    prepare(tmp_path / "project", tmp_path / "home", (request(), delivered(), human()))
    assert recover(tmp_path / "project", tmp_path / "home").returncode == 0
    assert isinstance(
        decisions.begin(
            tmp_path / "project",
            "decision-one",
            "Choose the next step?",
            OPTIONS,
            "chat",
            native_session_id=CHILD,
        ),
        Ok,
    )
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")


def test_status_question_does_not_discard_the_later_human_choice(tmp_path):
    prepare(
        tmp_path / "project",
        tmp_path / "home",
        (
            request(),
            delivered(),
            human("whats next"),
            human(),
        ),
    )
    assert recover(tmp_path / "project", tmp_path / "home").returncode == 0
    assert (
        decisions.record(tmp_path / "project")["answer"]
        == "Investigate first (Recommended)"
    )


def test_caller_selected_codex_home_is_not_a_native_evidence_source(tmp_path):
    prepare(tmp_path / "project", tmp_path / "home", (request(), delivered(), human()))
    assert (
        subprocess.run(
            (
                sys.executable,
                str(CLI),
                "decision",
                "recover",
                "--host",
                "codex",
                "--repo",
                str(tmp_path / "project"),
            ),
            env={
                **os.environ,
                "CODEX_HOME": str(tmp_path / "home"),
                "CODEX_THREAD_ID": PARENT,
            },
            capture_output=True,
            text=True,
            timeout=15,
        ).returncode
        != 0
    )
    assert decisions.waiting(tmp_path / "project")


def test_changed_native_option_descriptions_are_not_the_same_choice(tmp_path):
    prepare(
        tmp_path / "project",
        tmp_path / "home",
        (
            request(
                tuple(
                    {"label": option, "description": "Materially different meaning"}
                    for option in OPTIONS
                )
            ),
            delivered(),
            human(),
        ),
    )
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")


def test_another_parent_cannot_resolve_the_childs_choice(tmp_path):
    prepare(
        tmp_path / "project",
        tmp_path / "home",
        (request(), delivered(), human()),
        parent="33333333-3333-4333-8333-333333333333",
    )
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")


def test_recovery_cannot_grant_approval(tmp_path):
    prepare(
        tmp_path / "project",
        tmp_path / "home",
        (request(), delivered(), human()),
        approval=True,
    )
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")
    assert state.active_approval(tmp_path / "project") is None


def test_question_without_exact_pending_record_observation_is_rejected(tmp_path):
    prepare(tmp_path / "project", tmp_path / "home", ())
    transcript(
        tmp_path / "home",
        PARENT,
        {"cwd": str(tmp_path), "thread_source": "user"},
        (request(), delivered(), human()),
    )
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")


def test_recovery_rejects_agent_supplied_answers(tmp_path):
    prepare(tmp_path / "project", tmp_path / "home", (request(), delivered(), human()))
    assert (
        recover(
            tmp_path / "project", tmp_path / "home", "--answer", "Investigate first"
        ).returncode
        != 0
    )
    assert decisions.waiting(tmp_path / "project")


def test_recovery_is_reachable_while_a_choice_waits(tmp_path):
    from tests.harness.test_decisions import native

    prepare(tmp_path / "project", tmp_path / "home", ())
    assert "Wait for the human" not in native(
        tmp_path / "project",
        "pre-tool",
        {
            "tool_name": "exec_command",
            "tool_input": {
                "cmd": f"{HARNESS} decision recover --host codex --repo {tmp_path / 'project'}",
            },
        },
    )
    assert decisions.waiting(tmp_path / "project")


def test_one_user_reply_cannot_be_consumed_twice(tmp_path):
    prepare(tmp_path / "project", tmp_path / "home", (request(), delivered(), human()))
    assert recover(tmp_path / "project", tmp_path / "home").returncode == 0
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert (
        len(
            state.read_json(tmp_path / "project/.harness/state/decision-history.json")[
                "answers"
            ]
        )
        == 1
    )


def test_changed_reviewed_content_cannot_be_accepted_by_recovery(tmp_path):
    tmp_path.joinpath("project").mkdir()
    tmp_path.joinpath("project/plan.md").write_text("old plan")
    assert isinstance(
        decisions.begin(
            tmp_path / "project",
            "decision-one",
            "Choose the next step?",
            OPTIONS,
            "chat",
            (("plan.md", hashlib.sha256(b"old plan").hexdigest()),),
            native_session_id=CHILD,
        ),
        Ok,
    )
    transcript(tmp_path / "home", CHILD, {"parent_thread_id": PARENT}, ())
    transcript(
        tmp_path / "home",
        PARENT,
        {"cwd": str(tmp_path)},
        (
            observation(tmp_path / "project"),
            request(),
            delivered(),
            human(),
        ),
    )
    tmp_path.joinpath("project/plan.md").write_text("changed plan")
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")


def test_new_question_prevents_misattributing_the_next_reply(tmp_path):
    prepare(
        tmp_path / "project",
        tmp_path / "home",
        (
            request(),
            delivered(),
            request(("Something else", "Stop")),
            delivered(),
            human(),
        ),
    )
    assert recover(tmp_path / "project", tmp_path / "home").returncode != 0
    assert decisions.waiting(tmp_path / "project")


def test_missing_native_session_evidence_leaves_choice_pending(tmp_path):
    prepare(tmp_path / "project", tmp_path / "home", (request(), delivered(), human()))
    assert recover(tmp_path / "project", tmp_path / "missing-home").returncode != 0
    assert decisions.waiting(tmp_path / "project")
