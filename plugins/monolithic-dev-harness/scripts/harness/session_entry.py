"""Discover ordinary saved work without selecting a session on the user's behalf."""

import fcntl
import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path

from core.result import Ok, Result, attempt, bind, err, fmap
from harness import decisions, questions, state, work_sessions, workflow
from host_adapters import (
    StartEvent,
    hook_bridge,
    native_session_id,
    work_session_context,
)
from host_adapters.interactions import (
    chat_menu,
    normalize_human_reply,
    normalize_question,
    question_transport,
)


@dataclass(frozen=True)
class Candidates:
    sessions: tuple[work_sessions.Session, ...]
    damaged: tuple[Path, ...]
    unfinished_setup: bool


@dataclass(frozen=True)
class Option:
    key: str
    request: str = ""


@dataclass(frozen=True)
class Offer:
    request: str
    options: tuple[Option, ...]
    page: int = 0


def _offer_path(repo: Path, host: str, conversation: str) -> Result[Path]:
    match host, conversation.strip():
        case (("codex" | "claude" | "cursor"), str() as identity) if identity:
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            return Ok(
                repo / ".harness" / "state" / "session-entry" / host / f"{digest}.json"
            )
        case _:
            return err(
                "entry_identity_missing", "A trusted host conversation is required."
            )


def _write_entry(path: Path, payload: dict) -> None:
    """Make the control journal durable before acknowledging its state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(12)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def offer(repo: Path, host: str, conversation: str, request: str) -> Result[Offer]:
    """Prepare options only; this record does not select work or authorize a reply."""
    return bind(
        _offer_path(repo, host, conversation),
        lambda path: bind(
            attempt(
                lambda: _offer_locked(repo, path, conversation, request),
                "entry_unavailable",
                "Could not prepare saved-work options",
                OSError,
                UnicodeError,
            ),
            lambda result: result,
        ),
    )


def current_offer(repo: Path, host: str, conversation: str) -> Result[Offer]:
    """Read this conversation's pending entry menu without creating or changing it."""
    return bind(
        _offer_path(repo, host, conversation),
        lambda path: _current_offer(path),
    )


def current_offer_for_request(repo: Path, host: str, request: str) -> Result[Offer]:
    """Resolve only a unique pending offer for text-only hosts that lack CLI session env."""
    return bind(
        _offer_path(repo, host, "offer-lookup"),
        lambda probe: _find_offer_for_request(probe.parent, request.strip()),
    )


def _find_offer_for_request(folder: Path, request: str) -> Result[Offer]:
    matches = tuple(
        offer
        for path in folder.glob("*.json")
        for result in (_current_offer(path),)
        if isinstance(result, Ok)
        for offer in (result.value,)
        if not request or offer.request == request
    )
    match matches:
        case (Offer() as found,):
            return Ok(found)
        case ():
            return err("entry_missing", "No saved-work choice matches this request.")
        case _:
            return err(
                "entry_ambiguous",
                "More than one conversation has this pending saved-work request; present it from a conversation with a supported native identity.",
            )


def selected(repo: Path, host: str, conversation: str) -> str | None:
    match _offer_path(repo, host, conversation):
        case Ok(path):
            match state.read_json(path) if path.is_file() else None:
                case {"status": "complete", "selected": str() as identifier}:
                    return identifier
                case _:
                    return None
        case _:
            return None


def _current_offer(path: Path) -> Result[Offer]:
    match state.read_json(path) if path.is_file() else None:
        case {"status": "pending"} as record:
            match _decoded_offer(record):
                case Offer() as prepared:
                    return Ok(prepared)
                case _:
                    pass
        case _:
            pass
    return err("entry_missing", "No saved-work choice is waiting in this conversation.")


def _offer_locked(
    repo: Path, path: Path, conversation: str, request: str
) -> Result[Offer]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _prepare_offer(repo, path, conversation, request)


