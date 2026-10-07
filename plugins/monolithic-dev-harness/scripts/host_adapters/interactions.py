"""Host-owned question presentation. Async delivery is never a completed decision."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.decisions import Pending


_MENU_TEXT = {
    "en": {
        "closed": "Reply with a number or an option name.",
        "open": "Reply with a number, an option name, or tell me what you'd like instead.",
    },
    "pt-br": {
        "closed": "Responda com um número ou o nome de uma opção.",
        "open": "Responda com um número, o nome de uma opção ou diga o que prefere.",
    },
}


def chat_menu(choice: dict[str, Any], free_text: bool, language: str = "en") -> str:
    """The one chat rendering of a decision, so every fallback looks the same."""
    lines = [f"**{choice['question']}**", ""]
    for number, option in enumerate(choice["options"], start=1):
        detail = str(option.get("description", "")).strip()
        lines.append(
            f"{number}. **{option['label']}**" + (f" — {detail}" if detail else "")
        )
    text = _MENU_TEXT.get(language, _MENU_TEXT["en"])
    return "\n".join([*lines, "", text["open" if free_text else "closed"]])


def present(
    choice: dict[str, Any],
    host: str,
    blocking_available: bool,
    async_available: bool = False,
    *,
    free_text: bool = False,
    language: str = "en",
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
                "instruction": "Show the complete review before the buttons. After delivery, keep the turn open and use the interruptible wait in bounded intervals until the actual matching human answer arrives. Do no dependent work and ask no follow-up questions. Unrelated messages do not answer a closed-choice question: return to waiting. If the countdown hides the buttons, preserve the pending question; the user can reopen it with Answer question. Delivery, timeout, and dismissal are not answers. If delivery fails or interruptible waiting is unavailable, quietly use harness decision fallback to re-ask this question in chat and continue the same run. Do not show internal capability errors to the user.",
            }
        case _:
            return {
                "host": host,
                "transport": "chat",
                "question": choice["question"],
                "options": choice["options"],
                "menu": chat_menu(choice, free_text, language),
                "instruction": "Show the review, then `menu` exactly as written, and end the turn to receive the actual human reply. Do not reword, renumber, or add options. Preserve the review, choices, and progress; resume this same run when the human answers. Do not report internal tool failures or abandon the run.",
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
    from harness.questions import authorizing_options, match_option

    # A typed message is the human's own reply whatever showed the question: a dismissed picker
    # or expired buttons leave the person typing, and that reply must still count.
    if not prompt.lstrip().startswith("<send_user_message_question_reply>"):
        match match_option(prompt, pending.options):
            case str() as chosen:
                return pending.id, chosen, pending.transport
            case None if (
                pending.allow_free_text
                and not pending.approval
                and not authorizing_options(pending.options)
                and prompt.strip()
            ):
                return pending.id, prompt.strip(), pending.transport
            case _:
                return None
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
