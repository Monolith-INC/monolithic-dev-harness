"""Human-owned lifecycle controls use their own channel, independent of pending decisions."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.result import Ok, Result, err
from harness import questions, state
from harness.process_messages import HumanReply
from host_adapters import hook_bridge, native_session_id
from host_adapters.interactions import (
    normalize_human_reply,
    normalize_question,
    question_transport,
)

QUESTIONS = frozenset(
    {
        "How would you like to control the harness?",
        "Como você quer controlar o harness?",
    }
)
CHOICES = {
    "harness suspend": "suspend",
    "suspend harness": "suspend",
    "suspender harness": "suspend",
    "harness resume": "resume",
    "resume harness": "resume",
    "retomar harness": "resume",
    "free mode": "free",
    "modo livre": "free",
}


@dataclass(frozen=True)
class ControlRecord:
    presentation_id: str
    question: str
    options: tuple[str, ...]
    conversation: str
    transport: str
    status: str


@dataclass(frozen=True)
class ControlTransition:
    operation: str
    answer: str
    status: str = "answered"


def reduce_control(
    record: ControlRecord, reply: HumanReply, conversation: str
) -> Result[ControlTransition]:
    match record, reply:
        case ControlRecord(status="pending"), HumanReply() if (
            record.conversation == conversation
            and record.presentation_id == reply.presentation_id
            and record.question == reply.question
            and record.transport == reply.transport
            and reply.answer in record.options
            and operation(reply.answer) is not None
        ):
            return Ok(ControlTransition(operation(reply.answer), reply.answer))
        case _:
            return err(
                "control_reply_mismatch",
                "The reply must match this pending lifecycle control and conversation.",
            )


def operation(reply: str) -> str | None:
    match reply.strip().splitlines():
        case [opening, body, "```"] if opening.startswith("```"):
            return operation(body)
        case _:
            pass
    return CHOICES.get(reply.strip().strip("`").strip().rstrip(".!").casefold())


def is_question(tool_input: dict[str, Any]) -> bool:
    return any(
        question.get("question") in QUESTIONS
        for question in tool_input.get("questions", ())
    )


def _path(repo: Path, payload: dict[str, Any]) -> Path:
    return (
        repo
        / ".harness/state/control-questions"
        / (state.safe_name(hook_bridge.question_id(payload)) + ".json")
    )


def observe(repo: Path, host: str, payload: dict[str, Any]) -> bool:
    match normalize_question(host, hook_bridge.question_input(payload)):
        case tool_input if is_question(tool_input) and not questions.problems(
            tool_input
        ):
            _supersede(repo, native_session_id(host, payload) or "")
            state.write_json(
                _path(repo, payload),
                {"input": tool_input, "status": "pending"}
                | {
                    "conversation": native_session_id(host, payload) or "",
                    "transport": question_transport(
                        host, str(payload.get("tool_name", ""))
                    ),
                },
            )
            return True
        case _:
            return False


def answer(repo: Path, payload: dict[str, Any], host: str = "codex") -> str | None:
    match hook_bridge.question_id(payload):
        case "":
            return None
        case _:
            pass
    match state.read_json(_path(repo, payload)), hook_bridge.answer_response(payload):
        case {"input": dict() as tool_input, "status": "pending"} as observed, Ok(
            response
        ) if observed.get("conversation", "") == (
            native_session_id(host, payload) or ""
        ):
            match questions.answer(tool_input, response):
                case str() as reply if operation(reply) is not None:
                    state.write_json(
                        _path(repo, payload),
                        {**observed, "status": "answered", "answer": reply},
                    )
                    return operation(reply)
                case _:
                    return None
        case _:
            return None


def pending_native(repo: Path, conversation: str = "") -> bool:
    return any(
        record.get("status") == "pending"
        and record.get("transport") == "blocking"
        and record.get("conversation", "") == conversation
        for path in (repo / ".harness/state/control-questions").glob("*.json")
        for record in (state.read_json(path) or {},)
    )


def stage_chat(
    repo: Path,
    key: str,
    question: str,
    options: tuple[str, ...],
    conversation: str = "",
) -> object:
    """Fallback preserves presentation, never supplies a human answer."""
    _supersede(repo, conversation)
    return state.write_json(
        _path(repo, {"tool_use_id": key}),
        {
            "status": "pending",
            "transport": "chat",
            "conversation": conversation,
            "input": {
                "questions": [
                    {
                        "question": question,
                        "options": [{"label": label} for label in options],
                    }
                ]
            },
        },
    )


def _supersede(repo: Path, conversation: str) -> tuple[object, ...]:
    return tuple(
        state.write_json(path, {**record, "status": "superseded"})
        for path in (repo / ".harness/state/control-questions").glob("*.json")
        for record in (state.read_json(path) or {},)
        if record.get("status") == "pending"
        and record.get("conversation", "") == conversation
    )


def prompt_operation(
    repo: Path, reply: str, conversation: str = "", host: str = "codex"
) -> str | None:
    from harness.decisions import Pending

    return operation(reply) or next(
        (
            transition.value.operation
            for path in sorted(
                (repo / ".harness/state/control-questions").glob("*.json"),
                key=lambda file: file.stat().st_mtime_ns,
                reverse=True,
            )
            for record in (state.read_json(path) or {},)
            if record.get("status") == "pending"
            and record.get("transport") in {"chat", "async", "blocking"}
            and record.get("conversation", "") == conversation
            if not reply.strip().isdigit() or reply.strip().isascii()
            for question in record["input"]["questions"]
            for captured in (
                normalize_human_reply(
                    host,
                    reply,
                    Pending(
                        id=path.stem,
                        question=question["question"],
                        options=tuple(
                            option["label"] for option in question["options"]
                        ),
                        transport=record["transport"],
                        approval=False,
                        scope=None,
                    ),
                ),
            )
            if captured is not None
            for transition in (
                reduce_control(
                    ControlRecord(
                        path.stem,
                        question["question"],
                        tuple(option["label"] for option in question["options"]),
                        record.get("conversation", ""),
                        record["transport"],
                        record["status"],
                    ),
                    captured,
                    conversation,
                ),
            )
            if isinstance(transition, Ok)
        ),
        None,
    )


def waiting(repo: Path, conversation: str = "") -> bool:
    return any(
        record.get("status") == "pending"
        and record.get("transport") in {"async", "chat"}
        and record.get("conversation", "") == conversation
        for path in (repo / ".harness/state/control-questions").glob("*.json")
        for record in (state.read_json(path) or {},)
    )


def prompt(repo: Path, reply: str, conversation: str = "") -> tuple[object, ...]:
    """Preserve evidence when a real user prompt answers a delayed control."""
    return tuple(
        state.write_json(path, {**record, "status": "answered", "answer": reply})
        for path in (repo / ".harness/state/control-questions").glob("*.json")
        for record in (state.read_json(path),)
        if record is not None
        and record.get("status") == "pending"
        and record.get("conversation", "") == conversation
    )
