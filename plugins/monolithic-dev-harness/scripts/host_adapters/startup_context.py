"""Bind a conversation only to an armed, successful startup from the trusted host.

The pre-tool guard runs before arming. A post-tool event must supply completion evidence from
that exact invocation; arbitrary shell text, old output, and an unarmed call bind nothing.
"""

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from core.result import Ok, Result, attempt, bind, err, fmap, require
from harness import commands, decisions, startup_receipts, state, work_sessions
from host_adapters import hook_bridge, native_session_id, work_session_context


def invocation(command: str, cwd: Path) -> startup_receipts.Invocation | None:
    match commands.harness_args(command, cwd):
        case ("begin", *args) if args.count("--new") <= 1:
            match commands.option(tuple(args), "--request"):
                case str() as request:
                    return startup_receipts.Invocation(
                        request,
                        commands.option(tuple(args), "--session"),
                        "--new" in args,
                    )
        case _:
            pass
    return None


def _arm_path(repo: Path, host: str, conversation: str) -> Path:
    return (
        repo
        / work_session_context.ROOT
        / host
        / (hashlib.sha256(conversation.encode()).hexdigest() + "-begin.json")
    )


def arm(
    repo: Path, host: str, payload: dict, command: str, cwd: Path
) -> Result[object]:
    match (
        invocation(command, cwd),
        native_session_id(host, payload),
        hook_bridge.question_id(payload),
    ):
        case (
            startup_receipts.Invocation() as requested,
            str() as conversation,
            str() as call_id,
        ) if conversation and call_id:
            return attempt(
                lambda: state.write_json(
                    _arm_path(repo, host, conversation),
                    {
                        "tool_id": call_id,
                        "command": command,
                        "invocation": asdict(requested),
                        "created": datetime.now(UTC).isoformat(),
                        "consumed": False,
                    },
                ),
                "startup_binding_unwritable",
                "prepare startup conversation binding",
                OSError,
            )
        case startup_receipts.Invocation(), _, _ if host in ("codex", "claude"):
            return err(
                "startup_identity_missing",
                "the host did not supply a conversation and tool-call identity for startup",
            )
        case _:
            return Ok(None)


def complete(repo: Path, host: str, payload: dict) -> Result[str | None]:
    match native_session_id(host, payload), hook_bridge.question_id(payload):
        case str() as conversation, str() as call_id if conversation and call_id:
            return _complete_at(repo, host, payload, conversation, call_id)
        case _:
            return Ok(None)


def _complete_at(
    repo: Path, host: str, payload: dict, conversation: str, call_id: str
) -> Result[str | None]:
    call = hook_bridge.parse_tool_call(host, "startup", payload)
    match (
        invocation(call.command, Path(call.cwd or repo)),
        state.read_json(_arm_path(repo, host, conversation)),
    ):
        case startup_receipts.Invocation() as requested, {
            "tool_id": armed_id,
            "command": command,
            "invocation": armed_request,
            "created": str() as created,
            "consumed": False,
        } as armed if (
            call.kind == "shell"
            and armed_id == call_id
            and command == call.command
            and armed_request == asdict(requested)
        ):
            return bind(
                _output(payload.get("tool_response")),
                lambda output: _bind_output(
                    repo, host, conversation, requested, output, created, armed
                ),
            )
        case startup_receipts.Invocation(), _:
            return bind(_output(payload.get("tool_response")), _unarmed_output)
        case _:
            return Ok(None)


def _unarmed_output(output: object) -> Result[str | None]:
    match output:
        case {"startup_receipt": str()}:
            return err(
                "startup_binding_unarmed",
                "startup has no matching unused host invocation; preserve the prior binding",
            )
        case _:
            return Ok(None)


