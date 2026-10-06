#!/usr/bin/env python3
"""Single hook entry point for Claude Code, Cursor, and Codex.

    hook.py --host claude --event pre-tool   (Claude PreToolUse)
    hook.py --host claude --event prompt     (Claude UserPromptSubmit)
    hook.py --host claude|codex --event ask    (question-tool PreToolUse)
    hook.py --host claude|codex --event answer (question-tool PostToolUse)
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
    adoption,
    decisions,
    gitstate,
    globs,
    questions,
    rules,
    settings,
    state,
    tracker_policy,
    workflow,
)
from host_adapters import hook_bridge, work_session_context  # noqa: E402
from host_adapters.answer_recovery import recorded_answer  # noqa: E402
from host_adapters.interactions import (  # noqa: E402
    decision_exchange,
    normalize_question,
    prompt_answer,
    question_transport,
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
# Cursor has no question buttons: the user's whole message is the reply, so a quoted or negated
# mention ("don't use HT-1A2B3C yet") never counts.
TRACKER_REPLY_RE = re.compile(
    r"\s*(approve|aprovo|aprovado|aprovar|use|usar)\s+(HT-[A-Z0-9]{6})\s*[.!]?\s*",
    re.IGNORECASE,
)
STOP_TRUSTING_RE = re.compile(r"\s*stop\s+trusting\s+(.+?)\s*[.!]?\s*", re.IGNORECASE)
# The whole message, so a quoted or negated mention ("don't run harness suspend") never counts.
SUSPEND_RE = re.compile(r"\s*harness\s+(suspend|resume)\s*[.!]?\s*", re.IGNORECASE)
DEFAULT_WINDOW_MINUTES = 20


def _workspace(payload: dict[str, Any], host: str = "claude") -> Path:
    for candidate in hook_bridge.workspace_candidates(host, payload):
        if isinstance(candidate, str) and candidate and Path(candidate).is_dir():
            start = Path(candidate)
            return gitstate.repo_root(start) or start
    return Path.cwd()


def _tool_call(host: str, event: str, payload: dict[str, Any]) -> rules.ToolCall:
    return hook_bridge.parse_tool_call(host, event, payload)


def _emit_decision(host: str, decision: rules.Decision) -> None:
    match hook_bridge.format_pre_tool(host, decision):
        case str(output):
            print(output)
        case None:
            return


def _delegate_to_workflow_policy(
    host: str, payload: dict[str, Any], call: rules.ToolCall, repo: Path
) -> int:
    os.environ["WORKFLOW_HOOK_CLIENT"] = host
    try:
        from scripts.hook_runtime import run
    except (
        Exception
    ) as exc:  # the runtime is part of this plugin; failing to import is a defect
        return _fail(host, call, f"workflow policy runtime unavailable: {exc}")
    try:
        return run(host, payload, str(repo))
    except Exception as exc:
        return _fail(host, call, f"workflow policy runtime failed: {exc}")


def _fail(host: str, call: rules.ToolCall, message: str) -> int:
    """Fail closed for writes, open for reads, so a broken rule never silently permits a write."""
    try:
        write_class = rules.is_write_class(call)
    except Exception:
        # The classifier broke too: only calls that plainly cannot write go through.
        write_class = call.kind != "read"
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
    repo = _workspace(payload, host)
    entry = rules.rule_hook_entry(call)
    if not entry.allowed:
        _emit_decision(host, entry)
        return 0
    # The user released the checks from their own prompt; only their records stay protected.
    suspended = state.harness_mode(repo) == "suspended"
    context = work_session_context.for_payload(repo, host, payload)
    request = (
        work_session_context.requested(call.command, Path(call.cwd or repo))
        if call.kind == "shell"
        else None
    )
    held = None if suspended else _held(repo, call, context, request)
    if held is not None:
        _emit_decision(host, held)
        return 0
    work_session_id = context.value if isinstance(context, Ok) else None
    if not settings.governed(repo):
        # Not a governed repository: the harness is opt-in per repo (bootstrap writes the settings).
        _bind(repo, host, payload, work_session_id, request)
        _emit_decision(host, rules.Decision.allow())
        return 0
    timed = hasattr(signal, "SIGALRM")
    if timed:
        signal.signal(signal.SIGALRM, _out_of_time)
        signal.setitimer(signal.ITIMER_REAL, RULES_BUDGET_SECONDS)
    try:
        loaded = settings.load(repo)
        match suspended, loaded:
            case True, _:
                decision = rules.rule_human_owned(call, repo)
            case False, Err(failure):
                return _fail(
                    host, call, f"the settings cannot be used: {failure.message}"
                )
            case False, Ok(chosen):
                decision = rules.evaluate(
                    call,
                    repo,
                    chosen,
                    tracker_policy.build(repo, loaded),
                    work_session_id,
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
    if decision.allowed:
        _bind(repo, host, payload, work_session_id, request)
    if not decision.allowed or suspended:
        _emit_decision(host, decision)
        return 0
    if hook_bridge.delegates_workflow_policy(host, event):
        return _delegate_to_workflow_policy(host, payload, call, repo)
    _emit_decision(host, decision)
    return 0


def _held(
    repo: Path,
    call: rules.ToolCall,
    context: Any,
    request: tuple[str, str] | None,
) -> rules.Decision | None:
    """Why a write must wait: the conversation's session or a pending decision, checked once."""
    if not rules.is_write_class(call) or _diagnostic_read(call, repo):
        return None
    match context:
        case Err(failure):
            return rules.Decision.deny("work-session-context", failure.message)
        case Ok(current):
            pass
    mismatch = work_session_context.mismatch(current, request)
    if mismatch is not None:
        return rules.Decision.deny("work-session-mismatch", mismatch.message)
    if decisions.blocking(repo, current) and not (
        decisions.status_command(call.command, Path(call.cwd or repo))
        or decisions.fallback_command(call.command, Path(call.cwd or repo))
    ):
        return rules.Decision.deny(
            "decision-pending",
            "Wait for the human's answer before continuing this run.",
        )
    return None