def _prepare_offer(
    repo: Path, path: Path, conversation: str, request: str
) -> Result[Offer]:
    match request.strip(), path.exists():
        case "", _:
            return err("entry_request_missing", "The original request is required.")
        case _, True:
            return _existing_offer(path, request)
        case cleaned, False:
            found = candidates(repo, conversation)
            created = Offer(cleaned, options(found))
            _write_entry(
                path,
                {
                    "version": 1,
                    "status": "pending",
                    **asdict(created),
                    "saved_sessions": [
                        {"id": session.id, "request": session.request}
                        for session in found.sessions
                    ],
                },
            )
            return Ok(created)


def _existing_offer(path: Path, request: str) -> Result[Offer]:
    match state.read_json(path):
        case {
            "version": 1,
            "status": "pending",
            "request": str() as saved,
            "options": list() as items,
        } as record if saved == request.strip():
            match tuple(
                Option(item["key"], item["request"])
                for item in items
                if isinstance(item, dict)
                and isinstance(item.get("key"), str)
                and isinstance(item.get("request"), str)
            ):
                case decoded if len(decoded) == len(items):
                    page = record.get("page", 0)
                    match isinstance(page, int) and page >= 0:
                        case True:
                            return Ok(Offer(saved, decoded, page))
                        case False:
                            pass
        case _:
            pass
    return err(
        "entry_conflict",
        "The saved-work choice must be resolved before changing the request.",
    )


def question(prepared: Offer, language: str) -> dict:
    portuguese = language == "pt-br"
    labels = {
        "new:pause": "Começar novo — pausar o trabalho salvo"
        if portuguese
        else "Start new — pause the saved work",
        "new:stop": "Começar novo — parar o trabalho salvo"
        if portuguese
        else "Start new — stop the saved work",
        "new:pause-all": "Pausar os trabalhos salvos"
        if portuguese
        else "Pause all saved work",
        "new:stop-all": "Parar os trabalhos salvos"
        if portuguese
        else "Stop all saved work",
        "new": "Começar novo" if portuguese else "Start new",
        "setup": "Continuar a configuração pendente"
        if portuguese
        else "Continue the unfinished setup",
        "more": "Mais opções" if portuguese else "More choices",
        "more_saved": "Mais trabalhos salvos" if portuguese else "More saved work",
    }
    visible = _visible_options(prepared)
    return {
        "question": (
            (
                "O que fazer com os trabalhos salvos?"
                if portuguese
                else "What should happen to the saved work?"
            )
            if any(option.key == "new:pause-all" for option in prepared.options)
            else (
                "Qual trabalho você quer fazer nesta conversa?"
                if portuguese
                else "Which work do you want to do in this conversation?"
            )
        ),
        "options": [
            {
                "label": (
                    f"{'Continuar' if portuguese else 'Continue'} {index}: {option.request}"
                    if option.key.startswith("continue:")
                    else labels[option.key]
                )
            }
            for index, option in enumerate(visible, start=prepared.page * 2 + 1)
        ],
    }


def _visible_options(prepared: Offer) -> tuple[Option, ...]:
    start = prepared.page * 2
    remaining = prepared.options[start:]
    match len(prepared.options) <= 3 or len(remaining) <= 3:
        case True:
            return remaining
        case False:
            visible = remaining[:2]
            return (
                *visible,
                Option(
                    "more_saved"
                    if any(
                        item.key.startswith("continue:")
                        for item in remaining[len(visible) :]
                    )
                    else "more"
                ),
            )


def _decoded_offer(record: dict) -> Offer | None:
    match record:
        case {"version": 1, "request": str() as request, "options": list() as items}:
            decoded = tuple(
                Option(item["key"], item["request"])
                for item in items
                if isinstance(item, dict)
                and isinstance(item.get("key"), str)
                and isinstance(item.get("request"), str)
            )
            page = record.get("page", 0)
            return (
                Offer(request, decoded, page)
                if len(decoded) == len(items) and isinstance(page, int) and page >= 0
                else None
            )
        case _:
            return None


