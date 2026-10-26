"""Best-effort suspended question evidence, separate from approvals and pending decisions."""

from pathlib import Path
from typing import Any

from core.result import Ok, Result, attempt
from harness import questions, state
from host_adapters import hook_bridge
from host_adapters.interactions import normalize_question, question_transport


def _path(repo: Path, payload: dict[str, Any]) -> Path:
    return (
        repo
        / ".harness/state/question-observations"
        / (state.safe_name(hook_bridge.question_id(payload)) + ".json")
    )


def ask(repo: Path, host: str, payload: dict[str, Any]) -> Result[object]:
    return attempt(
        lambda: state.write_json(
            _path(repo, payload),
            {
                "host": host,
                "transport": question_transport(
                    host, str(payload.get("tool_name", ""))
                ),
                "tool_use_id": hook_bridge.question_id(payload),
                "input": normalize_question(host, hook_bridge.question_input(payload)),
                "status": "observed",
                "approval": False,
            },
        ),
        "observation_unavailable",
        "suspended question evidence",
        Exception,
    )


def answer(repo: Path, host: str, payload: dict[str, Any]) -> Result[object]:
    return attempt(
        lambda: _answer(repo, payload),
        "observation_unavailable",
        "suspended answer evidence",
        Exception,
    )


def _answer(repo: Path, payload: dict[str, Any]) -> object:
    match state.read_json(_path(repo, payload)), hook_bridge.answer_response(payload):
        case {"input": dict() as tool_input} as observed, Ok(response):
            match questions.answer(tool_input, response):
                case str() as reply:
                    return state.write_json(
                        _path(repo, payload),
                        {**observed, "status": "answered", "answer": reply},
                    )
                case _:
                    return None
        case _:
            return None


def foreign_prompt(repo: Path, pending_id: str, reply: str) -> bool:
    """An uncorrelated delayed reply is evidence, never an answer to an older decision."""
    match tuple(
        path
        for path in (repo / ".harness/state/question-observations").glob("*.json")
        for record in (state.read_json(path),)
        if record is not None
        and record.get("status") == "observed"
        and record.get("transport") == "async"
        and record.get("tool_use_id") != pending_id
    ):
        case ():
            return False
        case paths:
            return isinstance(
                attempt(
                    lambda: _record_prompt(paths, reply),
                    "observation_unavailable",
                    "delayed reply",
                    Exception,
                ),
                Ok,
            )


def _record_prompt(paths: tuple[Path, ...], reply: str) -> tuple[object, ...]:
    return tuple(
        state.write_json(
            path,
            {
                **(state.read_json(path) or {}),
                "status": "reply-observed",
                "reply": reply,
                "approval": False,
            },
        )
        for path in paths
    )