def _diagnostic_read(call: rules.ToolCall, repo: Path) -> bool:
    """Let proven file reads through the waiting gate, without skipping other rules."""
    match call.kind:
        case "shell":
            return _has_no_shell_writes(
                rules.shellscan.scan(call.command, str(call.cwd or repo), repo)
            )
        case _:
            return False


def _has_no_shell_writes(writes: rules.shellscan.ShellWrites) -> bool:
    return not (writes.targets or writes.trees or writes.unresolved)


def _bind(
    repo: Path,
    host: str,
    payload: dict[str, Any],
    current: str | None,
    request: tuple[str, str] | None,
) -> None:
    """Bind the conversation to the session an allowed command chose; a failure binds nothing."""
    from host_adapters import native_session_id

    work_session_context.bind_requested(
        repo, host, native_session_id(host, payload), current, request
    )


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


def _work_session(repo: Path, host: str, payload: dict[str, Any]) -> str | None:
    """The work session this conversation is bound to; `None` when there is none to find."""
    match work_session_context.for_payload(repo, host, payload):
        case Ok(found):
            return found
        case Err():
            return None


def _window(repo: Path) -> int:
    match settings.load(repo):
        case Ok(chosen):
            return chosen.approval_minutes
        case Err():
            return DEFAULT_WINDOW_MINUTES