def observe(repo: Path, host: str, payload: dict) -> Result[bool]:
    """Observe a host presentation; an unprepared or changed question is not a choice."""
    conversation = native_session_id(host, payload)
    identifier = hook_bridge.question_id(payload)
    match conversation, identifier:
        case str() as conversation, str() as identifier if conversation and identifier:
            return bind(
                _offer_path(repo, host, conversation),
                lambda path: (
                    _under_lock(
                        path, lambda: _observe_locked(path, host, identifier, payload)
                    )
                    if path.is_file()
                    else Ok(False)
                ),
            )
        case _:
            return Ok(False)


def observe_chat_response(repo: Path, host: str, payload: dict) -> Result[bool]:
    """Record Cursor's completed assistant message only when it contains our exact menu."""
    conversation = native_session_id(host, payload)
    generation = payload.get("generation_id")
    text = payload.get("text")
    match host, conversation, generation, text:
        case "cursor", str() as conversation, str() as generation, str() as text if (
            conversation and generation and text
        ):
            return bind(
                _offer_path(repo, host, conversation),
                lambda path: (
                    _under_lock(
                        path,
                        lambda: _observe_chat_response_locked(path, generation, text),
                    )
                    if path.is_file()
                    else Ok(False)
                ),
            )
        case _:
            return Ok(False)


def _observe_chat_response_locked(
    path: Path, generation: str, text: str
) -> Result[bool]:
    record = state.read_json(path) or {}
    prepared = _decoded_offer(record)
    match prepared, record.get("status"):
        case Offer() as prepared, "pending" if (
            record.get("prompt_generation_id", generation) == generation
        ):
            expected = next(
                (
                    (question(prepared, language), language)
                    for language in ("en", "pt-br")
                    if _chat_entry_menu(prepared, language) in text
                ),
                None,
            )
            match expected:
                case (dict() as shown, str() as _language):
                    _write_entry(
                        path,
                        {
                            **record,
                            "presented": f"cursor-response:{generation}",
                            "presented_generation": generation,
                            "input": {"questions": [shown]},
                            "transport": "chat",
                        },
                    )
                    return Ok(True)
        case _:
            pass
    return Ok(False)


def _chat_entry_menu(prepared: Offer, language: str) -> str:
    wording = question(prepared, language)
    return chat_menu(
        {
            **wording,
            "options": [{"label": item["label"]} for item in wording["options"]],
        },
        False,
        language,
    )


def note_prompt(repo: Path, host: str, payload: dict) -> Result[None]:
    """Expire a Cursor text menu on the first unrelated prompt; reject late response hooks."""
    conversation = native_session_id(host, payload)
    generation = payload.get("generation_id")
    match host, conversation, generation:
        case "cursor", str() as conversation, str() as generation if conversation:
            return bind(
                _offer_path(repo, host, conversation),
                lambda path: (
                    _under_lock(path, lambda: _note_prompt_locked(path, generation))
                    if path.is_file()
                    else Ok(None)
                ),
            )
        case _:
            return Ok(None)


def _note_prompt_locked(path: Path, generation: str) -> Result[None]:
    record = state.read_json(path) or {}
    match record:
        case {"status": "pending", "transport": "chat"}:
            _write_entry(
                path,
                {
                    **record,
                    "presented": "",
                    "presented_generation": "",
                    "input": {},
                    "transport": "",
                    "prompt_generation_id": generation,
                },
            )
            return Ok(None)
        case {"status": "pending"}:
            _write_entry(path, {**record, "prompt_generation_id": generation})
            return Ok(None)
        case _:
            return Ok(None)


def _under_lock(path: Path, action):
    return bind(
        attempt(
            lambda: _locked_action(path, action),
            "entry_unavailable",
            "Saved-work control unavailable",
            OSError,
            UnicodeError,
        ),
        lambda result: result,
    )


def _locked_action(path: Path, action):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return action()


