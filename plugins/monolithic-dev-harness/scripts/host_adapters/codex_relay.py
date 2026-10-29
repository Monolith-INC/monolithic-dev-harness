"""Recover non-approving relayed choices from Codex-owned session transcripts.

No caller-supplied answer, transcript path or synthetic hook event is accepted. The root must
have observed the exact pending record before delivering its exact native question. A real user
message after successful delivery is the answer; the native tool's acknowledgement is not.
"""

import json
import os
import pwd
import re
from dataclasses import dataclass, replace
from functools import reduce
from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt, bind, err, value_or
from harness import decisions, questions
from host_adapters.interactions import canonical_question_name


@dataclass(frozen=True)
class Exchange:
    observed: bool = False
    call_id: str = ""
    delivered: bool = False
    answer: str = ""
    message_id: str = ""


def recover(repo: Path, scope: str | None = None) -> Result[dict]:
    """Read only the current host's canonical logs, then resolve through normal validation."""
    return _eligible(
        repo,
        scope,
        decisions.record(repo, scope) or {},
        os.environ.get("CODEX_THREAD_ID", ""),
        _session_home(),
    )


def _session_home() -> Path:
    """The desktop host's OS-account log root, independent of caller HOME/CODEX_HOME."""
    return Path(pwd.getpwuid(os.getuid()).pw_dir) / ".codex"


def _eligible(
    repo: Path, scope: str | None, current: dict, session: str, home: Path
) -> Result[dict]:
    match current:
        case {
            "status": "pending",
            "approval": False,
            "native_session_id": str() as origin,
            "instance_id": str() as instance,
        } if (
            origin
            and instance
            and not questions.authorizing_options(tuple(current.get("options", ())))
        ):
            return bind(
                _transcript(home, session),
                lambda rows: bind(
                    _root(rows, session, repo),
                    lambda _: bind(
                        _origin(home, origin, session),
                        lambda _: _resolve(
                            repo,
                            scope,
                            current,
                            session,
                            reduce(
                                lambda exchange, row: _step(exchange, row, current),
                                rows,
                                Exchange(),
                            ),
                        ),
                    ),
                ),
            )
        case _:
            return err(
                "relay_recovery_unavailable",
                "Only a pending, non-approving choice can be recovered from a parent transcript.",
            )


def _transcript(home: Path, session: str) -> Result[tuple[dict, ...]]:
    match re.fullmatch(r"[0-9a-fA-F-]{36}", session):
        case None:
            return err(
                "relay_session_missing",
                "The current native session identity is unavailable.",
            )
        case _:
            return bind(
                attempt(
                    lambda: tuple(
                        home.joinpath("sessions").glob(
                            f"*/*/*/rollout-*-{session}.jsonl"
                        )
                    ),
                    "relay_transcript_unavailable",
                    "native session lookup",
                    OSError,
                ),
                lambda paths: _read_transcript(home, paths, session),
            )


def _read_transcript(
    home: Path, paths: tuple[Path, ...], session: str
) -> Result[tuple[dict, ...]]:
    match paths:
        case (path,) if (
            not path.is_symlink()
            and path.resolve().is_relative_to(home.joinpath("sessions").resolve())
            and path.stat().st_uid == os.getuid()
        ):
            return bind(
                attempt(
                    lambda: tuple(
                        json.loads(line) for line in path.read_text().splitlines()
                    ),
                    "relay_transcript_unavailable",
                    "native session transcript",
                    OSError,
                    ValueError,
                ),
                lambda rows: _identity(rows, session),
            )
        case _:
            return err(
                "relay_transcript_unavailable",
                "A unique, user-owned native session transcript is required.",
            )


def _identity(rows: tuple[dict, ...], session: str) -> Result[tuple[dict, ...]]:
    match rows:
        case ({"type": "session_meta", "payload": {"id": str() as identifier}}, *_) if (
            identifier == session
        ):
            return Ok(rows)
        case _:
            return err(
                "relay_identity_mismatch",
                "The native transcript identity does not match.",
            )


def _root(rows: tuple[dict, ...], session: str, repo: Path) -> Result[object]:
    match rows[0]["payload"]:
        case {"cwd": str() as cwd, **metadata} if (
            not metadata.get("parent_thread_id")
            and metadata.get("thread_source", "user") == "user"
            and repo.resolve().is_relative_to(Path(cwd).resolve())
            and metadata.get("id") == session
        ):
            return Ok(None)
        case _:
            return err(
                "relay_root_required",
                "Recovery must run in the parent root conversation containing this project.",
            )