def _tracker_act(
    repo: Path, action: str, name: str, pinned: str, current: str | None = None
) -> str:
    """Trust, select, or stop trusting one onboarded tracker, as the user just chose.

    `pinned` is the folder's version when the user was asked; if it changed since, nothing happens.
    `current` is the folder's version now, when the caller already hashed it.
    """
    from integrations import onboarding, registry, trust

    folder = repo / registry.ONBOARDED_RELATIVE_PATH / name
    manifest = registry.read_manifest(folder, "onboarded")
    label = manifest.value.label if isinstance(manifest, Ok) else name
    if current is None:
        current = trust.digest(folder) if folder.is_dir() else ""
    if action != "untrust" and current != pinned:
        return (
            f"[harness] the {label} tracker changed after the user was asked, so nothing was done. "
            "Show them what changed and ask again."
        )
    match action:
        case "trust":
            result = trust.trust(repo, name, folder, pinned)
            return (
                f"[harness] the user trusts the {label} tracker as it read when they were asked."
                if isinstance(result, Ok)
                else f"[harness] the {label} tracker was NOT trusted: {result.failure.message}"
            )
        case "select":
            chosen = onboarding.select(repo, name)
            return (
                f"[harness] the project now uses the {label} tracker; the settings were updated."
                if isinstance(chosen, Ok)
                else f"[harness] the {label} tracker was NOT selected: {chosen.failure.message}"
            )
        case _:
            removed = trust.untrust(repo, name)
            return (
                f"[harness] the {label} tracker is no longer trusted."
                if isinstance(removed, Ok)
                else f"[harness] the {label} tracker is STILL trusted: {removed.failure.message}"
            )


def _tracker_reply_notes(repo: Path, prompt: str) -> list[str]:
    """Cursor's typed replies, each the whole message.

    `approve HT-…` trusts and `use HT-…` selects the version whose short id the user was shown;
    `stop trusting <tracker>` withdraws trust by name.
    """
    from integrations import onboarding

    reply = TRACKER_REPLY_RE.fullmatch(prompt)
    if reply is not None:
        verb, short = reply.groups()
        found = onboarding.by_short_id(repo, short)
        if found is None:
            return [
                f"[harness] no staged tracker matches {short.upper()}; it may have changed since "
                "it was shown. Show the tracker again and ask."
            ]
        manifest, digest = found
        action = "select" if verb.lower() in ("use", "usar") else "trust"
        return [_tracker_act(repo, action, manifest.name, digest, current=digest)]
    stop = STOP_TRUSTING_RE.fullmatch(prompt)
    name = onboarding.named_in(repo, stop.group(1)) if stop is not None else None
    return [_tracker_act(repo, "untrust", name, "")] if name is not None else []


def _switch_harness(repo: Path, operation: str) -> str:
    mode = {"suspend": "suspended", "resume": "active"}[operation]
    try:
        state.set_harness_mode(repo, mode)
    except OSError as exc:
        return f"[harness] the harness checks were NOT {mode}: {exc}"
    if mode == "active":
        return "[harness] every harness check applies again in this repository."
    return (
        "[harness] every harness check is suspended in this repository at the user's request; "
        "edits to the harness's own records stay blocked. Type `harness resume` to restore them."
    )


def _print_prompt(host: str, notes: list[str]) -> None:
    if output := hook_bridge.format_prompt(host, notes):
        print(output)


def handle_prompt(host: str, payload: dict[str, Any]) -> int:
    prompt = hook_bridge.prompt_text(payload)
    repo = _workspace(payload, host)
    match SUSPEND_RE.fullmatch(prompt):
        case re.Match() as switch:
            _print_prompt(host, [_switch_harness(repo, switch.group(1).lower())])
            return 0
        case _:
            pass
    context = work_session_context.for_payload(repo, host, payload)
    if isinstance(context, Err):
        _print_prompt(host, [context.failure.message])
        return 0
    work_session_id = context.value
    match _recover_prompt_answer(repo, host, payload, work_session_id):
        case notes, pending:
            pass
    # Only a reply that picks an offered option answers; anything else is an ordinary prompt.
    reply = (
        prompt_answer(host, prompt, pending)
        if pending
        and not (
            REVOKE_RE.search(prompt)
            or APPROVE_RE.search(prompt)
            or MANUAL_RE.search(prompt)
        )
        else None
    )
    if pending is not None and reply is not None:
        _print_prompt(host, _answer_decision(repo, pending, work_session_id, reply))
        return 0
    if not settings.governed(repo):
        if output := hook_bridge.format_prompt(host, []):
            print(output)
        return 0
    window = _window(repo)
    notes.extend(_tracker_reply_notes(repo, prompt))
    if REVOKE_RE.search(prompt):
        notes.append(
            f"[harness] revoked {state.revoke_approvals(repo)} open approval window(s)."
        )
    for approval_id in dict.fromkeys(m.upper() for m in APPROVE_RE.findall(prompt)):
        state.open_approval(repo, approval_id, window, work_session_id=work_session_id)
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
    if output := hook_bridge.format_prompt(host, notes):
        print(output)
    return 0


