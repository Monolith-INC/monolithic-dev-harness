"""Pure, immutable source-method selection transitions."""

from dataclasses import dataclass, replace

from core.result import Ok, Result, err


@dataclass(frozen=True)
class SelectionState:
    selected: tuple[str, ...] = ()
    outcomes: tuple[tuple[str, str, str, str], ...] = ()
    phase: str = "choose"
    page: int = 0
    mode: str = "shortlist"
    pool: tuple[str, ...] = ()
    revision: int = 0
    events: tuple[str, ...] = ()
    directions: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelectionEvent:
    action: str
    methods: tuple[str, ...] = ()
    artifact: str = ""
    digest: str = ""


def reduce_selection(
    current: SelectionState, event: SelectionEvent
) -> Result[SelectionState]:
    match event.action, current.phase:
        case "add", "choose":
            return Ok(
                replace(
                    current,
                    selected=tuple(dict.fromkeys((*current.selected, *event.methods))),
                    revision=current.revision + 1,
                    mode="catalog" if current.mode == "catalog" else "shortlist",
                )
            )
        case "finish", "choose":
            return Ok(
                replace(
                    current,
                    phase="apply"
                    if len(current.outcomes) < len(current.selected)
                    else "hardening",
                    revision=current.revision + 1,
                )
            )
        case "accept_set", "choose":
            return Ok(
                replace(
                    current,
                    selected=tuple(dict.fromkeys((*current.selected, *event.methods))),
                    phase="apply",
                    revision=current.revision + 1,
                )
            )
        case "individual", "choose":
            return Ok(replace(current, mode="shortlist", revision=current.revision + 1))
        case "reopen", _:
            return Ok(replace(current, phase="choose", revision=current.revision + 1))
        case "next", "choose":
            return Ok(
                replace(current, page=current.page + 1, revision=current.revision + 1)
            )
        case "more", "choose":
            return Ok(replace(current, mode="actions", revision=current.revision + 1))
        case "catalog", "choose":
            return Ok(
                replace(current, mode="catalog", page=0, revision=current.revision + 1)
            )
        case "reshuffle", "choose":
            return Ok(
                replace(
                    current,
                    pool=event.methods,
                    mode="shortlist",
                    page=0,
                    revision=current.revision + 1,
                )
            )
        case "apply" | "reject", "apply" if len(current.outcomes) < len(
            current.selected
        ):
            return Ok(
                replace(
                    current,
                    outcomes=(
                        *current.outcomes,
                        (
                            current.selected[len(current.outcomes)],
                            event.action,
                            event.artifact,
                            event.digest,
                        ),
                    ),
                    phase="hardening"
                    if len(current.outcomes) + 1 == len(current.selected)
                    else "apply",
                    revision=current.revision + 1,
                )
            )
        case "direction", _:
            return Ok(replace(current, revision=current.revision + 1))
        case _:
            return err(
                "invalid_elicitation_transition",
                "That action does not match the saved method-selection phase.",
            )
