"""Host-bound observations for the optional knowledge-first mode hook."""

from pathlib import Path
from typing import Any

from project_knowledge import freshness

from core.result import Err, Ok, attempt
from harness import (
    commands,
    knowledge_first,
    knowledge_first_store,
    modes,
    rules,
    settings,
    state,
)
from host_adapters import hook_bridge, native_session_id

_STATE_NOTICE = "The knowledge-first reminder state is unavailable; this read is allowed without the gate."


def _state_notice() -> rules.Decision:
    return rules.Decision(True, "knowledge-first", _STATE_NOTICE)


def _context(repo: Path, host: str, payload: dict[str, Any]) -> tuple[str, Path] | None:
    conversation = native_session_id(host, payload) or ""
    match state.harness_mode(repo), modes.active(repo), settings.load(repo):
        case "suspended", _, _:
            return None
        case _, modes.Active(manifest=mode), Ok(chosen) if (
            conversation
            and mode.knowledge == "first"
            and "knowledge_first" in mode.hooks
            and chosen.knowledge_format == "markdown"
        ):
            root = (
                Path(chosen.knowledge_root)
                if chosen.knowledge_root
                else Path(chosen.artifacts_path) / "Project_Knowledge"
            )
            return conversation, (repo / root).resolve()
        case _:
            return None


def prompt(repo: Path, host: str, payload: dict[str, Any]) -> None:
    match _context(repo, host, payload):
        case (conversation, _):
            knowledge_first_store.begin_prompt(repo, host, conversation)
        case _:
            pass


def _classify(
    repo: Path, root: Path, call: rules.ToolCall, payload: dict[str, Any]
) -> knowledge_first.Action:
    cwd = Path(call.cwd or repo).resolve()
    args = commands.harness_args(call.command, cwd) if call.kind == "shell" else None
    selected_repo = commands.option(args, "--repo") if args else None
    command_repo = (cwd / selected_repo).resolve() if selected_repo else cwd
    chosen = settings.load(command_repo)
    command_root = None
    match chosen:
        case Ok(config) if config.knowledge_format == "markdown":
            path = (
                Path(config.knowledge_root)
                if config.knowledge_root
                else Path(config.artifacts_path) / "Project_Knowledge"
            )
            command_root = (command_repo / path).resolve()
        case _:
            pass
    name = str(payload.get("tool_name") or payload.get("toolName") or call.name)
    paths = tuple((cwd / path).resolve() for path in call.file_paths)
    return knowledge_first.classify(
        name,
        paths,
        root,
        args,
        expected_repo=repo.resolve(),
        command_repo=command_repo,
        command_store=command_root,
    )


def before(
    repo: Path, host: str, payload: dict[str, Any], call: rules.ToolCall
) -> rules.Decision | None:
    match _context(repo, host, payload):
        case (conversation, root):
            action = _classify(repo, root, call, payload)
            record = attempt(
                lambda: knowledge_first_store.read(repo, host, conversation),
                "knowledge_state_unavailable",
                "Could not read knowledge reminder state",
                Exception,
            )
            match record, action:
                case Err(), "external_read" | "knowledge_read":
                    return _state_notice()
                case Err(), _:
                    return None
                case Ok(None), "external_read" | "knowledge_read":
                    return _state_notice()
                case Ok(None), _:
                    return None
                case Ok(record), "knowledge_read":
                    observed = attempt(
                        lambda: knowledge_first_store.observe_read(
                            repo,
                            host,
                            conversation,
                            record.epoch,
                            hook_bridge.question_id(payload),
                        ),
                        "knowledge_state_unavailable",
                        "Could not record knowledge read",
                        Exception,
                    )
                    match observed:
                        case Err() | Ok(Err()):
                            return _state_notice()
                        case _:
                            return None
                case Ok(record), "external_read":
                    outcome = attempt(
                        lambda: knowledge_first_store.transition(
                            repo,
                            host,
                            conversation,
                            record.epoch,
                            freshness.verified_fresh(repo, root),
                            action,
                        ),
                        "knowledge_state_unavailable",
                        "Could not update knowledge reminder state",
                        Exception,
                    )
                    match outcome:
                        case Err():
                            return _state_notice()
                        case Ok(Err()):
                            return _state_notice()
                        case Ok(Ok(value)) if value is not None and not value.allowed:
                            return rules.Decision.deny("knowledge-first", value.message)
                        case Ok(Ok(value)) if value is not None and value.message:
                            return rules.Decision(
                                True, "knowledge-first", value.message
                            )
                        case _:
                            return None
                case _:
                    return None
        case _:
            return None


def after(repo: Path, host: str, payload: dict[str, Any]) -> None:
    match _context(repo, host, payload), hook_bridge.post_tool_response(host, payload):
        case (conversation, _), {"exit_code": int() as code} if (
            type(code) is int and code == 0
        ):
            knowledge_first_store.complete_read(
                repo, host, conversation, hook_bridge.question_id(payload), True
            )
        case (conversation, _), {"exit_code": int() as code} if type(code) is int:
            knowledge_first_store.complete_read(
                repo, host, conversation, hook_bridge.question_id(payload), False
            )
        case _:
            pass