def _origin(home: Path, origin: str, session: str) -> Result[object]:
    match origin == session:
        case True:
            return Ok(None)
        case False:
            return bind(
                _transcript(home, origin),
                lambda rows: (
                    Ok(None)
                    if rows[0]["payload"].get("parent_thread_id") == session
                    else err(
                        "relay_parent_mismatch",
                        "This decision was not prepared by the current root or its direct project agent.",
                    )
                ),
            )


def _documents(value: Any, depth: int = 0) -> tuple[dict, ...]:
    match value:
        case _ if depth > 8:
            return ()
        case str():
            return _documents(
                value_or(
                    attempt(
                        lambda: json.JSONDecoder().raw_decode(value.lstrip())[0],
                        "not_json",
                        "native tool output",
                        ValueError,
                    ),
                    None,
                ),
                depth + 1,
            )
        case dict():
            return (value,) + tuple(
                document
                for key in ("output", "text")
                for document in _documents(value.get(key), depth + 1)
            )
        case list() | tuple():
            return tuple(
                document for item in value for document in _documents(item, depth + 1)
            )
        case _:
            return ()


def _observed(output: Any, current: dict) -> bool:
    return any(document == current for document in _documents(output))


def _question(arguments: str, current: dict) -> bool:
    return any(
        question.get("title", question.get("question")) == current["question"]
        and _options(question.get("options", ()), current)
        for document in _documents(arguments)
        for question in document.get("questions", ())
        if isinstance(question, dict) and len(document["questions"]) == 1
    )


def _options(options: Any, current: dict) -> bool:
    return (
        isinstance(options, (list, tuple))
        and len(options) == len(current["options"])
        and all(
            _option(option, label, tuple(current.get("details", ()))[index : index + 1])
            for index, (option, label) in enumerate(
                zip(options, current["options"], strict=True)
            )
        )
    )


def _option(option: Any, label: str, details: tuple[str, ...]) -> bool:
    match option:
        case str():
            return option == label
        case {"label": str() as shown, **rest}:
            return shown == label and rest.get("description", "") == next(
                iter(details), ""
            )
        case _:
            return False


def _step(exchange: Exchange, row: dict, current: dict) -> Exchange:
    match exchange, row:
        case Exchange(answer=str() as answer), _ if answer:
            return exchange
        case _, {
            "type": "response_item",
            "payload": {
                "type": "function_call",
                "name": str() as name,
                "call_id": str() as call,
                "arguments": str() as arguments,
            },
        } if canonical_question_name(name) in (
            "request_user_input",
            "request_user_input_async",
        ):
            return (
                Exchange(observed=exchange.observed, call_id=call)
                if exchange.observed and _question(arguments, current)
                else Exchange()
            )
        case _, {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "call_id": str() as call,
                "output": output,
            },
        } if call == exchange.call_id and call:
            return replace(
                exchange,
                delivered=any(
                    document.get("accepted") is True for document in _documents(output)
                ),
            )
        case _, {
            "type": "response_item",
            "payload": {
                "type": "function_call_output" | "custom_tool_call_output",
                "output": output,
            },
        }:
            return replace(
                exchange, observed=exchange.observed or _observed(output, current)
            )
        case Exchange(delivered=True), {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "id": str() as identifier,
                "content": list() as content,
            },
        }:
            return _reply(
                exchange,
                identifier,
                "".join(
                    item.get("text", "")
                    for item in content
                    if item.get("type") == "input_text"
                ),
                tuple(current["options"]),
            )
        case _:
            return exchange


def _reply(
    exchange: Exchange, identifier: str, text: str, options: tuple[str, ...]
) -> Exchange:
    match questions.match_option(text, options):
        case str() as answer:
            return replace(exchange, answer=answer, message_id=identifier)
        case _:
            return exchange


def _resolve(
    repo: Path, scope: str | None, current: dict, session: str, exchange: Exchange
) -> Result[dict]:
    match exchange:
        case Exchange(
            answer=str() as answer, message_id=str() as message, call_id=str() as call
        ) if answer:
            return decisions.resolve(
                repo,
                current["id"],
                answer,
                current["transport"],
                work_session_id=scope,
                human_reply_evidence={
                    "source": "codex-parent-transcript",
                    "session_id": session,
                    "message_id": message,
                    "call_id": call,
                    "structured_qualified": False,
                },
            )
        case _:
            return err(
                "relay_answer_unavailable",
                "No matching, delivered question and actual human reply were recorded after this pending decision was shown. Keep it pending.",
            )
