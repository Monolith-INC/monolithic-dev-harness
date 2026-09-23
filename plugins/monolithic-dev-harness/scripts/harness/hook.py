#!/usr/bin/env python3
"""Single hook entry point for Claude Code and Cursor.

    hook.py --host claude --event pre-tool   (Claude PreToolUse)
    hook.py --host claude --event prompt     (Claude UserPromptSubmit)
    hook.py --host cursor --event pre-tool   (Cursor preToolUse)
    hook.py --host cursor --event shell      (Cursor beforeShellExecution)
    hook.py --host cursor --event mcp        (Cursor beforeMCPExecution)
    hook.py --host cursor --event prompt     (Cursor beforeSubmitPrompt)

Pre-tool events run the harness rules first. If they allow the call, Claude and Cursor
`preToolUse` payloads continue to the codex-workflows policy runtime (branch template, work-item
key, state, spec prerequisites, completion evidence, protected branches, stack merge order).
Prompt events are the only place approvals and manual-check evidence are recorded.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
for entry in (PLUGIN_ROOT, PLUGIN_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from harness import gitstate, rules, state  # noqa: E402
from harness.config import POLICY_RELATIVE_PATH, PolicyError, load_policy  # noqa: E402

APPROVE_RE = re.compile(
    r"\b(?:approve|aprovo|aprovado|aprovar)\s+(HB-[A-Z0-9]{4,12})\b", re.IGNORECASE
)
REVOKE_RE = re.compile(r"\bharness\s+revoke\b", re.IGNORECASE)
MANUAL_RE = re.compile(
    r"\bharness\s+manual-check\s+([A-Za-z0-9._-]{1,60})\s+ok\b", re.IGNORECASE
)


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
    if rules.is_write_class(call):
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
    if not (repo / POLICY_RELATIVE_PATH).is_file():
        # Not a governed repository: the harness is opt-in per repo (bootstrap writes the policy).
        _emit_decision(host, rules.Decision.allow())
        return 0
    try:
        policy = load_policy(repo)
        decision = rules.evaluate(call, repo, policy)
    except (PolicyError, gitstate.GitError, OSError, ValueError, KeyError) as exc:
        return _fail(host, call, f"harness rules could not run: {exc}")
    if not decision.allowed:
        _emit_decision(host, decision)
        return 0
    if host == "claude" or event == "pre-tool":
        return _delegate_to_workflow_policy(host, payload, call)
    _emit_decision(host, decision)
    return 0


def handle_prompt(host: str, payload: dict[str, Any]) -> int:
    prompt = payload.get("prompt") or payload.get("user_prompt") or ""
    repo = _workspace(payload)
    notes: list[str] = []
    if not (repo / POLICY_RELATIVE_PATH).is_file():
        if host == "cursor":
            print(json.dumps({"continue": True}))
        return 0
    try:
        window = int(load_policy(repo).get("approvals", {}).get("window_minutes", 20))
    except (PolicyError, ValueError):
        window = 20
    if REVOKE_RE.search(prompt):
        notes.append(
            f"[harness] revoked {state.revoke_approvals(repo)} open approval window(s)."
        )
    for approval_id in dict.fromkeys(m.upper() for m in APPROVE_RE.findall(prompt)):
        state.open_approval(repo, approval_id, window)
        notes.append(
            f"[harness] approval {approval_id} recorded; tracker/SCM writes are open for {window} minutes."
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude", "cursor"), required=True)
    parser.add_argument(
        "--event", choices=("pre-tool", "prompt", "shell", "mcp"), required=True
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
    return handle_pre_tool(args.host, args.event, payload)


if __name__ == "__main__":
    raise SystemExit(main())
