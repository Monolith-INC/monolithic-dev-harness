"""The ordinary begin path waits for a host-captured saved-work choice."""

import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from core.result import Err, Ok
from harness import decisions, hook, session_entry, startup, work_sessions
from harness.startup_receipts import Invocation
from host_adapters import installation_project, startup_context, work_session_context


def test_begin_offers_saved_work_before_any_setup_or_session_change(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Saved report").value
    before = tuple(work_sessions.list_sessions(tmp_path).value)

    result = startup.begin(
        tmp_path, "New request", host="codex", conversation="thread-a"
    )
    assert isinstance(result, Ok)
    assert result.value["state"] == "choose_session"
    assert "--gate session-entry" in result.value["command"]
    prepared = session_entry.current_offer(tmp_path, "codex", "thread-a").value
    assert tuple(option.key for option in prepared.options) == (
        f"continue:{saved.id}",
        "new:pause",
        "new:stop",
    )
    assert tuple(work_sessions.list_sessions(tmp_path).value) == before
    assert (
        work_session_context.resolve_session(tmp_path, "codex", "thread-a").value
        is None
    )


def test_unbound_claude_begin_fails_closed_without_creating_an_offer(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Saved report").value
    before = tuple(work_sessions.list_sessions(tmp_path).value)

    result = startup.begin(tmp_path, "New request", host="claude")

    assert isinstance(result, Err) and result.failure.code == "entry_identity_missing"
    assert tuple(work_sessions.list_sessions(tmp_path).value) == before
    assert isinstance(work_session_context.resolve_session(tmp_path, "claude", ""), Err)
    assert not (tmp_path / ".harness/state/session-entry/claude").exists()
    assert saved.id == before[0].id


def test_absolute_plugin_begin_is_readable_without_harness_on_path(
    tmp_path: Path, monkeypatch
) -> None:
    plugin = Path(hook.__file__).resolve().parents[2]
    monkeypatch.setenv("PATH", "")
    command = shlex.join(
        (
            str(plugin / "bin/harness"),
            "begin",
            "--request",
            "New request",
            "--repo",
            str(tmp_path),
        )
    )

    assert startup_context.invocation(command, tmp_path) == Invocation("New request")


def test_claude_begin_uses_only_the_matching_trusted_host_invocation(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    work_sessions.start(tmp_path, "Saved report")
    plugin = Path(hook.__file__).resolve().parents[2]
    command = shlex.join(
        (
            str(plugin / "bin/harness"),
            "begin",
            "--request",
            "New request",
            "--repo",
            ".",
        )
    )
    payload = {
        "session_id": "claude-thread",
        "tool_use_id": "begin-call",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    assert isinstance(
        startup_context.arm(tmp_path, "claude", payload, command, tmp_path), Ok
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "")

    result = startup.begin(tmp_path, "New request")

    assert isinstance(result, Ok) and result.value["state"] == "choose_session"
    assert "--host claude" in result.value["command"]
    assert startup_context.identity_for_invocation(
        tmp_path, Invocation("New request"), "claude"
    ).value == ("claude", "claude-thread")

    presented = subprocess.run(
        [
            sys.executable,
            str(plugin / "scripts/harness/cli.py"),
            "decision",
            "present",
            "--gate",
            "session-entry",
            "--host",
            "claude",
            "--entry-request",
            "New request",
            "--repo",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert presented.returncode == 0, presented.stdout + presented.stderr
    assert json.loads(presented.stdout)["state"] == "choose_session"

    prepared = session_entry.current_offer(tmp_path, "claude", "claude-thread").value
    question = session_entry.question(prepared, "en")
    ask_payload = {
        "session_id": "claude-thread",
        "tool_use_id": "entry-question",
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": [question]},
    }
    monkeypatch.setattr(hook, "_workspace", lambda *_: tmp_path)
    hook._handle_ask("claude", ask_payload)
    hook.handle_answer(
        "claude",
        {
            **ask_payload,
            "tool_response": {
                "answers": {question["question"]: question["options"][0]["label"]}
            },
        },
    )
    capsys.readouterr()
    assert (
        work_session_context.resolve_session(tmp_path, "claude", "claude-thread").value
        == work_sessions.list_sessions(tmp_path).value[0].id
    )


def test_gate_command_presents_the_saved_work_menu(tmp_path: Path) -> None:
    work_sessions.start(tmp_path, "Saved report")
    startup.begin(tmp_path, "New request", host="codex", conversation="thread-a")
    plugin = Path(hook.__file__).resolve().parents[2]
    env = {**os.environ, "CODEX_THREAD_ID": "thread-a"}

    result = subprocess.run(
        [
            sys.executable,
            str(plugin / "scripts/harness/cli.py"),
            "decision",
            "present",
            "--gate",
            "session-entry",
            "--host",
            "codex",
            "--repo",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["state"] == "choose_session"
    assert output["transport"] == "blocking"
    options = output["questions"][0]["options"]
    assert "Saved report" in options[0]["label"]
    assert tuple(option["label"] for option in options) == (
        "Continue 1: Saved report",
        "Start new — pause the saved work",
        "Start new — stop the saved work",
    )


def test_large_menu_pages_require_observed_native_questions_and_preserve_sessions(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    saved = tuple(
        work_sessions.start(tmp_path, f"Saved report {index}").value
        for index in range(4)
    )
    startup.begin(tmp_path, "New request", host="codex", conversation="thread-a")
    plugin = Path(hook.__file__).resolve().parents[2]
    monkeypatch.setattr(hook, "_workspace", lambda *_: tmp_path)
    snapshot = tuple(
        (item.id, item.status, item.updated_at, item.events)
        for item in work_sessions.list_sessions(tmp_path).value
    )

    def present_page(call_id):
        result = subprocess.run(
            [
                sys.executable,
                str(plugin / "scripts/harness/cli.py"),
                "decision",
                "present",
                "--gate",
                "session-entry",
                "--host",
                "codex",
                "--entry-request",
                "New request",
                "--repo",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "CODEX_THREAD_ID": "thread-a"},
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        output = json.loads(result.stdout)
        assert output["transport"] == "blocking"
        shown = output["questions"][0]
        base = {
            "session_id": "thread-a",
            "tool_use_id": call_id,
            "tool_name": "request_user_input",
        }
        assert (
            hook._handle_ask("codex", {**base, "tool_input": {"questions": [shown]}})
            == 0
        )
        return base, shown

    def answer_page(base, shown, index):
        hook.handle_answer(
            "codex",
            {
                **base,
                "tool_input": {"questions": [shown]},
                "tool_response": {
                    "answers": {shown["question"]: shown["options"][index]["label"]}
                },
            },
        )
        capsys.readouterr()

    first_base = {
        "session_id": "thread-a",
        "tool_use_id": "fabricated",
        "tool_name": "request_user_input",
    }
    offered = session_entry.current_offer(tmp_path, "codex", "thread-a").value
    first_question = session_entry.question(offered, "en")
    assert len(first_question["options"]) == 3
    assert (
        session_entry.answer(
            tmp_path,
            "codex",
            {
                **first_base,
                "tool_input": {"questions": [first_question]},
                "tool_response": {
                    "answers": {
                        first_question["question"]: first_question["options"][2][
                            "label"
                        ]
                    }
                },
            },
        ).value
        is None
    )
    assert (
        tuple(
            (item.id, item.status, item.updated_at, item.events)
            for item in work_sessions.list_sessions(tmp_path).value
        )
        == snapshot
    )

    first_call, first_shown = present_page("entry-page-0")
    assert len(first_shown["options"]) == 3
    assert first_shown["options"][-1]["label"] == "More saved work"
    answer_page(first_call, first_shown, 2)
    assert session_entry.current_offer(tmp_path, "codex", "thread-a").value.page == 1
    assert (
        tuple(
            (item.id, item.status, item.updated_at, item.events)
            for item in work_sessions.list_sessions(tmp_path).value
        )
        == snapshot
    )

    second_call, second_shown = present_page("entry-page-1")
    assert len(second_shown["options"]) == 3
    assert second_shown["options"][1]["label"] == f"Continue 4: {saved[0].request}"
    answer_page(second_call, second_shown, 1)
    assert (
        work_session_context.resolve_session(tmp_path, "codex", "thread-a").value
        == saved[0].id
    )


def test_native_unavailable_keeps_large_menu_pending_without_chat_acceptance(
    tmp_path: Path,
) -> None:
    tuple(work_sessions.start(tmp_path, f"Saved report {index}") for index in range(4))
    startup.begin(tmp_path, "New request", host="codex", conversation="thread-a")
    before = tuple(
        (item.id, item.status, item.updated_at, item.events)
        for item in work_sessions.list_sessions(tmp_path).value
    )
    plugin = Path(hook.__file__).resolve().parents[2]
    result = subprocess.run(
        [
            sys.executable,
            str(plugin / "scripts/harness/cli.py"),
            "decision",
            "present",
            "--gate",
            "session-entry",
            "--host",
            "codex",
            "--entry-request",
            "New request",
            "--repo",
            str(tmp_path),
            "--native-unavailable",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "CODEX_THREAD_ID": "thread-a"},
        check=False,
    )

    assert result.returncode != 0
    assert "continue in a host that supports native questions" in result.stderr
    assert session_entry.answer_prompt(tmp_path, "codex", "thread-a", "4").value is None
    assert isinstance(session_entry.apply_selection(tmp_path, "codex", "thread-a"), Err)
    assert (
        tuple(
            (item.id, item.status, item.updated_at, item.events)
            for item in work_sessions.list_sessions(tmp_path).value
        )
        == before
    )


def test_host_captured_continue_binds_only_after_the_real_answer(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    saved = work_sessions.start(tmp_path, "Saved report").value
    startup.begin(tmp_path, "New request", host="codex", conversation="thread-a")
    prepared = session_entry.current_offer(tmp_path, "codex", "thread-a").value
    shown = session_entry.question(prepared, "en")
    base = {
        "session_id": "thread-a",
        "tool_use_id": "entry-question",
        "tool_name": "request_user_input",
    }
    monkeypatch.setattr(hook, "_workspace", lambda *_: tmp_path)

    assert (
        hook._handle_ask("codex", {**base, "tool_input": {"questions": [shown]}}) == 0
    )
    assert (
        work_session_context.resolve_session(tmp_path, "codex", "thread-a").value
        is None
    )

    hook.handle_answer(
        "codex",
        {
            **base,
            "tool_input": {"questions": [shown]},
            "tool_response": {
                "answers": {shown["question"]: shown["options"][0]["label"]}
            },
        },
    )
    capsys.readouterr()

    assert (
        work_session_context.resolve_session(tmp_path, "codex", "thread-a").value
        == saved.id
    )
    assert (
        session_entry.current_offer(tmp_path, "codex", "thread-a").failure.code
        == "entry_missing"
    )


def test_answer_from_another_conversation_cannot_select_or_bind(
    tmp_path: Path, monkeypatch
) -> None:
    saved = work_sessions.start(tmp_path, "Saved report").value
    startup.begin(tmp_path, "New request", host="codex", conversation="thread-a")
    prepared = session_entry.current_offer(tmp_path, "codex", "thread-a").value
    shown = session_entry.question(prepared, "en")
    monkeypatch.setattr(hook, "_workspace", lambda *_: tmp_path)
    payload = {
        "session_id": "thread-a",
        "tool_use_id": "entry-question",
        "tool_input": {"questions": [shown]},
    }
    hook._handle_ask("codex", payload)
    hook.handle_answer(
        "codex",
        {
            **payload,
            "session_id": "thread-b",
            "tool_response": {
                "answers": {shown["question"]: shown["options"][0]["label"]}
            },
        },
    )

    assert (
        work_session_context.resolve_session(tmp_path, "codex", "thread-a").value
        is None
    )
    assert (
        work_session_context.resolve_session(tmp_path, "codex", "thread-b").value
        is None
    )
    assert tuple(work_sessions.list_sessions(tmp_path).value)[0].id == saved.id


def test_codex_manifest_pretool_then_posttool_captures_native_session_choice(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Saved report").value
    assert (
        startup.begin(
            tmp_path, "New request", host="codex", conversation="thread-real"
        ).value["state"]
        == "choose_session"
    )
    offer = session_entry.current_offer(tmp_path, "codex", "thread-real").value
    shown = session_entry.question(offer, "en")
    payload = {
        "cwd": str(tmp_path),
        "session_id": "thread-real",
        "tool_use_id": "entry-real",
        "tool_name": "request_user_input",
        "tool_input": {"questions": [shown]},
    }
    plugin = Path(hook.__file__).resolve().parents[2]
    manifest = json.loads((plugin / "hooks/codex.hooks.json").read_text())

    def run_manifest_hook(
        event_name: str, matcher: str
    ) -> subprocess.CompletedProcess[str]:
        configured = next(
            entry
            for entry in manifest["hooks"][event_name]
            if entry.get("matcher") == matcher
        )
        command = configured["hooks"][0]["command"].replace(
            "${PLUGIN_ROOT}", str(plugin)
        )
        return subprocess.run(
            shlex.split(command),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=tmp_path,
            env={**os.environ, "CODEX_THREAD_ID": "agent-supplied-fake"},
            check=False,
        )

    pre_tool = run_manifest_hook("PreToolUse", ".*")
    assert pre_tool.returncode == 0, pre_tool.stdout + pre_tool.stderr
    assert '"decision": "deny"' not in pre_tool.stdout
    assert "presented" not in json.loads(
        (
            tmp_path
            / ".harness/state/session-entry/codex"
            / (hashlib.sha256(b"thread-real").hexdigest() + ".json")
        ).read_text()
    )

    payload["tool_response"] = {
        "answers": {shown["question"]: shown["options"][0]["label"]}
    }
    post_tool = run_manifest_hook(
        "PostToolUse", "^(functions\\.)?request_user_input(_async)?$"
    )
    assert post_tool.returncode == 0, post_tool.stdout + post_tool.stderr
    assert (
        work_session_context.resolve_session(tmp_path, "codex", "thread-real").value
        == saved.id
    )


def test_setup_only_begin_waits_for_a_captured_handover_choice(
    tmp_path: Path, capsys
) -> None:
    assert isinstance(
        decisions.begin(
            tmp_path,
            "setup-question",
            "Continue project setup?",
            ("Continue", "Stop"),
            "blocking",
            gate="setup-confirm",
            native_session_id="old-thread",
        ),
        Ok,
    )
    before = decisions.record(tmp_path)

    result = startup.begin(
        tmp_path, "New request", host="codex", conversation="new-thread"
    )

    assert isinstance(result, Ok) and result.value["state"] == "choose_session"
    prepared = session_entry.current_offer(tmp_path, "codex", "new-thread").value
    assert tuple(option.key for option in prepared.options) == ("new", "setup")
    assert (
        prepared.options
        and session_entry.question(prepared, "en")["options"][-1]["label"]
        == "Continue the unfinished setup"
    )
    assert decisions.record(tmp_path) == before
    assert tuple(work_sessions.list_sessions(tmp_path).value) == ()

    shown = session_entry.question(prepared, "en")
    payload = {
        "cwd": str(tmp_path),
        "session_id": "new-thread",
        "tool_use_id": "setup-entry-choice",
        "tool_name": "request_user_input",
        "tool_input": {"questions": [shown]},
    }
    assert hook._handle_ask("codex", payload) == 0
    hook.handle_answer(
        "codex",
        {
            **payload,
            "tool_response": {
                "answers": {shown["question"]: "Continue the unfinished setup"}
            },
        },
    )
    capsys.readouterr()

    handed_over = decisions.record(tmp_path)
    assert handed_over is not None
    assert handed_over["native_session_id"] == "new-thread"
    assert handed_over["handover_pending"] is True
    assert session_entry.selected(tmp_path, "codex", "new-thread") == "setup"
    assert tuple(work_sessions.list_sessions(tmp_path).value) == ()


def test_cursor_installed_hooks_capture_only_the_displayed_menu_and_scoped_reply(
    tmp_path: Path,
) -> None:
    saved = work_sessions.start(tmp_path, "Saved report").value
    plugin = Path(hook.__file__).resolve().parents[2]
    planned = installation_project.assets("cursor", tmp_path, plugin)
    assert isinstance(planned, Ok)
    hooks_text = next(
        item.text
        for item in planned.value
        if item.path == tmp_path / ".cursor/hooks.json"
    )
    manifest = json.loads(hooks_text)

    def run_hook(event: str, payload: dict, matcher: str | None = None):
        configured = next(
            item
            for item in manifest["hooks"][event]
            if matcher is None or item.get("matcher") == matcher
        )
        return subprocess.run(
            shlex.split(configured["command"]),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            cwd=tmp_path,
            check=False,
        )

    request = "New Cursor request"
    begin_command = shlex.join(
        (
            str(plugin / "bin/harness"),
            "begin",
            "--request",
            request,
            "--repo",
            str(tmp_path),
        )
    )
    begin_payload = {
        "hook_event_name": "preToolUse",
        "conversation_id": "cursor-thread",
        "generation_id": "cursor-gen-1",
        "tool_use_id": "begin-tool",
        "tool_name": "Shell",
        "tool_input": {"command": begin_command},
        "cwd": str(tmp_path),
        "workspace_roots": [str(tmp_path)],
    }
    pretool = run_hook("preToolUse", begin_payload)
    assert pretool.returncode == 0, pretool.stdout + pretool.stderr
    assert '"permission": "allow"' in pretool.stdout

    begin = subprocess.run(
        [
            sys.executable,
            str(plugin / "scripts/harness/cli.py"),
            "begin",
            "--request",
            request,
            "--repo",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "CODEX_THREAD_ID": "", "CURSOR_SESSION_ID": "fake"},
        check=False,
    )
    assert begin.returncode == 0, begin.stdout + begin.stderr
    assert json.loads(begin.stdout)["state"] == "choose_session"
    assert session_entry.current_offer(tmp_path, "cursor", "cursor-thread").value

    posttool = run_hook(
        "postToolUse",
        {
            **begin_payload,
            "hook_event_name": "postToolUse",
            "tool_output": json.dumps({"exitCode": 0, "stdout": begin.stdout}),
        },
        "Shell",
    )
    assert posttool.returncode == 0, posttool.stdout + posttool.stderr

    observed_output = run_hook(
        "postToolUse",
        {
            **begin_payload,
            "hook_event_name": "postToolUse",
            "tool_output": json.dumps({"exitCode": 0, "stdout": begin.stdout}),
        },
        "Shell|Read|Grep|MCP:.*",
    )
    assert observed_output.returncode == 0, (
        observed_output.stdout + observed_output.stderr
    )

    present = subprocess.run(
        [
            sys.executable,
            str(plugin / "scripts/harness/cli.py"),
            "decision",
            "present",
            "--gate",
            "session-entry",
            "--host",
            "cursor",
            "--entry-request",
            request,
            "--repo",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert present.returncode == 0, present.stdout + present.stderr
    displayed = json.loads(present.stdout)
    assert displayed["transport"] == "chat"
    menu = displayed["menu"]
    assert "Continue 1: Saved report" in menu

    def response(generation: str, text: str, conversation: str = "cursor-thread"):
        return run_hook(
            "afterAgentResponse",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": conversation,
                "generation_id": generation,
                "workspace_roots": [str(tmp_path)],
                "text": text,
            },
        )

    spoof = response("cursor-gen-1", menu.replace("Saved report", "Other report"))
    assert spoof.returncode == 0
    entry_path = session_entry._offer_path(tmp_path, "cursor", "cursor-thread").value
    assert "presented" not in json.loads(entry_path.read_text())

    unrelated = run_hook(
        "beforeSubmitPrompt",
        {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": "cursor-thread",
            "generation_id": "cursor-gen-2",
            "workspace_roots": [str(tmp_path)],
            "prompt": "Please wait before choosing.",
        },
    )
    assert unrelated.returncode == 0
    late_response = response("cursor-gen-1", menu)
    assert late_response.returncode == 0
    assert "presented" not in json.loads(entry_path.read_text())

    actual_display = response("cursor-gen-2", menu)
    assert actual_display.returncode == 0
    assert json.loads(entry_path.read_text())["transport"] == "chat"

    foreign_reply = run_hook(
        "beforeSubmitPrompt",
        {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": "other-cursor-thread",
            "generation_id": "other-gen-1",
            "workspace_roots": [str(tmp_path)],
            "prompt": "Continue 1: Saved report",
        },
    )
    assert foreign_reply.returncode == 0
    assert session_entry.selected(tmp_path, "cursor", "cursor-thread") is None

    selected_reply = run_hook(
        "beforeSubmitPrompt",
        {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": "cursor-thread",
            "generation_id": "cursor-gen-3",
            "workspace_roots": [str(tmp_path)],
            "prompt": "Continue 1: Saved report",
        },
    )
    assert selected_reply.returncode == 0
    assert session_entry.selected(tmp_path, "cursor", "cursor-thread") == saved.id
    assert (
        work_session_context.resolve_session(tmp_path, "cursor", "cursor-thread").value
        == saved.id
    )

    replay = run_hook(
        "beforeSubmitPrompt",
        {
            "hook_event_name": "beforeSubmitPrompt",
            "conversation_id": "cursor-thread",
            "generation_id": "cursor-gen-4",
            "workspace_roots": [str(tmp_path)],
            "prompt": "Continue 1: Saved report",
        },
    )
    assert replay.returncode == 0
    assert session_entry.selected(tmp_path, "cursor", "cursor-thread") == saved.id
    assert len(work_sessions.list_sessions(tmp_path).value) == 1
    assert response("cursor-gen-2", menu).returncode == 0
    assert json.loads(entry_path.read_text())["status"] == "complete"


def test_cursor_unrelated_prompt_cannot_answer_another_pending_decision(
    tmp_path: Path, capsys
) -> None:
    saved = work_sessions.start(tmp_path, "Saved report").value
    approval_id = "HB-CUR1234"
    assert isinstance(
        decisions.begin(
            tmp_path,
            "approval-question",
            "Approve the saved change?",
            ("Approve", "Reject"),
            "chat",
            approval=True,
            work_session_id=saved.id,
            native_session_id="cursor-thread",
        ),
        Ok,
    )
    startup.begin(tmp_path, "New request", host="cursor", conversation="cursor-thread")
    prepared = session_entry.current_offer(tmp_path, "cursor", "cursor-thread").value
    menu = session_entry._chat_entry_menu(prepared, "en")
    assert session_entry.observe_chat_response(
        tmp_path,
        "cursor",
        {
            "conversation_id": "cursor-thread",
            "generation_id": "cursor-gen-1",
            "text": menu,
        },
    ).value

    assert (
        hook.handle_prompt(
            "cursor",
            {
                "cwd": str(tmp_path),
                "workspace_roots": [str(tmp_path)],
                "conversation_id": "cursor-thread",
                "generation_id": "cursor-gen-2",
                "prompt": f"Approve {approval_id}",
            },
        )
        == 0
    )
    output = capsys.readouterr().out

    assert json.loads(output) == {"continue": True}
    pending = decisions.record(tmp_path, saved.id)
    assert pending is not None and pending["status"] == "pending"
    assert pending["answer"] == ""
    entry = session_entry.current_offer(tmp_path, "cursor", "cursor-thread")
    assert isinstance(entry, Ok)
    entry_path = session_entry._offer_path(tmp_path, "cursor", "cursor-thread").value
    record = json.loads(entry_path.read_text())
    assert record["status"] == "pending"
    assert not record.get("presented")
