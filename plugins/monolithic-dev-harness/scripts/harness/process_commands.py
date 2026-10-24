"""The shared command vocabulary; adapters interpret no private command variants."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.result import Ok, Result, attempt, bind, err, fmap
from harness import commands, rules
from harness.process_assignment import Assignment, decode_assignment
from harness.process_messages import ProcessStatus


@dataclass(frozen=True)
class ControlRequest:
    operation: str
    process_id: str
    status: ProcessStatus | None = None
    session_id: str = ""
    adapter: str = ""
    assignment: Assignment | None = None


def _options(
    values: tuple[str, ...], seen: tuple[tuple[str, str], ...] = ()
) -> Result[tuple[tuple[str, str], ...]]:
    match values:
        case ():
            return Ok(seen)
        case (str() as flag, *tail) if "=" in flag:
            return _options((*flag.split("=", 1), *tail), seen)
        case (flag, value, *tail) if (
            flag in ("--repo", "--session-id", "--host", "--status", "--assignment")
            and value
            and not value.startswith("--")
            and flag not in dict(seen)
        ):
            return _options(tuple(tail), (*seen, (flag, value)))
        case _:
            return err(
                "invalid_process_command",
                "use one plain process command with unique --repo, --host and --session-id options",
            )


def control(call: rules.ToolCall, repo: Path) -> Result[ControlRequest | None]:
    match call.kind, commands.harness_args(call.command, Path(call.cwd or repo)):
        case "shell", (
            "process",
            "cancel" | "report" | "assign" as operation,
            process_id,
            *options,
        ) if process_id and not process_id.startswith("--"):
            return bind(
                _options(tuple(options)),
                lambda values: _cancel_scope(
                    operation, process_id, dict(values), Path(call.cwd or repo), repo
                ),
            )
        case "shell", ("process", "cancel" | "report" | "assign", *_):
            return err(
                "invalid_process_command",
                "process cancellation requires a process identifier",
            )
        case _:
            return Ok(None)


def _cancel_scope(
    operation: str, process_id: str, options: dict[str, str], cwd: Path, repo: Path
) -> Result[ControlRequest]:
    match operation, (cwd / options.get("--repo", ".")).resolve() == repo.resolve():
        case "assign", True if "--status" not in options:
            return fmap(
                bind(
                    attempt(
                        lambda: json.loads(options.get("--assignment", "")),
                        "invalid_assignment",
                        "assignment must be valid JSON",
                        ValueError,
                    ),
                    decode_assignment,
                ),
                lambda assignment: ControlRequest(
                    operation,
                    process_id,
                    None,
                    options.get("--session-id", ""),
                    options.get("--host", ""),
                    assignment,
                ),
            )
        case _, True if "--assignment" not in options and (
            (operation == "cancel" and "--status" not in options)
            or (
                operation == "report"
                and options.get("--status")
                in tuple(value.value for value in ProcessStatus)
            )
        ):
            return Ok(
                ControlRequest(
                    operation,
                    process_id,
                    ProcessStatus(options["--status"])
                    if operation == "report"
                    else None,
                    options.get("--session-id", ""),
                    options.get("--host", ""),
                )
            )
        case _:
            return err(
                "process_scope_mismatch",
                "process cancellation must run in the owning project",
            )


def recovery_command(call: rules.ToolCall, repo: Path) -> bool:
    match call.kind, commands.harness_args(call.command, Path(call.cwd or repo)):
        case "shell", ("process", "list", *options):
            return (
                isinstance(_options(tuple(options)), Ok)
                and (
                    Path(call.cwd or repo)
                    / (commands.option(tuple(options), "--repo") or ".")
                ).resolve()
                == repo.resolve()
            )
        case "shell", ("process", "status", identifier, *options) if identifier:
            return (
                isinstance(_options(tuple(options)), Ok)
                and (
                    Path(call.cwd or repo)
                    / (commands.option(tuple(options), "--repo") or ".")
                ).resolve()
                == repo.resolve()
            )
        case _:
            match control(call, repo):
                case Ok(ControlRequest(operation="cancel" | "report")):
                    return True
                case _:
                    return False