def _observe_locked(
    path: Path, host: str, identifier: str, payload: dict
) -> Result[bool]:
    record = state.read_json(path) or {}
    prepared = _decoded_offer(record)
    observed = normalize_question(host, hook_bridge.question_input(payload))
    match prepared, record.get("status"), observed:
        case Offer() as prepared, "pending", {"questions": [dict() as shown]} if (
            not observed.get("answers")
            and not shown.get("answers")
            and not shown.get("multiSelect")
        ):
            expected = next(
                (
                    candidate
                    for language in ("en", "pt-br")
                    for candidate in (question(prepared, language),)
                    if shown.get("question") == candidate["question"]
                    and len(shown.get("options", ())) == len(candidate["options"])
                    and all(
                        isinstance(item, dict) and not item.get("description")
                        for item in shown.get("options", ())
                    )
                    and tuple(
                        item.get("label")
                        for item in shown.get("options", ())
                        if isinstance(item, dict)
                    )
                    == tuple(item["label"] for item in candidate["options"])
                ),
                None,
            )
            match expected:
                case dict():
                    _write_entry(
                        path,
                        {
                            **record,
                            "presented": identifier,
                            "input": observed,
                            "transport": question_transport(
                                host, str(payload.get("tool_name", ""))
                            ),
                        },
                    )
                    return Ok(True)
        case _:
            pass
    return Ok(False)


def answer(repo: Path, host: str, payload: dict) -> Result[str | None]:
    """Record only the option in the matching observed host reply, once."""
    conversation = native_session_id(host, payload)
    match conversation, hook_bridge.question_id(payload):
        case str() as conversation, str() as identifier if conversation and identifier:
            return bind(
                _offer_path(repo, host, conversation),
                lambda path: (
                    bind(
                        _journal_reply(path, identifier, payload),
                        lambda _: _under_lock(
                            path, lambda: _answer_locked(path, identifier, payload)
                        ),
                    )
                    if _native_reply_matches(path, identifier, payload)
                    else Ok(None)
                ),
            )
        case _:
            return Ok(None)


def _native_reply_matches(path: Path, identifier: str, payload: dict) -> bool:
    match state.read_json(path) or {}, hook_bridge.answer_response(payload):
        case {
            "status": "pending",
            "presented": str() as shown_id,
            "input": {"questions": [dict() as shown]} as input_,
        }, Ok(dict() as response) if shown_id == identifier:
            return questions.answer(input_, response) in tuple(
                option["label"] for option in shown["options"]
            )
        case _:
            return False


def _journal_reply(path: Path, identifier: str, payload: dict) -> Result[None]:
    """Keep host evidence before taking the contested offer lock; never overwrite collisions."""
    return bind(
        attempt(
            lambda: _persist_reply(path, identifier, payload),
            "entry_evidence_unavailable",
            "Could not retain the human reply",
            OSError,
            ValueError,
        ),
        lambda result: result,
    )


