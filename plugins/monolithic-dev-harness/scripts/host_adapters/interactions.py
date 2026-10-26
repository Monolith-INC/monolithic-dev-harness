"""Host-owned question presentation. Async delivery is never a completed decision."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from core.result import Err, Ok
from host_adapters.codex_runtime import (
    CodexRuntimeProfile,
    DecisionContext,
    select_question_transport,
)

_DEFAULT_DECISION = DecisionContext()

if TYPE_CHECKING:
    from harness.decisions import Pending

_ZED_MENU_INSTRUCTION = (
    "Show the review, then `menu` exactly as written, and end the turn to receive the "
    "actual human reply. Do not reword, renumber, or add options. Preserve the review, "
    "choices, and progress; resume this same run when the human answers. On Zed the menu "
    "renders as plain chat text because the editor has no native question control; do not "
    "invent a clickable control and do not treat an MCP tool result as the human's answer. "
    "Do not report internal tool failures or abandon the run."
)

_DEFAULT_CHAT_INSTRUCTION = (
    "Show the review, then `menu` exactly as written, and end the turn to receive the "
    "actual human reply. Do not reword, renumber, or add options. Preserve the review, "
    "choices, and progress; resume this same run when the human answers. Do not report "
    "internal tool failures or abandon the run. The chat menu is for this one question: "
    "present the next question with native controls again."
)


def chat_instruction(host: str) -> str:
    """The delivery instruction for the chat-transport fallback, per host."""
    return (
        _ZED_MENU_INSTRUCTION
        if host.strip().lower() == "zed"
        else _DEFAULT_CHAT_INSTRUCTION
    )


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
    codex_profile: CodexRuntimeProfile | None = None,
    decision: DecisionContext = _DEFAULT_DECISION,
) -> dict[str, Any]:
    match host, codex_profile:
        case "codex", CodexRuntimeProfile():
            return _present_codex(choice, codex_profile, decision, free_text, language)
        case _:
            pass
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
                "instruction": chat_instruction(host),
            }


def _present_codex(
    choice: dict[str, Any],
    profile: CodexRuntimeProfile,
    decision: DecisionContext,
    free_text: bool,
    language: str,
) -> dict[str, Any]:
    match select_question_transport(profile, decision):
        case Err(failure):
            return {
                **present(
                    choice, "codex", False, free_text=free_text, language=language
                ),
                "transport_error": failure.to_dict(),
                "structured_qualified": False,
                **_native_candidate(choice, profile, decision, "chat"),
                "instruction": "Keep this decision pending. Use native_candidate only if "
                "the root's actual advertised tool and instructions permit it; otherwise run "
                "harness decision fallback. Preparation is not delivery or an answer.",
            }
        case Ok(transport):
            return (
                {
                    **present(
                        choice,
                        "codex",
                        transport == "blocking",
                        transport == "async",
                        free_text=free_text,
                        language=language,
                    ),
                    "isBlocking": transport == "blocking" and profile.mode == "plan",
                    "structured_qualified": transport in profile.qualified_transports,
                    "instruction": _codex_instruction(profile, decision, transport),
                }
                | _async_wait(profile, transport)
                | _native_candidate(choice, profile, decision, transport)
            )


def _native_candidate(
    choice: dict[str, Any],
    profile: CodexRuntimeProfile,
    decision: DecisionContext,
    transport: str,
) -> dict[str, Any]:
    match transport, decision, profile:
        case _, _, CodexRuntimeProfile(root=False, evidence=(_, *_)):
            return {}
        case "chat", DecisionContext(purpose="domain", structured_required=True), _:
            return {
                "native_candidate": {
                    "tool": "request_user_input_async",
                    "questions": [
                        {
                            "title": choice["question"],
                            "options": [
                                option["label"] for option in choice["options"]
                            ],
                        }
                    ],
                    "availability": "unverified",
                    "instruction": "Only the root may attempt this candidate when the actual "
                    "native tool is advertised and permitted. It is prepared, not delivered. "
                    "Do not show transport diagnostics to the human. Preserve the exact review "
                    "and question; use typed fallback if unavailable. No dependent work is authorized.",
                },
            }
        case _:
            return {}


def _async_wait(profile: CodexRuntimeProfile, transport: str) -> dict[str, Any]:
    match transport, "clock.sleep" in profile.tools:
        case "async", False:
            return {"wait": None}
        case _:
            return {}


def _codex_instruction(
    profile: CodexRuntimeProfile, decision: DecisionContext, transport: str
) -> str:
    match transport, decision.optional, profile.mode:
        case "chat", _, _:
            return chat_instruction("codex")
        case _, True, _:
            return (
                "Show the review and ask this optional question. Delivery and silence are "
                "not answers. An unanswered preference may use its safe default."
            )
        case "async", _, _ if "clock.sleep" not in profile.tools:
            return (
                "Show the full review and deliver the exact native async question. No "
                "interruptible wait is advertised: end the turn with this decision pending. "
                "Do no dependent work. Delivery, timeout and dismissal are not answers."
            )
        case _, _, "plan":
            return (
                "Show the full review and use the exact native question. Keep the decision "
                "pending until the actual answer is captured. Plan mode permits this decision; "
                "implementation still requires an actual host mode switch and fresh observation."
            )
        case _:
            return (
                "Show the full review and use the exact native question. Wait interruptibly "
                "in bounded intervals for the matching actual answer. Delivery, timeout, "
                "dismissal and unrelated replies are not answers."
            )


def canonical_question_name(tool_name: str) -> str:
    return tool_name.rsplit("__", 1)[-1].rsplit(".", 1)[-1]


def question_transport(host: str, tool_name: str) -> str:
    return (
        "async"
        if host == "codex"
        and canonical_question_name(tool_name) == "request_user_input_async"
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
    match normalize_human_reply(host, prompt, pending):
        case None:
            return None
        case reply:
            return reply.decision_tuple()


def normalize_human_reply(host: str, prompt: str, pending: Pending):
    from harness.process_messages import HumanReply

    match _prompt_answer(host, prompt, pending):
        case (identifier, answer, transport):
            return HumanReply(identifier, pending.question, answer, transport)
        case None:
            return None


def _prompt_answer(
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