def _output(response: object) -> Result[dict | None]:
    match response:
        case str() as text:
            return bind(
                attempt(
                    lambda: json.loads(text),
                    "startup_response_invalid",
                    "startup tool response",
                    ValueError,
                ),
                _output,
            )
        case {"exit_code": code} if code != 0:
            return Ok(None)
        case {"interrupted": True} | {"isError": True}:
            return Ok(None)
        case {"stdout": str() as text} | {"output": str() as text}:
            return attempt(
                lambda: json.loads(text),
                "startup_response_invalid",
                "startup command output",
                ValueError,
            )
        case _:
            return Ok(None)


def _bind_output(
    repo: Path,
    host: str,
    conversation: str,
    requested: startup_receipts.Invocation,
    output: object,
    created: str,
    armed: dict,
) -> Result[str | None]:
    match output:
        case {"session_id": str() as identifier, "startup_receipt": str() as receipt}:
            return bind(
                _receipt(repo, identifier, receipt),
                lambda saved: bind(
                    require(
                        saved.get("invocation") == asdict(requested)
                        and saved.get("result")
                        == {
                            key: value
                            for key, value in output.items()
                            if key != "startup_receipt"
                        }
                        and saved.get("created", "") >= created
                        and saved.get("id") == receipt
                        and saved.get("session_id") == identifier
                        and saved.get("version") == 1
                        and work_sessions.current(repo) == identifier,
                        "startup_binding_invalid",
                        "startup completion does not match the armed selection",
                    ),
                    lambda _: _bind_selected(
                        repo, host, conversation, identifier, receipt, armed
                    ),
                ),
            )
        case _:
            return Ok(None)


def _receipt(repo: Path, identifier: str, receipt: str) -> Result[dict]:
    return bind(
        attempt(
            lambda: state.safe_name(receipt),
            "startup_binding_invalid",
            "invalid completion receipt",
            ValueError,
        ),
        lambda safe: bind(
            require(
                safe.startswith("BS-"),
                "startup_binding_invalid",
                "invalid completion receipt",
            ),
            lambda _: bind(
                work_sessions.require_active(repo, identifier),
                lambda selected: _saved_receipt(
                    state.read_json(selected.folder / "startups" / f"{safe}.json")
                ),
            ),
        ),
    )


def _saved_receipt(saved: dict | None) -> Result[dict]:
    match saved:
        case dict():
            return Ok(saved)
        case _:
            return err(
                "startup_binding_invalid",
                "no protected startup completion receipt was saved",
            )


def _bind_selected(
    repo: Path, host: str, conversation: str, identifier: str, receipt: str, armed: dict
) -> Result[str | None]:
    return bind(
        work_session_context.resolve_session(repo, host, conversation),
        lambda current: _consume_or_bind(
            repo, host, conversation, identifier, receipt, armed, current
        ),
    )


def _consume_or_bind(
    repo: Path,
    host: str,
    conversation: str,
    identifier: str,
    receipt: str,
    armed: dict,
    current: str | None,
) -> Result[str | None]:
    match work_session_context.startup_consumed(repo, host, conversation, receipt):
        case True:
            return _finish_arm(repo, host, conversation, armed, current)
        case False:
            return bind(
                require(
                    not decisions.blocking(repo, current)
                    or work_session_context.recovery_allowed(
                        repo, current, (identifier, "begin")
                    ),
                    "decision_pending",
                    "answer the pending question before switching work",
                ),
                lambda _: bind(
                    work_session_context.bind_session(
                        repo, host, conversation, identifier, startup_receipt=receipt
                    ),
                    lambda selected: _finish_arm(
                        repo, host, conversation, armed, selected
                    ),
                ),
            )


def _finish_arm(
    repo: Path, host: str, conversation: str, armed: dict, selected: str | None
) -> Result[str | None]:
    return fmap(
        attempt(
            lambda: state.write_json(
                _arm_path(repo, host, conversation), {**armed, "consumed": True}
            ),
            "startup_binding_unwritable",
            "complete startup binding",
            OSError,
        ),
        lambda _: selected,
    )
