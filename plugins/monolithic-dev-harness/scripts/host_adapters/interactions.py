"""Host-owned question presentation. Async delivery is never a completed decision."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.decisions import Pending


def present(
    choice: dict[str, Any],
    host: str,
    blocking_available: bool,
    async_available: bool = False,
) -> dict[str, Any]:
    match host, blocking_available:
        case "codex", True:
            return {
                "host": host,
                "transport": "blocking",
                "tool": "request_user_input",
                "isBlocking": True,
                "questions": [choice],
            }
        case "claude", True:
            return {
                "host": host,
                "transport": "blocking",
                "tool": "AskUserQuestion",
                "questions": [
                    {key: value for key, value in choice.items() if key != "id"}
                    | {"multiSelect": False}
                ],
            }
        case "codex", False if async_available:
            return {
                "host": host,
                "transport": "async",
                "tool": "request_user_input_async",
                "isBlocking": False,
                "questions": [
                    {
                        "title": choice["question"],
                        "options": [option["label"] for option in choice["options"]],
                    }
                ],
                "wait": {"tool": "clock.sleep", "arguments": {"duration_ms": 20000}},
                "instruction": "Show the complete review before the buttons. After delivery, keep the turn open and use the interruptible wait in bounded intervals until the actual matching human answer arrives. Do no dependent work and ask no follow-up questions. Unrelated messages do not answer the question: return to waiting. If the countdown hides the buttons, preserve the pending question; the user can reopen it with Answer question. Do not reissue it automatically. Delivery, timeout, and dismissal are not answers. If interruptible waiting is unavailable, report the host capability blocker instead of promising persistent buttons.",
            }
        case _:
            return {
                "host": host,
                "transport": "chat",
                "question": choice["question"],
                "options": choice["options"],
                "instruction": "Show the review and question in chat, end the turn, and wait for the actual human reply.",
            }


def question_transport(host: str, tool_name: str) -> str:
    return (
        "async"
        if host == "codex"
        and tool_name.rsplit("__", 1)[-1] == "request_user_input_async"
        else "blocking"
    )


def normalize_question(host: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    if host != "codex":
        return tool_input
    return {
        **tool_input,
        "questions": [
            {
                **question,
                "question": question.get("question", question.get("title", "")),
                "options": [
                    {"label": option, "description": ""}
                    if isinstance(option, str)
                    else option
                    for option in question.get("options", ())
                ],
            }
            for question in tool_input.get("questions", ())
        ],
    }


def prompt_answer(
    host: str, prompt: str, pending: Pending
) -> tuple[str, str, str] | None:
    if pending.transport == "chat" or (
        host == "codex"
        and pending.transport == "async"
        and not prompt.lstrip().startswith("<send_user_message_question_reply>")
    ):
        typed = prompt.strip().rstrip(".!").strip().casefold()
        chosen = next(
            (
                str(option)
                for option in pending.options
                if str(option).strip().casefold() == typed
            ),
            None,
        )
        return (pending.id, chosen, pending.transport) if chosen else None
    if host != "codex" or pending.transport != "async":
        return None
    match = re.fullmatch(
        r"\s*<send_user_message_question_reply>\s*(.*?)\s*</send_user_message_question_reply>\s*",
        prompt,
        re.DOTALL,
    )
    if match is None:
        return None
    try:
        replies = json.loads(match.group(1))
        if not isinstance(replies, list) or len(replies) != 1:
            return None
        reply = replies[0]
        item = json.loads(reply["questionItemId"])
        if (
            item != ["request_user_input_async", pending.id, 0]
            or reply.get("question") != pending.question
        ):
            return None
        answer = reply.get("answer")
        return (pending.id, answer, "async") if isinstance(answer, str) else None
    except (ValueError, KeyError, TypeError):
        return None


def decision_exchange(
    pending: Pending, answer: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The question a delayed reply answered and the response, in the shape the question checks read."""
    question = {
        "id": "decision",
        "question": pending.question,
        "options": [{"label": option, "description": ""} for option in pending.options],
    }
    return {"questions": [question]}, {"answers": {"decision": {"answers": [answer]}}}
