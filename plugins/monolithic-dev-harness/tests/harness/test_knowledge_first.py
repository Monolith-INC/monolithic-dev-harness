"""The mode's knowledge-first reminder has a single per-prompt state."""

import fcntl
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from project_knowledge import freshness

from core.result import Err, Ok
from harness import (
    hook,
    knowledge_first,
    knowledge_first_live,
    knowledge_first_store,
    mode_hooks,
    modes,
    rules,
)
from host_adapters import hook_bridge
from tests.settings_fixture import write_settings


def test_host_events_require_successful_knowledge_read_and_reset_per_prompt(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    store = tmp_path / "Project_Knowledge"
    store.mkdir()
    write_settings(
        tmp_path, knowledge={"format": "markdown", "root": "Project_Knowledge"}
    )
    monkeypatch.setattr(hook, "_workspace", lambda payload, host: tmp_path)
    monkeypatch.setattr(
        knowledge_first_live,
        "_context",
        lambda repo, host, payload: ("chat-1", store),
    )
    monkeypatch.setattr(freshness, "verified_fresh", lambda repo, root: True)

    payload = {"cwd": str(tmp_path), "session_id": "chat-1", "prompt": "investigate"}
    assert hook.handle_prompt("claude", payload) == 0
    assert not knowledge_first_store.read(tmp_path, "claude", "chat-1").value.searched

    outside_read = {
        **payload,
        "tool_name": "Read",
        "tool_input": {"file_path": str(tmp_path / "src/main.py")},
    }
    assert hook.handle_pre_tool("claude", "pre-tool", outside_read) == 0
    assert "knowledge-first" in capsys.readouterr().out
    assert not knowledge_first_store.read(tmp_path, "claude", "chat-1").value.searched

    knowledge_read = {
        **payload,
        "tool_name": "Bash",
        "tool_use_id": "tool-knowledge-1",
        "tool_input": {
            "command": f"{hook.PLUGIN_ROOT / 'bin/harness'} knowledge find rules",
            "cwd": str(tmp_path),
        },
    }
    assert hook.handle_pre_tool("claude", "pre-tool", knowledge_read) == 0
    assert not knowledge_first_store.read(tmp_path, "claude", "chat-1").value.searched
    hook._dispatch_event(
        type("Args", (), {"event": "knowledge-post", "host": "claude"})(),
        {**knowledge_read, "tool_response": {"exit_code": 1}},
    )
    assert not knowledge_first_store.read(tmp_path, "claude", "chat-1").value.searched

    assert hook.handle_pre_tool("claude", "pre-tool", knowledge_read) == 0
    hook._dispatch_event(
        type("Args", (), {"event": "knowledge-post", "host": "claude"})(),
        {**knowledge_read, "tool_response": {"exit_code": 0}},
    )
    assert knowledge_first_store.read(tmp_path, "claude", "chat-1").value.searched

    next_prompt = {**payload, "prompt": "new task"}
    assert hook.handle_prompt("claude", next_prompt) == 0
    assert not knowledge_first_store.read(tmp_path, "claude", "chat-1").value.searched
    denied = hook.handle_pre_tool("claude", "pre-tool", outside_read)
    assert denied == 0 and "knowledge-first" in capsys.readouterr().out


def test_only_validated_knowledge_reads_bypass_the_pending_write_gate(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(hook.decisions, "blocking", lambda repo, scope: True)
    monkeypatch.setattr(hook.decisions, "pending", lambda repo, scope: object())
    monkeypatch.setattr(hook, "_pending_decision_guidance", lambda *args: "pending")

    def held(command: str):
        call = hook_bridge.parse_tool_call(
            "claude",
            "pre-tool",
            {
                "cwd": str(tmp_path),
                "tool_name": "Bash",
                "tool_input": {"command": command},
            },
        )
        return hook._held(tmp_path, call, Ok(None), None, host="claude")

    executable = str(hook.PLUGIN_ROOT / "bin/harness")
    assert held(f"{executable} knowledge find terms") is None
    assert held(f"{executable} knowledge find terms --repo {tmp_path}") is None
    assert held(f"{executable} knowledge find terms --repo /other") is not None
    assert (
        held(f"{executable} knowledge find terms --repo {tmp_path} --repo {tmp_path}")
        is not None
    )
    assert held(f"{executable} knowledge refresh") is not None
    assert held(f"{executable} knowledge find terms && touch marker") is not None


def test_lock_failure_fails_open_with_user_visible_notice(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    store = tmp_path / "Project_Knowledge"
    store.mkdir()
    monkeypatch.setattr(hook, "_workspace", lambda payload, host: tmp_path)
    monkeypatch.setattr(
        knowledge_first_live,
        "_context",
        lambda repo, host, payload: ("chat-lock", store),
    )
    monkeypatch.setattr(freshness, "verified_fresh", lambda repo, root: True)
    record = knowledge_first_store.begin_prompt(tmp_path, "claude", "chat-lock").value
    lock_path = next((tmp_path / ".harness/state/knowledge-first").glob("*.lock"))
    payload = {
        "cwd": str(tmp_path),
        "session_id": "chat-lock",
        "tool_name": "Read",
        "tool_input": {"file_path": str(tmp_path / "src/main.py")},
    }

    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert hook.handle_pre_tool("claude", "pre-tool", payload) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"].get("permissionDecision", "allow") == "allow"
    assert "knowledge-first reminder state is unavailable" in output["systemMessage"]
    assert knowledge_first_store.read(tmp_path, "claude", "chat-lock") == record


def test_state_read_exception_fails_open_with_user_visible_notice(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    store = tmp_path / "Project_Knowledge"
    store.mkdir()
    monkeypatch.setattr(hook, "_workspace", lambda payload, host: tmp_path)
    monkeypatch.setattr(
        knowledge_first_live,
        "_context",
        lambda repo, host, payload: ("chat-error", store),
    )
    monkeypatch.setattr(
        knowledge_first_store,
        "read",
        lambda *args: (_ for _ in ()).throw(OSError("locked")),
    )
    payload = {
        "cwd": str(tmp_path),
        "session_id": "chat-error",
        "tool_name": "Read",
        "tool_input": {"file_path": str(tmp_path / "src/main.py")},
    }

    assert hook.handle_pre_tool("claude", "pre-tool", payload) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"].get("permissionDecision", "allow") == "allow"
    assert "knowledge-first reminder state is unavailable" in output["systemMessage"]


def test_real_hook_subprocess_loads_the_project_knowledge_package(
    tmp_path: Path,
) -> None:
    payload = {
        "cwd": str(tmp_path),
        "session_id": "chat-subprocess",
        "tool_name": "Bash",
        "tool_input": {"command": "echo knowledge"},
    }
    result = subprocess.run(
        [
            sys.executable,
            str(hook.PLUGIN_ROOT / "scripts/harness/hook.py"),
            "--host",
            "claude",
            "--event",
            "pre-tool",
        ],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "[harness harness-error]" not in result.stdout
    assert '"permissionDecision":"deny"' not in result.stdout


def test_external_read_is_refused_only_once_until_a_knowledge_read() -> None:
    initial = knowledge_first.State()
    refused = knowledge_first.evaluate(initial, True, True, "external_read")
    retry = knowledge_first.evaluate(refused.state, True, True, "external_read")
    read = knowledge_first.evaluate(refused.state, True, True, "knowledge_read")
    after = knowledge_first.evaluate(read.state, True, True, "external_read")

    assert not refused.allowed and "knowledge find" in refused.message
    assert retry.allowed and after.allowed


def test_empty_store_allows_and_notifies_once() -> None:
    first = knowledge_first.evaluate(
        knowledge_first.State(), True, False, "external_read"
    )
    second = knowledge_first.evaluate(first.state, True, False, "external_read")

    assert first.allowed and "empty" in first.message
    assert second.allowed and not second.message


def test_outside_mode_and_unrelated_actions_are_silent() -> None:
    initial = knowledge_first.State()
    outside = knowledge_first.evaluate(initial, False, True, "external_read")
    unrelated = knowledge_first.evaluate(initial, True, True, "other")

    assert outside.allowed and not outside.message and outside.state == initial
    assert unrelated.allowed and not unrelated.message and unrelated.state == initial


def test_mode_hook_runs_only_when_its_manifest_selects_knowledge_first(
    tmp_path: Path, monkeypatch
) -> None:
    mode = modes.Mode(
        name="discovery",
        goal="discover",
        expectations=(),
        entry_skill="discovery",
        skills=(),
        operations=(),
        hooks=("knowledge_first",),
        knowledge="first",
        exit=(),
        root=tmp_path,
    )
    active = modes.Active("discovery", "WS-1", "", "", mode)
    monkeypatch.setattr(mode_hooks, "_hooked", lambda repo, hook: active)

    result = mode_hooks.knowledge_first_decision(
        tmp_path, knowledge_first.State(), True, "external_read"
    )

    assert not result.allowed


def test_classifier_distinguishes_reads_inside_and_outside_the_store() -> None:
    root = Path("/repo/knowledge")

    assert (
        knowledge_first.classify("Read", (root / "catalog.tsv",), root)
        == "knowledge_read"
    )
    assert knowledge_first.classify("Read", (root / "unit.md",), root) == "other"
    assert knowledge_first.classify("Grep", (root,), root) == "other"
    assert (
        knowledge_first.classify("Glob", (Path("/repo/src"),), root) == "external_read"
    )
    assert knowledge_first.classify("Grep", (), root) == "external_read"
    assert knowledge_first.classify("WebFetch", (), root) == "external_read"
    assert knowledge_first.classify("Write", (Path("/repo/file"),), root) == "other"
    assert (
        knowledge_first.classify("Read", (Path("relative"),), root) == "external_read"
    )
    assert (
        knowledge_first.classify("Read", (root / ".." / "secret",), root)
        == "external_read"
    )


def test_classifier_only_recognizes_checked_read_only_harness_commands() -> None:
    root = Path("/repo/knowledge")

    assert (
        knowledge_first.classify(
            "Bash",
            (),
            root,
            ("knowledge", "find", "rule"),
            expected_repo=Path("/repo"),
            command_repo=Path("/repo"),
            command_store=root,
        )
        == "knowledge_read"
    )
    assert (
        knowledge_first.classify(
            "Bash",
            (),
            root,
            ("knowledge", "fetch", "rule"),
            expected_repo=Path("/repo"),
            command_repo=Path("/repo"),
            command_store=root,
        )
        == "knowledge_read"
    )
    assert (
        knowledge_first.classify("Bash", (), root, ("knowledge", "refresh")) == "other"
    )
    assert knowledge_first.classify("Bash", (), root, None) == "other"
    assert knowledge_first.classify("Write", (), root, ("knowledge", "find")) == "other"
    assert knowledge_first.classify("Bash", (), root, ("knowledge", "find")) == "other"
    assert (
        knowledge_first.classify(
            "Bash",
            (),
            root,
            ("knowledge", "catalog", "--repo", "/other"),
            expected_repo=Path("/repo"),
            command_repo=Path("/other"),
            command_store=root,
        )
        == "other"
    )
    assert (
        knowledge_first.classify(
            "Bash",
            (),
            root,
            ("knowledge", "catalog", "--help"),
            expected_repo=Path("/repo"),
            command_repo=Path("/repo"),
            command_store=root,
        )
        == "other"
    )


def test_late_read_cannot_satisfy_next_prompt(tmp_path: Path) -> None:
    first = knowledge_first_store.begin_prompt(tmp_path, "codex", "chat").value
    second = knowledge_first_store.begin_prompt(tmp_path, "codex", "chat").value

    late = knowledge_first_store.transition(
        tmp_path, "codex", "chat", first.epoch, True, "knowledge_read"
    )
    current = knowledge_first_store.read(tmp_path, "codex", "chat")

    assert isinstance(late, Ok) and late.value is None
    assert current == second and not current.value.searched


def test_prompt_state_is_scoped_and_requires_identity(tmp_path: Path) -> None:
    first = knowledge_first_store.begin_prompt(tmp_path, "codex", "one").value
    second = knowledge_first_store.begin_prompt(tmp_path, "codex", "two").value

    knowledge_first_store.transition(
        tmp_path, "codex", "one", first.epoch, True, "knowledge_read"
    )

    assert knowledge_first_store.read(tmp_path, "codex", "one").value.searched
    assert knowledge_first_store.read(tmp_path, "codex", "two") == second
    assert isinstance(knowledge_first_store.begin_prompt(tmp_path, "codex", ""), Err)


def test_prompt_state_is_protected_against_agent_writes() -> None:
    assert rules.is_human_owned(".harness/state/knowledge-first/fake.json")


def test_busy_state_returns_without_overwriting(tmp_path: Path) -> None:
    record = knowledge_first_store.begin_prompt(tmp_path, "codex", "chat").value
    lock_path = next((tmp_path / ".harness/state/knowledge-first").glob("*.lock"))

    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = knowledge_first_store.transition(
            tmp_path, "codex", "chat", record.epoch, True, "knowledge_read"
        )

    assert isinstance(result, Err)
    assert knowledge_first_store.read(tmp_path, "codex", "chat") == record


def test_only_success_for_observed_tool_in_same_prompt_counts(tmp_path: Path) -> None:
    first = knowledge_first_store.begin_prompt(tmp_path, "codex", "chat").value
    assert knowledge_first_store.observe_read(
        tmp_path, "codex", "chat", first.epoch, "tool-1"
    ).value
    assert not knowledge_first_store.complete_read(
        tmp_path, "codex", "chat", "other", True
    ).value
    assert not knowledge_first_store.complete_read(
        tmp_path, "codex", "chat", "tool-1", False
    ).value
    assert not knowledge_first_store.read(tmp_path, "codex", "chat").value.searched
    assert knowledge_first_store.observe_read(
        tmp_path, "codex", "chat", first.epoch, "tool-2"
    ).value
    second = knowledge_first_store.begin_prompt(tmp_path, "codex", "chat").value
    assert not knowledge_first_store.complete_read(
        tmp_path, "codex", "chat", "tool-2", True
    ).value
    assert knowledge_first_store.read(tmp_path, "codex", "chat") == second
    assert knowledge_first_store.observe_read(
        tmp_path, "codex", "chat", second.epoch, "tool-3"
    ).value
    assert knowledge_first_store.complete_read(
        tmp_path, "codex", "chat", "tool-3", True
    ).value
    assert knowledge_first_store.read(tmp_path, "codex", "chat").value.searched


def test_freshness_requires_matching_source_hashes(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("facts", encoding="utf-8")
    root = tmp_path / "knowledge"
    root.mkdir()
    unit = root / "unit.md"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    unit.write_text(
        f"---\nid: unit\nstatus: current\nsources:\n  - source.txt#sha256:{digest}\n---\n\n## Fact\nKnowledge.\n"
    )

    assert freshness.verified_fresh(tmp_path, root)
    source.write_text("changed", encoding="utf-8")
    assert not freshness.verified_fresh(tmp_path, root)
    unit.write_text("---\nid: unit\nsources:\n  - source.txt\n---\nFacts")
    assert not freshness.verified_fresh(tmp_path, root)
    assert not freshness.verified_fresh(tmp_path, tmp_path / "missing")


def test_live_observation_requires_explicit_success_and_exact_tool_id(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        knowledge_first_live, "_context", lambda *args: ("chat", tmp_path)
    )
    monkeypatch.setattr(
        knowledge_first_live, "_classify", lambda *args: "knowledge_read"
    )
    record = knowledge_first_store.begin_prompt(tmp_path, "codex", "chat").value
    payload = {"tool_use_id": "read-1"}
    knowledge_first_live.before(tmp_path, "codex", payload, rules.make_call("read", {}))
    knowledge_first_live.after(
        tmp_path, "codex", {"tool_use_id": "read-1", "tool_response": "output"}
    )
    assert not knowledge_first_store.read(tmp_path, "codex", "chat").value.searched
    knowledge_first_live.after(
        tmp_path, "codex", {"tool_use_id": "other", "tool_response": {"exit_code": 0}}
    )
    assert not knowledge_first_store.read(tmp_path, "codex", "chat").value.searched
    knowledge_first_live.after(
        tmp_path, "codex", {"tool_use_id": "read-1", "tool_response": {"exit_code": 0}}
    )
    assert knowledge_first_store.read(tmp_path, "codex", "chat").value.searched
    assert knowledge_first_store.read(tmp_path, "codex", "chat").epoch == record.epoch


def test_cursor_tool_output_status_is_authoritative_for_read_completion(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        knowledge_first_live, "_context", lambda *args: ("chat", tmp_path)
    )
    monkeypatch.setattr(
        knowledge_first_live, "_classify", lambda *args: "knowledge_read"
    )
    knowledge_first_store.begin_prompt(tmp_path, "cursor", "chat")
    payload = {
        "conversation_id": "chat",
        "tool_use_id": "read-cursor",
        "tool_name": "Read",
    }
    knowledge_first_live.before(
        tmp_path, "cursor", payload, rules.make_call("Read", {}, kind="read")
    )
    knowledge_first_live.after(
        tmp_path,
        "cursor",
        {**payload, "tool_output": json.dumps({"exitCode": 1, "stdout": ""})},
    )
    assert not knowledge_first_store.read(tmp_path, "cursor", "chat").value.searched
    knowledge_first_live.before(
        tmp_path, "cursor", payload, rules.make_call("Read", {}, kind="read")
    )
    knowledge_first_live.after(
        tmp_path,
        "cursor",
        {**payload, "tool_output": json.dumps({"exitCode": 0, "stdout": "ok"})},
    )
    assert knowledge_first_store.read(tmp_path, "cursor", "chat").value.searched
    assert (
        hook_bridge.post_tool_response(
            "cursor", {"tool_output": json.dumps({"stdout": "ok"})}
        )
        is None
    )


def test_live_stale_store_never_denies_and_fresh_reminder_is_once(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        knowledge_first_live, "_context", lambda *args: ("chat", tmp_path)
    )
    monkeypatch.setattr(
        knowledge_first_live, "_classify", lambda *args: "external_read"
    )
    monkeypatch.setattr(
        knowledge_first_live.freshness, "verified_fresh", lambda *args: False
    )
    knowledge_first_store.begin_prompt(tmp_path, "codex", "chat")
    call = rules.make_call("Read", {}, kind="read")
    stale = knowledge_first_live.before(tmp_path, "codex", {}, call)
    assert stale is not None and stale.allowed and "empty" in stale.reason
    assert knowledge_first_live.before(tmp_path, "codex", {}, call) is None
    monkeypatch.setattr(
        knowledge_first_live.freshness, "verified_fresh", lambda *args: True
    )
    assert not knowledge_first_live.before(tmp_path, "codex", {}, call).allowed
    assert knowledge_first_live.before(tmp_path, "codex", {}, call) is None
