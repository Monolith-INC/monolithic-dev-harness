"""Questions the agent asks the user (Claude/Codex native pickers): plain language and approval by click.

Two hooks use this module:

- Before a question is shown (`problems`): a question the user would have to decode is sent back to
  be rewritten. One question at a time, short, and free of file names, code, and the harness's own
  vocabulary (rule names, batch ids, tool names). A question that arrives with answers already
  filled in is refused: only the user answers.
- After the user answers (`approval`): picking the `Approve` option of a question opens an approval
  window, exactly like typing `approve HB-…`. The click comes from the user, not the agent.
- Tracker questions (`tracker_action`, `tracker_choice`): a question that says "tracker" and offers
  `Trust`, `Use it`, or `Stop trusting` is about one onboarded tracker it names. The "before" hook
  pins that tracker's exact version to the question; the "after" hook acts on the click.

The "before" hook marks each question it let through under `.harness/state/asked/`, a human-owned
folder. The "after" hook only honours an answer to a marked question, so a question that skipped
the check (the hook failed, or it was never run) can never open a window.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

MAX_QUESTION_WORDS = 50
MAX_DESCRIPTION_WORDS = 25
APPROVE_LABELS = frozenset({"approve", "aprovar", "aprovo"})
MANUAL_APPROVE_LABELS = frozenset({"approve change", "aprovar mudança"})
ADOPTION_APPROVE_LABELS = frozenset({"approve adoption", "aprovar adoção"})
TRACKER_ACTIONS = {"trust": "trust", "use it": "select", "stop trusting": "untrust"}
_ADOPTION_ID = re.compile(r"\bHA-[A-F0-9]{10}\b", re.IGNORECASE)


@dataclass(frozen=True)
class ChoiceOption:
    id: str
    en: str
    pt_br: str
    consequence_en: str
    consequence_pt_br: str


@dataclass(frozen=True)
class Choice:
    id: str
    header_en: str
    header_pt_br: str
    question_en: str
    question_pt_br: str
    options: tuple[ChoiceOption, ...]
    approval: bool = False


def render_choice(
    choice: Choice,
    language: str,
    host: str,
    native_available: bool,
    approval_token: str = "",
) -> dict[str, Any]:
    """One decision contract, shown natively or with an equivalent text fallback."""
    portuguese = language == "pt-br"
    options = tuple(
        {
            "id": option.id,
            "label": option.pt_br if portuguese else option.en,
            "description": option.consequence_pt_br
            if portuguese
            else option.consequence_en,
        }
        for option in choice.options
    )
    question = choice.question_pt_br if portuguese else choice.question_en
    header = choice.header_pt_br if portuguese else choice.header_en
    match native_available, len(options) <= 3, choice.approval, approval_token:
        case True, True, _, _ if not choice.approval or any(
            item["label"].strip().lower() in APPROVE_LABELS for item in options
        ):
            return {
                "host": host,
                **({"isBlocking": True} if host == "codex" else {}),
                "questions": [
                    {
                        **(
                            {"id": choice.id}
                            if host == "codex"
                            else {"multiSelect": False}
                        ),
                        "header": header,
                        "question": question,
                        "options": [
                            {"label": item["label"], "description": item["description"]}
                            for item in options
                        ],
                    }
                ],
            }
        case _, _, True, str() as token if token:
            return {
                "host": host,
                "text": f"{question}\n"
                + (
                    f"Reply exactly: approve {token}"
                    if not portuguese
                    else f"Responda exatamente: approve {token}"
                ),
                "options": options,
            }
        case _, _, True, _:
            return {
                "host": host,
                "error": "approval needs a working native control or an exact typed token",
            }
        case _:
            return {
                "host": host,
                "text": "\n".join(
                    (
                        question,
                        *(
                            f"{index}. {item['label']} — {item['description']}"
                            for index, item in enumerate(options, 1)
                        ),
                        "Reply with the number."
                        if not portuguese
                        else "Responda com o número.",
                    )
                ),
                "options": options,
            }


_RULE_NAMES = (
    "human-owned",
    "approval-required",
    "protected-items",
    "tests-with-code",
    "generated-files",
    "guarded-paths",
    "draft-reviewed-prs",
    "feature-branch",
    "history-preserved",
    "harness-error",
)
_JARGON = (
    (re.compile(r"`"), "code formatting (backticks)"),
    (re.compile(r"\bHB-[A-Z0-9]+", re.IGNORECASE), "a batch id"),
    (re.compile(r"\bmcp__\w+"), "a tool name"),
    (
        re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),
        "an identifier with underscores",
    ),
    (re.compile(r"(?<![\w.])\.[A-Za-z][\w.-]*"), "a dotfile or folder name"),
    (re.compile(r"(?:^|\s)(?:~|\.{1,2})?/[\w.-]"), "a path"),
    (re.compile(r"\b[\w-]+/[\w./-]*\.\w{1,5}\b"), "a path"),
    (
        re.compile(r"\b[\w-]+\.(?:json|md|py|ts|tsx|js|dart|ya?ml|sh|toml|lock|txt)\b"),
        "a file name",
    ),
    (re.compile(r"\bG[1-4]\b"), "a gate number"),
    (
        re.compile(r"\b(?:" + "|".join(map(re.escape, _RULE_NAMES)) + r")\b"),
        "a rule name",
    ),
)


def _words(text: str) -> int:
    return len(text.split())


def _jargon(text: str) -> list[str]:
    return [label for pattern, label in _JARGON if pattern.search(text)]


def problems(tool_input: dict[str, Any]) -> list[str]:
    """What makes this question hard for a person to answer; empty when it is fine."""
    if tool_input.get("answers"):
        return [
            "it arrives with answers already filled in; only the user answers a question"
        ]
    questions = tool_input.get("questions")
    if not isinstance(questions, list) or not questions:
        return []
    found: list[str] = []
    if len(questions) > 1:
        found.append(
            f"it asks {len(questions)} questions at once; ask one, then the next"
        )
    for question in questions:
        if not isinstance(question, dict):
            continue
        text = str(question.get("question", ""))
        if _words(text) > MAX_QUESTION_WORDS:
            found.append(
                f"the question has {_words(text)} words; keep it under {MAX_QUESTION_WORDS}"
            )
        if text.count("?") > 1:
            found.append("the question asks more than one thing")
        pieces = [text, str(question.get("header", ""))]
        for option in question.get("options") or []:
            if not isinstance(option, dict):
                continue
            description = str(option.get("description", ""))
            pieces += [str(option.get("label", "")), description]
            if _words(description) > MAX_DESCRIPTION_WORDS:
                found.append(
                    f"the description of {option.get('label')!r} has {_words(description)} words; "
                    f"keep each under {MAX_DESCRIPTION_WORDS}"
                )
        for label in dict.fromkeys(
            label for piece in pieces for label in _jargon(piece)
        ):
            found.append(f"it contains {label}")
    return list(dict.fromkeys(found))


def rewrite_reason(found: list[str]) -> str:
    return (
        "This question is not plain enough to show the user: "
        + "; ".join(found)
        + ". Rewrite it for someone who knows the goal but not the harness: one decision, in everyday "
        "words, saying what each option does for them. No file names, code, or internal names; if a "
        "detail matters, describe what it does instead. Leave anything unrelated to this decision for "
        "the end of the stage."
    )


def approval(tool_input: dict[str, Any], tool_response: Any) -> tuple[str, str] | None:
    """The (question, answer) the user approved, if they picked an `Approve` option."""
    answers = tool_response.get("answers") if isinstance(tool_response, dict) else None
    if not isinstance(answers, dict):
        return None
    questions = tool_input.get("questions") or []
    for question in questions:
        if not isinstance(question, dict):
            continue
        text = str(question.get("question", ""))
        labels = {
            str(option.get("label", ""))
            for option in question.get("options") or []
            if isinstance(option, dict)
        }
        answer = _answer_for(question, answers)
        match answer:
            case str() if answer in labels and answer.strip().lower() in APPROVE_LABELS:
                return text, answer
    return None


def manual_signoff(tool_input: dict[str, Any]) -> str | None:
    """Question text when it offers the dedicated guarded-change approval action."""
    question = _first_question(tool_input)
    labels = {
        str(option.get("label", "")).strip().lower()
        for option in question.get("options") or []
        if isinstance(option, dict)
    }
    return str(question.get("question", "")) if labels & MANUAL_APPROVE_LABELS else None


def manual_choice(tool_input: dict[str, Any], tool_response: Any) -> bool:
    """Whether the user clicked the dedicated guarded-change approval action."""
    answers = tool_response.get("answers") if isinstance(tool_response, dict) else None
    answer = _answer_for(_first_question(tool_input), answers)
    return isinstance(answer, str) and answer.strip().lower() in MANUAL_APPROVE_LABELS


def adoption_signoff(tool_input: dict[str, Any]) -> tuple[str, str] | None:
    """Question text and adoption id for the dedicated continuation-plan approval."""
    question = _first_question(tool_input)
    labels = {
        str(option.get("label", "")).strip().lower()
        for option in question.get("options") or []
        if isinstance(option, dict)
    }
    text = str(question.get("question", ""))
    found = tuple(dict.fromkeys(match.upper() for match in _ADOPTION_ID.findall(text)))
    match bool(labels & ADOPTION_APPROVE_LABELS), found:
        case True, (adoption_id,):
            return text, adoption_id
        case _:
            return None


def adoption_requested(tool_input: dict[str, Any]) -> bool:
    return any(
        isinstance(option, dict)
        and str(option.get("label", "")).strip().lower() in ADOPTION_APPROVE_LABELS
        for option in _first_question(tool_input).get("options") or []
    )


def adoption_choice(tool_input: dict[str, Any], tool_response: Any) -> bool:
    """Whether the user clicked the dedicated adoption-plan approval action."""
    answers = tool_response.get("answers") if isinstance(tool_response, dict) else None
    answer = _answer_for(_first_question(tool_input), answers)
    return isinstance(answer, str) and answer.strip().lower() in ADOPTION_APPROVE_LABELS


def _first_question(tool_input: dict[str, Any]) -> dict[str, Any]:
    questions = tool_input.get("questions") or []
    first = questions[0] if questions else {}
    return first if isinstance(first, dict) else {}


def _answer_for(question: dict[str, Any], answers: Any) -> str | None:
    """Read Claude's text-keyed answer or Codex's id-keyed answer."""
    match answers:
        case dict() as answer_map:
            candidate = answer_map.get(str(question.get("question", "")))
            selected = answer_map.get(str(question.get("id", "")), candidate)
            match selected:
                case str():
                    return selected
                case {"answers": [str(answer), *_]}:
                    return answer
                case _:
                    return None
        case _:
            return None


def tracker_action(tool_input: dict[str, Any]) -> tuple[tuple[str, ...], str] | None:
    """(actions offered, question text) for a question about a tracker; None for any other.

    It must say "tracker" and offer Trust, Use it, or Stop trusting: "Use it" alone is an
    everyday label ("Should I reuse the cached build?") and never makes a tracker question.
    """
    question = _first_question(tool_input)
    text = str(question.get("question", ""))
    actions = tuple(
        dict.fromkeys(
            TRACKER_ACTIONS[label]
            for option in question.get("options") or []
            if isinstance(option, dict)
            and (label := str(option.get("label", "")).strip().lower())
            in TRACKER_ACTIONS
        )
    )
    mentions = re.search(r"\btrackers?\b", text, re.IGNORECASE)
    return (actions, text) if actions and mentions else None


def tracker_choice(tool_input: dict[str, Any], tool_response: Any) -> str | None:
    """The tracker action the user clicked, or None when they picked anything else."""
    answers = tool_response.get("answers") if isinstance(tool_response, dict) else None
    answer = _answer_for(_first_question(tool_input), answers)
    return (
        TRACKER_ACTIONS.get(answer.strip().lower()) if isinstance(answer, str) else None
    )


def approval_id(tool_use_id: str) -> str:
    """A batch id for a clicked approval, stable for the question it answers."""
    digest = hashlib.sha256(tool_use_id.encode("utf-8")).hexdigest()[:8].upper()
    return f"HB-Q{digest}"


def marker_name(tool_use_id: str) -> str:
    return hashlib.sha256(tool_use_id.encode("utf-8")).hexdigest()[:32]
