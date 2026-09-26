#!/usr/bin/env python3
"""Single hook entry point for Claude Code and Cursor.

    hook.py --host claude --event pre-tool   (Claude PreToolUse)
    hook.py --host claude --event prompt     (Claude UserPromptSubmit)
    hook.py --host claude --event ask        (Claude PreToolUse on AskUserQuestion)
    hook.py --host claude --event answer     (Claude PostToolUse on AskUserQuestion)
    hook.py --host cursor --event pre-tool   (Cursor preToolUse)
    hook.py --host cursor --event shell      (Cursor beforeShellExecution)
    hook.py --host cursor --event mcp        (Cursor beforeMCPExecution)
    hook.py --host cursor --event prompt     (Cursor beforeSubmitPrompt)

Pre-tool events run the harness rules first. If they allow the call, Claude and Cursor
`preToolUse` payloads continue to the workflow policy runtime (branch template, work-item
key, state, spec prerequisites, completion evidence, protected branches).
Prompt events record approvals, manual-check evidence, and tracker trust from what the user typed; answer events
record an approval from the user clicking `Approve` on a question. Ask events send a question back
to be rewritten when it is not plain enough to show a person.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
for entry in (PLUGIN_ROOT, PLUGIN_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from core.result import Err, Ok  # noqa: E402
from harness import (  # noqa: E402
    gitstate,
    questions,
    rules,
    settings,
    state,
    tracker_policy,
)

# The hosts give the hook 15 seconds and treat a timeout as "no decision", which lets the call
# through. The rules get less than that, and running out counts as a failure.
RULES_BUDGET_SECONDS = 10


class _OutOfTime(Exception):
    pass


def _out_of_time(_signum: int, _frame: Any) -> None:
    raise _OutOfTime(f"the rules took longer than {RULES_BUDGET_SECONDS}s")


APPROVE_RE = re.compile(
    r"\b(?:approve|aprovo|aprovado|aprovar)\s+(HB-[A-Z0-9]{4,12})\b", re.IGNORECASE
)
REVOKE_RE = re.compile(r"\bharness\s+revoke\b", re.IGNORECASE)
MANUAL_RE = re.compile(
    r"\bharness\s+manual-check\s+([A-Za-z0-9._-]{1,60})\s+ok\b", re.IGNORECASE
)
TRUST_RE = re.compile(
    r"\bharness\s+trust-tracker\s+([a-z][a-z0-9-]{0,63})\s+([0-9a-f]{12,64})\b",
    re.IGNORECASE,
)
UNTRUST_RE = re.compile(
    r"\bharness\s+untrust-tracker\s+([a-z][a-z0-9-]{0,63})\b", re.IGNORECASE
)
DEFAULT_WINDOW_MINUTES = 20


def _workspace(payload: dict[str, Any]) -> Path:
    candidates = [
        payload.get("cwd"),
        *(payload.get("workspace_roots") or []),
        os.environ.get("CLAUDE_PROJECT_DIR"),
        os.environ.get("CURSOR_PROJECT_DIR"),
        os.getcwd(),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate and Path(candidate).is_dir():
            start = Path(candidate)
            return gitstate.repo_root(start) or start
    return Path.cwd()


def _tool_call(host: str, event: str, payload: dict[str, Any]) -> rules.ToolCall:
    cwd = str(payload.get("cwd") or "")
    if host == "cursor" and event == "shell":
        return rules.make_call(
            "Shell", {"command": payload.get("command", "")}, cwd=cwd
        )
    tool_input = (
        payload.get("tool_input")
        or payload.get("toolInput")
        or payload.get("input")
        or {}
    )
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except json.JSONDecodeError:
            tool_input = {"raw": tool_input}
    name = (
        payload.get("tool_name") or payload.get("toolName") or payload.get("tool") or ""
    )
    server = payload.get("server") or payload.get("server_name") or ""
    return rules.make_call(
        str(name),
        tool_input if isinstance(tool_input, dict) else {},
        str(server),
        cwd=cwd,
    )


def _emit_decision(host: str, decision: rules.Decision) -> None:
    if host == "claude":
        if decision.allowed:
            return
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": decision.reason,
                    }
                }
            )
        )
        return
    response: dict[str, Any] = {"permission": "allow" if decision.allowed else "deny"}
    if not decision.allowed:
        response["user_message"] = decision.reason
        response["agent_message"] = decision.reason
    print(json.dumps(response))


def _delegate_to_workflow_policy(
    host: str, payload: dict[str, Any], call: rules.ToolCall
) -> int:
    os.environ["WORKFLOW_HOOK_CLIENT"] = host
    try:
        from scripts.hook_runtime import run
    except (
        Exception
    ) as exc:  # the runtime is part of this plugin; failing to import is a defect
        return _fail(host, call, f"workflow policy runtime unavailable: {exc}")
    try:
        return run(host, payload)
    except Exception as exc:
        return _fail(host, call, f"workflow policy runtime failed: {exc}")


def _fail(host: str, call: rules.ToolCall, message: str) -> int:
    """Fail closed for writes, open for reads, so a broken rule never silently permits a write."""
    try:
        write_class = rules.is_write_class(call)
    except Exception:
        # The classifier broke too: only calls that plainly cannot write go through.
        write_class = call.name not in rules.READ_ONLY_TOOLS
    if write_class:
        _emit_decision(
            host,
            rules.Decision.deny(
                "harness-error",
                f"{message}. Write-class calls are blocked until this is fixed.",
            ),
        )
    else:
        _emit_decision(host, rules.Decision.allow())
    return 0


def handle_pre_tool(host: str, event: str, payload: dict[str, Any]) -> int:
    call = _tool_call(host, event, payload)
    repo = _workspace(payload)
    if not settings.governed(repo):
        # Not a governed repository: the harness is opt-in per repo (bootstrap writes the settings).
        _emit_decision(host, rules.Decision.allow())
        return 0
    timed = hasattr(signal, "SIGALRM")
    if timed:
        signal.signal(signal.SIGALRM, _out_of_time)
        signal.setitimer(signal.ITIMER_REAL, RULES_BUDGET_SECONDS)
    try:
        loaded = settings.load(repo)
        match loaded:
            case Err(failure):
                return _fail(
                    host, call, f"the settings cannot be used: {failure.message}"
                )
            case Ok(chosen):
                decision = rules.evaluate(
                    call, repo, chosen, tracker_policy.build(repo, loaded)
                )
    except (Exception, _OutOfTime) as exc:
        # Any failure of the rules, including a crash or running out of time, blocks writes.
        # A hook that exits with an error or times out is not a block: the host lets the call run.
        return _fail(
            host, call, f"harness rules could not run: {type(exc).__name__}: {exc}"
        )
    finally:
        if timed:
            signal.setitimer(signal.ITIMER_REAL, 0)
    if not decision.allowed:
        _emit_decision(host, decision)
        return 0
    if host == "claude" or event == "pre-tool":
        return _delegate_to_workflow_policy(host, payload, call)
    _emit_decision(host, decision)
    return 0


def _pin_approved_notes(repo: Path, approval_id: str) -> str:
    """Pin the notes marked approved in the artifacts path to this approval; a note for the user."""
    # Imported here so only approvals pay for loading the artifacts-path reader.
    from harness import local_artifacts

    try:
        notes = local_artifacts.approved_notes(repo)
        state.pin_notes(repo, approval_id, notes)
    except (OSError, ValueError) as exc:
        return f" Approved plan and spec notes were NOT pinned: {exc}"
    if not notes:
        return ""
    return (
        f" It also covers {len(notes)} plan or spec note(s) marked approved, as they read now;"
        " editing one needs a new approval."
    )


def _window(repo: Path) -> int:
    match settings.load(repo):
        case Ok(chosen):
            return chosen.approval_minutes
        case Err():
            return DEFAULT_WINDOW_MINUTES


def _trust_notes(repo: Path, prompt: str) -> list[str]:
    """Trust or untrust onboarded trackers the user named, each pinned to the digest they typed."""
    from integrations import registry, trust

    trusted = [
        (
            name,
            trust.trust(
                repo, name, repo / registry.ONBOARDED_RELATIVE_PATH / name, digest
            ),
        )
        for name, digest in TRUST_RE.findall(prompt)
    ]
    untrusted = [
        (name, trust.untrust(repo, name)) for name in UNTRUST_RE.findall(prompt)
    ]
    return [
        *(
            f"[harness] tracker {name} is trusted as it reads now (digest {result.value[:12]})."
            if isinstance(result, Ok)
            else f"[harness] tracker {name} was NOT trusted: {result.failure.message}"
            for name, result in trusted
        ),
        *(f"[harness] tracker {name} is no longer trusted." for name, _ in untrusted),
    ]


def handle_prompt(host: str, payload: dict[str, Any]) -> int:
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    repo = _workspace(payload)
    notes: list[str] = []
    if not settings.governed(repo):
        if host == "cursor":
            print(json.dumps({"continue": True}))
        return 0
    window = _window(repo)
    notes.extend(_trust_notes(repo, prompt))
    if REVOKE_RE.search(prompt):
        notes.append(
            f"[harness] revoked {state.revoke_approvals(repo)} open approval window(s)."
        )
    for approval_id in dict.fromkeys(m.upper() for m in APPROVE_RE.findall(prompt)):
        state.open_approval(repo, approval_id, window)
        notes.append(
            f"[harness] approval {approval_id} recorded; tracker/SCM writes are open for {window} minutes."
            + _pin_approved_notes(repo, approval_id)
        )
    for name in MANUAL_RE.findall(prompt):
        try:
            tree = gitstate.index_tree(repo)
        except gitstate.GitError as exc:
            notes.append(f"[harness] manual check {name} NOT recorded: {exc}")
            continue
        state.record_manual(repo, name, tree, prompt[:500])
        notes.append(
            f"[harness] manual check {name} recorded for staged tree {tree[:12]}."
        )
    if host == "cursor":
        print(json.dumps({"continue": True}))
    elif notes:
        print("\n".join(notes))
    return 0


def _governed(payload: dict[str, Any]) -> Path | None:
    repo = _workspace(payload)
    return repo if settings.governed(repo) else None


def handle_ask(payload: dict[str, Any]) -> int:
    """Before a question is shown: send it back if a person would have to decode it."""
    repo = _governed(payload)
    if repo is None:
        return 0
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    found = questions.problems(tool_input)
    if found:
        _emit_decision(
            "claude",
            rules.Decision.deny("plain-questions", questions.rewrite_reason(found)),
        )
        return 0
    tool_use_id = str(payload.get("tool_use_id") or "")
    if tool_use_id:
        state.mark_asked(repo, questions.marker_name(tool_use_id))
    return 0


def handle_answer(payload: dict[str, Any]) -> int:
    """After the user answers: an `Approve` click opens an approval window."""
    repo = _governed(payload)
    tool_use_id = str(payload.get("tool_use_id") or "")
    if repo is None or not tool_use_id:
        return 0
    if not state.take_asked(repo, questions.marker_name(tool_use_id)):
        return 0  # the question never passed the check, so its answer opens nothing
    tool_input = payload.get("tool_input")
    approved = questions.approval(
        tool_input if isinstance(tool_input, dict) else {}, payload.get("tool_response")
    )
    if approved is None:
        return 0
    window = _window(repo)
    approval_id = questions.approval_id(tool_use_id)
    state.open_approval(repo, approval_id, window, question=approved[0])
    pinned = _pin_approved_notes(repo, approval_id)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"[harness] the user approved; approval {approval_id} is open "
                    f"for {window} minutes. Make only the writes the question described."
                    + pinned,
                }
            }
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude", "cursor"), required=True)
    parser.add_argument(
        "--event",
        choices=("pre-tool", "prompt", "shell", "mcp", "ask", "answer"),
        required=True,
    )
    args = parser.parse_args(argv)
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if args.event == "prompt":
        return handle_prompt(args.host, payload)
    if args.event in ("ask", "answer"):
        try:
            return (
                handle_ask(payload) if args.event == "ask" else handle_answer(payload)
            )
        except Exception:
            # A question is not a write: a broken check shows it as asked. Its answer then opens
            # nothing, because only a question the check let through is honoured.
            return 0
    try:
        return handle_pre_tool(args.host, args.event, payload)
    except Exception as exc:
        # Last resort: anything that escaped the rules still fails closed.
        call = rules.make_call(
            str(payload.get("tool_name") or payload.get("toolName") or "Bash"), {}
        )
        return _fail(
            args.host, call, f"harness hook failed: {type(exc).__name__}: {exc}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