def _persist_reply(path: Path, identifier: str, payload: dict) -> Result[None]:
    folder = path.parent / (path.stem + "-replies")
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (hashlib.sha256(identifier.encode()).hexdigest() + ".json")
    value = {"identifier": identifier, "payload": payload}
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    temp = folder / ("." + secrets.token_hex(16) + ".tmp")
    try:
        with temp.open("xb") as file:
            file.write(serialized)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(temp, destination)
        except FileExistsError:
            return (
                Ok(None)
                if destination.read_bytes() == serialized
                else err(
                    "entry_reply_collision",
                    "A different reply was already retained for this presentation; inspect the control.",
                )
            )
        descriptor = os.open(folder, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return Ok(None)
    finally:
        temp.unlink(missing_ok=True)


def recover_reply(repo: Path, host: str, conversation: str) -> Result[str | None]:
    return bind(
        _offer_path(repo, host, conversation),
        lambda path: (
            _under_lock(path, lambda: _recover_locked(path, host, conversation))
            if path.is_file()
            else Ok(None)
        ),
    )


def _recover_locked(path: Path, host: str, conversation: str) -> Result[str | None]:
    record = state.read_json(path) or {}
    match record.get("status"), record.get("presented"):
        case "pending", str() as identifier if identifier:
            evidence = (
                path.parent
                / (path.stem + "-replies")
                / (hashlib.sha256(identifier.encode()).hexdigest() + ".json")
            )
            match state.read_json(evidence):
                case {"identifier": str() as saved, "payload": dict() as payload} if (
                    saved == identifier
                    and native_session_id(host, payload) == conversation
                    and hook_bridge.question_id(payload) == identifier
                ):
                    match payload:
                        case {"session_entry_prompt": str() as prompt}:
                            return _answer_prompt_locked(path, host, prompt)
                        case _:
                            return _answer_locked(path, identifier, payload)
        case _:
            pass
    return Ok(None)


def _answer_locked(path: Path, identifier: str, payload: dict) -> Result[str | None]:
    record = state.read_json(path) or {}
    prepared = _decoded_offer(record)
    match prepared, record, hook_bridge.answer_response(payload):
        case Offer() as prepared, {
            "status": "pending",
            "presented": str() as seen,
            "input": dict() as shown,
        }, Ok(dict() as response) if seen == identifier:
            selected = questions.answer(shown, response)
            return _store_answer(path, record, prepared, shown, selected)
        case _:
            pass
    return Ok(None)


def _store_answer(
    path: Path, record: dict, prepared: Offer, shown: dict, selected: str | None
) -> Result[str | None]:
    labels = tuple(item.get("label") for item in shown["questions"][0]["options"])
    match tuple(
        option.key
        for option, label in zip(_visible_options(prepared), labels, strict=True)
        if label == selected
    ):
        case (str() as key,):
            _write_entry(path, {**record, "status": "answered", "selection": key})
            return Ok(key)
        case _:
            return Ok(None)


def answer_prompt(
    repo: Path, host: str, conversation: str, prompt: str
) -> Result[str | None]:
    return bind(
        _offer_path(repo, host, conversation),
        lambda path: (
            _journal_prompt(path, host, conversation, prompt)
            if path.is_file()
            else Ok(None)
        ),
    )


def _journal_prompt(
    path: Path, host: str, conversation: str, prompt: str
) -> Result[str | None]:
    record = state.read_json(path) or {}
    match record:
        case {
            "status": "pending",
            "presented": str() as identifier,
            "input": {"questions": [dict() as shown]},
            "transport": str() as transport,
        } if transport in ("blocking", "async", "chat"):
            labels = tuple(item["label"] for item in shown["options"])
            pending = decisions.Pending(
                identifier,
                shown["question"],
                labels,
                transport,
                False,
                None,
                presentation_id=identifier,
            )
            match normalize_human_reply(host, prompt, pending):
                case None:
                    return Ok(None)
                case reply if reply.answer not in labels:
                    return Ok(None)
                case _:
                    payload = {
                        **(
                            {"conversation_id": conversation}
                            if host == "cursor"
                            else {"session_id": conversation}
                        ),
                        "tool_use_id": identifier,
                        "session_entry_prompt": prompt,
                    }
                    return bind(
                        _journal_reply(path, identifier, payload),
                        lambda _: _under_lock(
                            path, lambda: _answer_prompt_locked(path, host, prompt)
                        ),
                    )
        case _:
            return Ok(None)


def _answer_prompt_locked(path: Path, host: str, prompt: str) -> Result[str | None]:
    record = state.read_json(path) or {}
    prepared = _decoded_offer(record)
    match prepared, record:
        case Offer() as prepared, {
            "status": "pending",
            "presented": str() as identifier,
            "input": {"questions": [dict() as shown]},
            "transport": str() as transport,
        }:
            labels = tuple(item["label"] for item in shown["options"])
            pending = decisions.Pending(
                identifier,
                shown["question"],
                labels,
                transport,
                False,
                None,
                presentation_id=identifier,
            )
            match normalize_human_reply(host, prompt, pending):
                case None:
                    return Ok(None)
                case reply:
                    return _store_answer(
                        path, record, prepared, record["input"], reply.answer
                    )
        case _:
            return Ok(None)


def apply_selection(repo: Path, host: str, conversation: str) -> Result[str]:
    """Apply a captured human choice under the entry lock, retrying recorded steps."""
    return bind(
        _offer_path(repo, host, conversation),
        lambda path: (
            _under_lock(path, lambda: _apply_locked(repo, host, conversation, path))
            if path.is_file()
            else err("entry_missing", "No saved-work choice was prepared.")
        ),
    )


def _apply_locked(repo: Path, host: str, conversation: str, path: Path) -> Result[str]:
    record = state.read_json(path) or {}
    match record:
        case {"status": "complete", "selected": str() as selected}:
            return Ok(selected)
        case {"status": "answered", "selection": str() as choice}:
            return _start_apply(repo, host, conversation, path, record, choice)
        case {"status": "applying", "selection": str(), "selected": str()}:
            return _apply_record(repo, host, conversation, path, record)
        case _:
            return err(
                "entry_unanswered", "A real user must answer the saved-work choice."
            )


def _start_apply(
    repo: Path, host: str, conversation: str, path: Path, record: dict, choice: str
) -> Result[str]:
    prepared = _decoded_offer(record)
    match prepared, choice:
        case Offer(page=page) as prepared, "more" | "more_saved" if choice in tuple(
            option.key for option in _visible_options(prepared)
        ):
            _write_entry(
                path,
                {
                    **record,
                    "status": "pending",
                    "page": page + 1,
                    "presented": "",
                    "input": {},
                    "transport": "",
                },
            )
            return err(
                "entry_more_options",
                "A later saved-work choice page is ready; present it through the host question tool.",
            )
        case Offer(options=options), "new" if (
            len(
                tuple(
                    option for option in options if option.key.startswith("continue:")
                )
            )
            > 1
        ):
            following = (Option("new:pause-all"), Option("new:stop-all"))
            _write_entry(
                path,
                {
                    "version": 1,
                    "status": "pending",
                    "request": record["request"],
                    "options": [asdict(option) for option in following],
                    "prior_options": record["options"],
                    "saved_sessions": record.get("saved_sessions", []),
                },
            )
            return err(
                "entry_disposition_required",
                "Ask what should happen to the saved work before starting new work.",
            )
        case Offer() as prepared, str() as choice if choice in tuple(
            option.key for option in prepared.options
        ) and choice.startswith("continue:"):
            selected = choice.removeprefix("continue:")
        case (
            Offer() as prepared,
            "new:pause" | "new:stop" | "new:pause-all" | "new:stop-all",
        ):
            selected = "WS-" + secrets.token_hex(12)
        case Offer() as prepared, "setup" if any(
            option.key == "setup" for option in prepared.options
        ):
            selected = "setup"
        case _:
            return err(
                "entry_choice_unsupported",
                "This saved-work choice cannot yet be applied.",
            )
    next_record = {**record, "status": "applying", "selected": selected}
    _write_entry(path, next_record)
    return _apply_record(repo, host, conversation, path, next_record)


def _apply_record(
    repo: Path, host: str, conversation: str, path: Path, record: dict
) -> Result[str]:
    choice = record["selection"]
    match choice:
        case str() as selected if selected.startswith("continue:"):
            return bind(
                _handover_pending(repo, record["selected"], conversation),
                lambda _: bind(
                    _resume_choice(repo, record["selected"]),
                    lambda session: bind(
                        _sync_effect(session.folder / "session.json"),
                        lambda _: _finish_binding(
                            repo, host, conversation, path, record
                        ),
                    ),
                ),
            )
        case "new:pause" | "new:stop" | "new:pause-all" | "new:stop-all":
            return bind(
                _disposition(
                    repo,
                    record,
                    "pause" if choice in ("new:pause", "new:pause-all") else "stop",
                ),
                lambda old: bind(
                    _sync_sessions(old),
                    lambda _: bind(
                        work_sessions.create_reserved(
                            repo, record["request"], record["selected"]
                        ),
                        lambda session: bind(
                            _sync_effect(session.folder / "session.json"),
                            lambda _: _finish_binding(
                                repo, host, conversation, path, record
                            ),
                        ),
                    ),
                ),
            )
        case "setup":
            return bind(
                decisions.hand_over(repo, None, conversation),
                lambda _: _complete_entry(path, record, "setup"),
            )
        case _:
            return err(
                "entry_choice_unsupported",
                "This saved-work choice cannot yet be applied.",
            )


def _resume_choice(repo: Path, identifier: str) -> Result[work_sessions.Session]:
    match work_sessions.select(repo, identifier):
        case Ok(session) if session.mode_session:
            return err(
                "entry_invalid", "A mode session cannot be selected as saved work."
            )
        case Ok(session) if _unscoped_pending(decisions.record(repo, identifier) or {}):
            return err(
                "entry_handover_required",
                "The saved question must be handed over before continuing.",
            )
        case Ok(session) if session.status == work_sessions.Status.ACTIVE:
            return Ok(session)
        case Ok(session) if session.status in (
            work_sessions.Status.PAUSED,
            work_sessions.Status.STOPPED,
        ):
            return work_sessions.transition(
                repo, identifier, "resume", make_current=False
            )
        case Ok():
            return err("entry_invalid", "Completed work cannot be continued.")
        case failure:
            return failure


def _handover_pending(repo: Path, identifier: str, conversation: str) -> Result[None]:
    record = decisions.record(repo, identifier) or {}
    return (
        fmap(decisions.hand_over(repo, identifier, conversation), lambda _: None)
        if record.get("status") == "pending" and not _unscoped_pending(record)
        else Ok(None)
    )


def _unscoped_pending(record: dict) -> bool:
    """An older unknown-origin question needs explicit repair before binding a new chat."""
    return record.get("status") == "pending" and not (
        record.get("native_session_id") or record.get("presented_in")
    )


def _disposition(
    repo: Path, record: dict, operation: str
) -> Result[tuple[work_sessions.Session, ...]]:
    source = {**record, "options": record.get("prior_options", record.get("options"))}
    prepared = _decoded_offer(source)
    all_saved = tuple(
        item["id"]
        for item in record.get("saved_sessions", ())
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    )
    match prepared, all_saved:
        case Offer(), identifiers if identifiers:
            return _dispose_many(repo, identifiers, operation)
        case Offer(options=options), ():
            match tuple(
                option.key.removeprefix("continue:")
                for option in options
                if option.key.startswith("continue:")
            ):
                case identifiers if identifiers:
                    return _dispose_many(repo, identifiers, operation)
        case _:
            pass
    return err("entry_invalid", "The saved-work disposition is ambiguous.")


def _dispose_many(
    repo: Path, identifiers: tuple[str, ...], operation: str
) -> Result[tuple[work_sessions.Session, ...]]:
    match identifiers:
        case ():
            return Ok(())
        case (identifier, *remaining):
            return bind(
                work_sessions.select(repo, identifier),
                lambda session: bind(
                    _dispose_one(repo, session, operation),
                    lambda updated: bind(
                        _sync_effect(updated.folder / "session.json"),
                        lambda _: bind(
                            _dispose_many(repo, tuple(remaining), operation),
                            lambda tail: Ok((updated, *tail)),
                        ),
                    ),
                ),
            )


def _sync_sessions(sessions: tuple[work_sessions.Session, ...]) -> Result[None]:
    match sessions:
        case ():
            return Ok(None)
        case (session, *remaining):
            return bind(
                _sync_effect(session.folder / "session.json"),
                lambda _: _sync_sessions(tuple(remaining)),
            )


def _dispose_one(
    repo: Path, session: work_sessions.Session, operation: str
) -> Result[work_sessions.Session]:
    match session.status, operation:
        case work_sessions.Status.ACTIVE, _:
            return work_sessions.transition(
                repo, session.id, operation, make_current=False
            )
        case work_sessions.Status.PAUSED, "stop":
            return work_sessions.transition(
                repo, session.id, "stop", make_current=False
            )
        case ((work_sessions.Status.PAUSED | work_sessions.Status.STOPPED), _):
            return Ok(session)
        case _:
            return err(
                "entry_invalid", "The saved work changed before the choice was applied."
            )


def _finish_binding(
    repo: Path, host: str, conversation: str, path: Path, record: dict
) -> Result[str]:
    return bind(
        work_session_context.bind_session(repo, host, conversation, record["selected"]),
        lambda selected: bind(
            work_session_context._path(repo, host, conversation),
            lambda binding: bind(
                _sync_effect(binding), lambda _: _complete_entry(path, record, selected)
            ),
        ),
    )


def _sync_effect(path: Path) -> Result[None]:
    return attempt(
        lambda: _fsync_effect(path),
        "entry_sync_failed",
        "Could not persist the saved-work transition",
        OSError,
    )


def _fsync_effect(path: Path) -> None:
    with path.open("rb") as file:
        os.fsync(file.fileno())
    directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _complete_entry(path: Path, record: dict, selected: str) -> Result[str]:
    _write_entry(path, {**record, "status": "complete", "selected": selected})
    return Ok(selected)


def candidates(repo: Path, conversation: str = "") -> Candidates:
    sessions, damaged = work_sessions.scan(repo)
    decision = decisions.record(repo) or {}
    eligible = tuple(
        session
        for session in work_sessions.chosen_among(sessions)
        if session.status
        in (
            work_sessions.Status.ACTIVE,
            work_sessions.Status.PAUSED,
            work_sessions.Status.STOPPED,
        )
    )
    return Candidates(
        sessions=tuple(
            sorted(eligible, key=lambda item: (item.updated_at, item.id), reverse=True)
        ),
        damaged=damaged,
        unfinished_setup=(
            decision.get("status") == "pending"
            and decisions.onboarding_question(decision)
            and bool(decision.get("native_session_id"))
            and decision.get("native_session_id") != conversation
        ),
    )


def options(found: Candidates) -> tuple[Option, ...]:
    choices = tuple(
        Option(f"continue:{session.id}", session.request) for session in found.sessions
    )
    match len(found.sessions):
        case 0:
            new = (Option("new"),)
        case 1:
            new = (Option("new:pause"), Option("new:stop"))
        case _:
            new = (Option("new"),)
    return (*choices, *new, *((Option("setup"),) if found.unfinished_setup else ()))


def on_start(repo: Path, host: str, event: StartEvent) -> str | None:
    match event:
        case StartEvent(subagent=True):
            return None
        case _:
            return _start_context(repo, host, event.conversation)


def _start_context(repo: Path, host: str, conversation: str) -> str | None:
    match work_session_context.resolve_session(repo, host, conversation):
        case Ok(str() as identifier):
            return _bound_context(repo, identifier)
        case Ok(None):
            found = candidates(repo, conversation)
            match found.sessions, found.unfinished_setup:
                case (), False:
                    return None
                case sessions, unfinished:
                    descriptions = tuple(
                        session.request for session in sessions[:3]
                    ) + (("unfinished project setup",) if unfinished else ())
                    return "Saved work is available: " + "; ".join(descriptions) + "."
        case _:
            return None


def _bound_context(repo: Path, identifier: str) -> str | None:
    match work_sessions.select(repo, identifier):
        case Ok(session) if not session.mode_session:
            pending = decisions.pending(repo, identifier)
            checkpoint = workflow.load(repo, identifier)
            return " ".join(
                (
                    f"Saved work {session.id}: {session.request} ({session.status.value}).",
                    f"Checkpoint: {checkpoint.value.current.label}."
                    if isinstance(checkpoint, Ok)
                    else "",
                    f"Waiting question: {pending.question}." if pending else "",
                    "Run harness begin to continue.",
                )
            )
        case _:
            return None