def _recover_prompt_answer(
    repo: Path,
    host: str,
    payload: dict[str, Any],
    scope: str | None,
) -> tuple[list[str], decisions.Pending | None]:
    match decisions.pending(repo, scope):
        case decisions.Pending() as pending:
            match recorded_answer(host, payload, pending):
                case tuple() as captured:
                    return (
                        _answer_decision(repo, pending, scope, captured),
                        decisions.pending(repo, scope),
                    )
                case None:
                    return [], pending
        case None:
            return [], None


def _governed(payload: dict[str, Any], host: str = "claude") -> Path | None:
    repo = _workspace(payload, host)
    return repo if settings.governed(repo) else None


def _question_repo(payload: dict[str, Any], host: str) -> Path | None:
    """Prepared onboarding decisions exist before shared repository settings do."""
    match _workspace(payload, host):
        case repo if settings.governed(repo) or decisions.pending(repo) is not None:
            return repo
        case _:
            return None


def handle_ask(host: str, payload: dict[str, Any]) -> int:
    """Before a question is shown: send it back if a person would have to decode it."""
    repo = _question_repo(payload, host)
    if repo is None:
        return 0
    context = work_session_context.for_payload(repo, host, payload)
    if isinstance(context, Err):
        _emit_decision(
            host, rules.Decision.deny("work-session-context", context.failure.message)
        )
        return 0
    work_session_id = context.value
    pending = decisions.pending(repo, work_session_id)
    transport = question_transport(host, str(payload.get("tool_name", "")))
    tool_input = normalize_question(host, hook_bridge.question_input(payload))
    first = (tool_input.get("questions") or [{}])[0]
    preparing = pending is not None and pending.matches_presentation(first, transport)
    if decisions.blocking(repo, work_session_id) and not preparing:
        _emit_decision(
            host,
            rules.Decision.deny(
                "decision-pending",
                "Answer the current question before presenting another.",
            ),
        )
        return 0
    found = questions.problems(tool_input)
    # While suspended only the wording check is off: the checks below pin what a click approves.
    if found and state.harness_mode(repo) != "suspended":
        _emit_decision(
            host,
            rules.Decision.deny("plain-questions", questions.rewrite_reason(found)),
        )
        return 0
    tracker_detail = _tracker_question(repo, tool_input)
    if tracker_detail is None:
        _emit_decision(
            "claude",
            rules.Decision.deny(
                "plain-questions",
                "This question offers a tracker choice but does not name exactly one staged "
                'tracker: name the tracker by its label, for example "Trust the Acme Boards '
                'tracker as I just described it?", so the click applies to that one.',
            ),
        )
        return 0
    manual_detail = _manual_question(repo, tool_input)
    match manual_detail:
        case None:
            _emit_decision(
                "claude",
                rules.Decision.deny(
                    "plain-questions",
                    "A guarded-change approval must apply to exactly one staged manual check. "
                    "Stage only that change, describe what the user should validate, and ask again.",
                ),
            )
            return 0
        case _:
            pass
    adoption_detail = _adoption_question(repo, tool_input)
    match adoption_detail:
        case None:
            _emit_decision(
                "claude",
                rules.Decision.deny(
                    "plain-questions",
                    "An adoption approval must name exactly one current plan id shown by the "
                    "adoption plan command. Show that plan, include its HA id in the question, "
                    "and ask again.",
                ),
            )
            return 0
        case _:
            pass
    detail = {**tracker_detail, **manual_detail, **adoption_detail}
    tool_use_id = hook_bridge.question_id(payload)
    if not tool_use_id:
        return 0
    question = str(first.get("question", ""))
    options = tuple(
        str(option.get("label", ""))
        for option in first.get("options", ())
        if isinstance(option, dict)
    )
    decision_scope = (
        pending.scope if pending is not None and preparing else work_session_id
    )
    result = (
        decisions.bind_question(
            repo,
            pending.id if pending is not None else "",
            tool_use_id,
            question,
            options,
            work_session_id=decision_scope,
        )
        if preparing
        else decisions.begin(
            repo,
            tool_use_id,
            question,
            options,
            transport,
            _artifacts(repo, decision_scope),
            work_session_id=decision_scope,
            allow_free_text=questions.native_routing_question(tool_input)
            and not detail
            and not questions.authorizing_options(options),
        )
    )
    if isinstance(result, Err):
        _emit_decision(
            host, rules.Decision.deny("decision-invalid", result.failure.message)
        )
        return 0
    match preparing, pending:
        case True, decisions.Pending(id=old_id) if old_id != tool_use_id:
            state.take_asked(repo, questions.marker_name(old_id), decision_scope)
        case _:
            pass
    state.mark_asked(repo, questions.marker_name(tool_use_id), detail, decision_scope)
    return 0


