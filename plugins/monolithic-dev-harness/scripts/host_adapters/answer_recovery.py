"""Recover a missed Codex answer from the transcript supplied by a real prompt hook."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.result import Ok, attempt, value_or
from harness import decisions, questions
from host_adapters.hook_bridge import answer_response
from host_adapters.interactions import canonical_question_name


def recorded_answer(
    host: str,
    payload: dict[str, Any],
    pending: decisions.Pending,
) -> tuple[str, str, str] | None:
    match host, pending.transport, payload:
        case "codex", "blocking", {
            "transcript_path": str() as path,
            "session_id": str() as session,
            "cwd": str() as cwd,
        } if session:
            return _matching_answer(
                value_or(
                    attempt(
                        lambda: tuple(
                            json.loads(line)
                            for line in Path(path).read_text().splitlines()
                        ),
                        "transcript_unavailable",
                        "host transcript",
                        OSError,
                        ValueError,
                    ),
                    (),
                ),
                session,
                cwd,
                pending,
            )
        case _:
            return None


def _matching_answer(
    rows: tuple[dict[str, Any], ...],
    session: str,
    cwd: str,
    pending: decisions.Pending,
) -> tuple[str, str, str] | None:
    match rows:
        case ({"type": "session_meta", "payload": dict() as metadata}, *_) if (
            metadata.get("id") == session and metadata.get("cwd") == cwd
        ):
            return _recorded_exchange(
                tuple(
                    row["payload"]
                    for row in rows
                    if isinstance(row, dict)
                    and row.get("type") == "response_item"
                    and isinstance(row.get("payload"), dict)
                    and row["payload"].get("call_id") == pending.id
                ),
                pending,
            )
        case _:
            return None


def _recorded_exchange(
    events: tuple[dict[str, Any], ...],
    pending: decisions.Pending,
) -> tuple[str, str, str] | None:
    match events:
        case (
            {
                "type": "function_call",
                "name": str() as name,
                "arguments": str() as arguments,
            },
            {"type": "function_call_output", "output": response},
        ) if canonical_question_name(name) == "request_user_input":
            return _read_answer(
                value_or(
                    attempt(
                        lambda: json.loads(arguments),
                        "invalid_question",
                        "question",
                        ValueError,
                    ),
                    {},
                ),
                response,
                pending,
            )
        case _:
            return None


def _read_answer(
    tool_input: Any,
    response: Any,
    pending: decisions.Pending,
) -> tuple[str, str, str] | None:
    match tool_input, answer_response({"tool_response": response}):
        case {
            "questions": [{"question": str() as text, "options": list() as options}]
        }, Ok(decoded) if (
            text == pending.question
            and tuple(
                option.get("label") for option in options if isinstance(option, dict)
            )
            == pending.options
        ):
            match questions.answer(tool_input, decoded):
                case str() as answer:
                    return pending.id, answer, "blocking"
                case None:
                    return None
        case _:
            return None
