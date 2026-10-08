"""The catalog of standard questions (`config/gates.toml`), ready in every supported language.

The agent picks a gate and fills its slots; the harness supplies the wording in the project's
language. A gate that approves writes also says what the approval is tied to, so the write check
can hold the approval to that context.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, err
from harness import questions

CATALOG = Path(__file__).resolve().parents[2] / "config" / "gates.toml"
RECOMMENDED = {"en": "Recommended", "pt-br": "Recomendado"}
_SLOT = re.compile(r"\{([a-z_]+)\}")
_BINDS = re.compile(r"^(|artifacts|(branch|pr|item):\{[a-z_]+\})$")


@dataclass(frozen=True)
class Option:
    id: str
    label: dict[str, str]
    detail: dict[str, str]


@dataclass(frozen=True)
class Gate:
    id: str
    question: dict[str, str]
    options: tuple[Option, ...]
    free_text: bool = False
    approval: bool = False
    artifact: bool = False
    recommended: str = ""
    binds: str = ""


@dataclass(frozen=True)
class Rendered:
    """A gate in one language, slots filled: what `decision present` shows and records."""

    gate: str
    question: str
    options: tuple[str, ...]
    details: tuple[str, ...]
    free_text: bool
    approval: bool
    artifact: bool
    bound: bool  # an approval tied to a context (no expiry); False: a general, short window
    target: tuple[str, str] | None


def load(path: Path = CATALOG) -> Result[tuple[tuple[str, ...], dict[str, Gate]]]:
    """The supported languages and every gate, or the first reason the catalog is unusable."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return err("gate_catalog_invalid", f"{path.name}: {exc}")
    languages = tuple(raw.get("languages", ()))
    gates: dict[str, Gate] = {}
    for entry in raw.get("gate", ()):
        match _gate(entry, languages):
            case Err() as failure:
                return failure
            case Ok(gate) if gate.id in gates:
                return err("gate_catalog_invalid", f"gate {gate.id} is defined twice")
            case Ok(gate):
                gates[gate.id] = gate
    return (
        Ok((languages, gates))
        if languages
        else err("gate_catalog_invalid", "the catalog names no languages")
    )


def _gate(entry: dict[str, Any], languages: tuple[str, ...]) -> Result[Gate]:
    gate_id = str(entry.get("id", ""))
    options = tuple(
        Option(
            str(option.get("id", "")),
            dict(option.get("label", {})),
            dict(option.get("detail", {})),
        )
        for option in entry.get("option", ())
    )
    gate = Gate(
        id=gate_id,
        question=dict(entry.get("question", {})),
        options=options,
        free_text=bool(entry.get("free_text", False)),
        approval=bool(entry.get("approval", False)),
        artifact=bool(entry.get("artifact", False)),
        recommended=str(entry.get("recommended", "")),
        binds=str(entry.get("binds", "")),
    )
    problems = _problems(gate, languages)
    return (
        Ok(gate)
        if not problems
        else err("gate_catalog_invalid", f"gate {gate_id or '?'}: {problems[0]}")
    )


def _problems(gate: Gate, languages: tuple[str, ...]) -> list[str]:
    ids = [option.id for option in gate.options]
    found = [
        problem
        for problem, failed in (
            ("needs an id", not gate.id),
            ("needs one to three options", not 1 <= len(gate.options) <= 3),
            ("has repeated option ids", len(set(ids)) != len(ids)),
            (
                "recommends an option it does not offer",
                bool(gate.recommended) and gate.recommended not in ids,
            ),
            ("has an unknown binds value", not _BINDS.match(gate.binds)),
            ("binds only matter for approvals", bool(gate.binds) and not gate.approval),
            (
                "cannot both approve and take free text",
                gate.approval and gate.free_text,
            ),
        )
        if failed
    ]
    for language in languages:
        texts = [gate.question.get(language, "")] + [
            text
            for option in gate.options
            for text in (
                option.label.get(language, ""),
                option.detail.get(language, ""),
            )
        ]
        if not all(text.strip() for text in texts):
            found.append(f"is missing {language} text")
        labels = [option.label.get(language, "") for option in gate.options]
        if len({questions.choice_label(label).casefold() for label in labels}) != len(
            labels
        ):
            found.append(f"repeats an option label in {language}")
        if gate.approval and not any(
            label.casefold() in questions.APPROVE_LABELS for label in labels
        ):
            found.append(f"approves writes without an Approve option in {language}")
        if _text_slots(gate, language) != _text_slots(gate, languages[0]):
            found.append(f"uses different slots in {language}")
    return found


def _text_slots(gate: Gate, language: str) -> set[str]:
    texts = [gate.question.get(language, "")] + [
        text
        for option in gate.options
        for text in (option.label.get(language, ""), option.detail.get(language, ""))
    ]
    return {slot for text in texts for slot in _SLOT.findall(text)}


def _slots(gate: Gate, language: str) -> set[str]:
    """Every value the gate needs: its text's slots and the slot its approval binds to."""
    return _text_slots(gate, language) | set(_SLOT.findall(gate.binds))


def render(
    gate_id: str,
    language: str,
    values: dict[str, str],
    recommended: str | None = None,
    path: Path = CATALOG,
) -> Result[Rendered]:
    """One gate in `language` with its slots filled; never in any other wording."""
    match load(path):
        case Err() as failure:
            return failure
        case Ok((languages, gates)):
            pass
    gate = gates.get(gate_id)
    if gate is None:
        return err(
            "gate_unknown", f"no gate {gate_id!r}; known: {', '.join(sorted(gates))}"
        )
    language = language if language in languages else languages[0]
    needed = _slots(gate, language)
    if set(values) != needed:
        return err(
            "gate_values",
            f"gate {gate_id} needs values for {sorted(needed) or 'nothing'}, got {sorted(values)}",
        )
    if any(
        not value.strip() or "{" in value or "}" in value for value in values.values()
    ):
        return err("gate_values", "gate values must be plain, non-empty text")
    chosen = recommended if recommended is not None else gate.recommended
    if chosen and chosen not in {option.id for option in gate.options}:
        return err("gate_values", f"gate {gate_id} has no option {chosen!r}")

    def fill(text: str) -> str:
        return _SLOT.sub(lambda match: values[match.group(1)], text)

    return Ok(
        Rendered(
            gate=gate.id,
            question=fill(gate.question[language]),
            options=tuple(
                fill(option.label[language])
                + (f" ({RECOMMENDED[language]})" if option.id == chosen else "")
                for option in gate.options
            ),
            details=tuple(fill(option.detail[language]) for option in gate.options),
            free_text=gate.free_text,
            approval=gate.approval,
            artifact=gate.artifact,
            bound=gate.approval and bool(gate.binds),
            target=_target(gate.binds, fill),
        )
    )


def _target(binds: str, fill: Any) -> tuple[str, str] | None:
    match binds.split(":", 1):
        case [kind, slot]:
            return (kind, fill(slot))
        case _:
            return None