def _artifacts(repo: Path, scope: str | None) -> tuple[tuple[str, str], ...]:
    """The reviewed files of the current checkpoint, so a changed one cannot be approved."""
    current = workflow.load(repo, scope)
    return current.value.current.artifacts if isinstance(current, Ok) else ()


def _tracker_question(repo: Path, tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """What a tracker question is about, pinned now: {} for other questions, None if unclear.

    A Trust or Stop trusting question must name one onboarded tracker. "Use it" alone may be about
    anything, a shipped tracker included, so an unmatched one is an ordinary question.
    """
    from integrations import onboarding, registry, trust

    asked = questions.tracker_action(tool_input)
    if asked is None:
        return {}
    actions, text = asked
    name = onboarding.named_in(repo, text)
    if name is None:
        return None if {"trust", "untrust"} & set(actions) else {}
    folder = repo / registry.ONBOARDED_RELATIVE_PATH / name
    return {
        "tracker": name,
        "actions": list(actions),
        "digest": trust.digest(folder) if folder.is_dir() else "",
    }


def _manual_question(repo: Path, tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """Pin one unmet manual guard and the exact staged tree before showing its button."""
    text = questions.manual_signoff(tool_input)
    if text is None:
        return {}
    match text, settings.load(repo):
        case _, Err():
            return None
        case str(), Ok(chosen):
            staged = gitstate.staged_paths(repo)
            tree = gitstate.index_tree(repo)
            guards = tuple(
                guard
                for guard in chosen.guarded_paths
                if guard.kind == "manual"
                and globs.select(staged, [guard.path])
                and not state.has_manual(repo, guard.name, tree)
            )
            match guards:
                case (guard,):
                    return {
                        "manual": {
                            "name": guard.name,
                            "tree": tree,
                            "question": text,
                        }
                    }
                case _:
                    return None


def _adoption_question(repo: Path, tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """Pin the exact persisted continuation plan before showing its approval button."""
    asked = questions.adoption_signoff(tool_input)
    match asked, questions.adoption_requested(tool_input):
        case None, False:
            return {}
        case None, True:
            return None
        case (text, adoption_id), True:
            match adoption.plan_for_question(repo, adoption_id):
                case Ok(found):
                    return {
                        "adoption": {
                            "id": adoption_id,
                            "digest": found.get("digest", ""),
                            "question": text,
                        }
                    }
                case Err():
                    return None


def handle_answer(host: str, payload: dict[str, Any]) -> int:
    """After the user answers a question: record the decision, then what the question pinned."""
    repo = _question_repo(payload, host)
    tool_use_id = hook_bridge.question_id(payload)
    if repo is None or not tool_use_id:
        return 0
    context = work_session_context.for_payload(repo, host, payload)
    if isinstance(context, Err):
        print(hook_bridge.format_answer_context(context.failure.message))
        return 0
    work_session_id = context.value
    pending = decisions.pending(repo, work_session_id)
    decision_scope = pending.scope if pending is not None else work_session_id
    tool_input = normalize_question(host, hook_bridge.question_input(payload))
    if pending is not None and pending.transport == "async":
        return 0  # tool completion is delivery; the reply arrives later as a prompt
    match hook_bridge.answer_response(payload):
        case Err(failure):
            print(
                hook_bridge.format_answer_context(
                    f"[harness] human reply capture failed ({host}, answer): {failure.message}. "
                    "The question remains pending; inspect the host response format."
                    " Quietly re-ask through `harness decision fallback` using the next supported "
                    "method. Preserve the review and choices; do not expose internal errors to the user."
                )
            )
            return 0
        case Ok(response):
            pass
    if pending is not None:
        answered = questions.answer(tool_input, response)
        match answered:
            case None:
                print(
                    hook_bridge.format_answer_context(
                        f"[harness] human reply capture failed ({host}, answer): "
                        "no matching human answer was received. The question remains pending; "
                        "delivery or dismissal does not answer it."
                        " If delivery failed, quietly re-ask through `harness decision fallback`; "
                        "continue the same run once the human answers."
                    )
                )
                return 0
            case _:
                pass
        chosen = next(
            (
                str(option)
                for option in pending.options
                if questions.choice_label(str(option)).casefold()
                == questions.choice_label(answered).casefold()
            ),
            answered,
        )
        result = decisions.resolve(
            repo,
            tool_use_id,
            chosen,
            pending.transport,
            work_session_id=decision_scope,
        )
        if isinstance(result, Err):
            print(
                hook_bridge.format_answer_context(
                    f"[harness] decision not recorded: {result.failure.message}"
                )
            )
            return 0
    note = _apply_marker(
        repo, tool_use_id, decision_scope, work_session_id, tool_input, response
    )
    if note:
        print(hook_bridge.format_answer_context(note))
    return 0


def _answer_decision(
    repo: Path,
    pending: decisions.Pending,
    conversation_scope: str | None,
    reply: tuple[str, str, str],
) -> list[str]:
    """Record a typed or delayed reply, then what it approves; notes for the agent."""
    key, answer, transport = reply
    decision_scope = pending.scope
    match decisions.resolve(
        repo, key, answer, transport, work_session_id=decision_scope
    ):
        case Err(failure):
            return [f"[harness] decision not recorded: {failure.message}"]
        case Ok(found):
            pass
    notes = [f"[harness] human decision recorded: {found['answer']}"]
    match decision_exchange(pending, answer):
        case tool_input, response:
            match _apply_marker(
                repo, key, decision_scope, conversation_scope, tool_input, response
            ):
                case str() as note:
                    return notes + [note]
                case None:
                    pass
    if (
        found.get("approval")
        and questions.choice_label(str(found["answer"])).casefold()
        in questions.APPROVE_LABELS
    ):
        notes.append(
            _open_approval(
                repo,
                questions.approval_id(str(found["id"])),
                str(found.get("question", "")),
                conversation_scope,
            )
        )
    return notes


def _open_approval(
    repo: Path, approval_id: str, question: str, scope: str | None
) -> str:
    """Open a window for the conversation that approved; it covers only that work session."""
    window = _window(repo)
    state.open_approval(repo, approval_id, window, question, work_session_id=scope)
    return (
        f"[harness] the user approved; approval {approval_id} is open for {window} minutes. "
        "Make only the writes the question described."
        + _pin_approved_notes(repo, approval_id)
    )


def _apply_marker(
    repo: Path,
    marker_id: str,
    decision_scope: str | None,
    conversation_scope: str | None,
    tool_input: dict[str, Any],
    response: Any,
) -> str | None:
    """What an answered question pinned when it was asked: adoption, manual check, tracker, or approval."""
    asked = state.take_asked(repo, questions.marker_name(marker_id), decision_scope)
    if asked is None:
        return None  # the question never passed the check, so its answer opens nothing
    match asked.get("adoption"):
        case dict() as plan:
            chosen = questions.adoption_choice(
                tool_input,
                response,
            )
            result = (
                adoption.approve(
                    repo,
                    str(plan.get("id", "")),
                    str(plan.get("digest", "")),
                    str(plan.get("question", "")),
                )
                if chosen
                else None
            )
            match result:
                case Ok():
                    note = (
                        f"[harness] adoption plan {plan.get('id')} approved for its exact content. "
                        "The materialize command may now create the recovery worktree."
                    )
                case Err(failure):
                    note = f"[harness] adoption approval was NOT recorded: {failure.message}"
                case None:
                    note = "[harness] the adoption plan was not approved."
            return note
        case _:
            pass
    match asked.get("manual"):
        case dict() as manual:
            chosen = questions.manual_choice(
                tool_input,
                response,
            )
            current = gitstate.index_tree(repo)
            recorded = chosen and current == manual.get("tree")
            match recorded:
                case True:
                    state.record_manual(
                        repo,
                        str(manual.get("name", "")),
                        current,
                        str(manual.get("question", ""))[:500],
                    )
                    note = (
                        f"[harness] manual check {manual.get('name')} recorded for staged tree "
                        f"{current[:12]}."
                    )
                case False if chosen:
                    note = (
                        "[harness] the staged change changed after the question was shown, so the "
                        "manual check was not recorded. Show the updated change and ask again."
                    )
                case False:
                    note = "[harness] the guarded change was not approved."
            return note
        case _:
            pass
    if asked.get("tracker"):
        chosen = questions.tracker_choice(
            tool_input,
            response,
        )
        note = (
            _tracker_act(repo, chosen, asked["tracker"], asked.get("digest", ""))
            if chosen is not None and chosen in asked.get("actions", ())
            else f"[harness] nothing changed for the {asked['tracker']} tracker."
        )
        return note
    approved = questions.approval(tool_input, response)
    if approved is None:
        return None
    return _open_approval(
        repo, questions.approval_id(marker_id), approved[0], conversation_scope
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude", "cursor", "codex"), required=True)
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
        try:
            return handle_prompt(args.host, payload)
        except Exception as exc:
            # Prompts only record what the user typed; a broken record must not drop the message.
            _print_prompt(
                args.host,
                [
                    "[harness] Your reply could not be recorded. "
                    "The decision remains unconfirmed; read-only diagnosis is available."
                ],
            )
            print(
                f"[harness] human reply capture failed ({args.host}, prompt): "
                f"{type(exc).__name__}. No answer or suspension was confirmed; "
                "inspect the hook configuration and project state.",
                file=sys.stderr,
            )
            return 0
    if args.event in ("ask", "answer"):
        try:
            return (
                handle_ask(args.host, payload)
                if args.event == "ask"
                else handle_answer(args.host, payload)
            )
        except Exception:
            # A question is not a write: a broken check shows it as asked. Its answer then opens
            # nothing, because only a question the check let through is honoured.
            return 0
    try:
        return handle_pre_tool(args.host, args.event, payload)
    except Exception as exc:
        # Last resort: anything that escaped the rules still fails closed.
        call = rules.make_call("unknown", {}, kind="other")
        return _fail(
            args.host, call, f"harness hook failed: {type(exc).__name__}: {exc}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
