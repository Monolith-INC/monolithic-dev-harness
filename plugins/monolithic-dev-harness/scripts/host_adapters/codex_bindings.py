"""Hook-only native child lineage; observations confer no additional permission.

The observed 0.162.1 wire uses the root session_id plus agent_id on child effects.
Only SubagentStart establishes lineage. No CLI/MCP operation exposes this writer.
Bindings live inside the existing human-owned host_sessions tree.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, err, fmap, require, sequence
from harness import project_paths, rules, shellscan, state, work_sessions
from host_adapters import work_session_context

ROOT = work_session_context.ROOT / "codex" / "children"


@dataclass(frozen=True)
class CodexChildBinding:
    parent_native_session: str
    child_native_session: str
    project: str
    work_session_id: str
    status: str = "active"
    version: int = 1


def _identity(payload: dict[str, Any], key: str) -> str:
    match payload.get(key):
        case str() as value:
            return value.strip()
        case _:
            return ""


def is_child(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("agent_id", "agent_type", "parent_thread_id"))


def _path(repo: Path, child: str) -> Path:
    return (
        repo.resolve() / ROOT / (hashlib.sha256(child.encode()).hexdigest() + ".json")
    )


def _load(repo: Path, child: str) -> Result[CodexChildBinding | None]:
    match _path(repo, child).exists():
        case False:
            return Ok(None)
        case _:
            return bind(
                attempt(
                    lambda: json.loads(_path(repo, child).read_text(encoding="utf-8")),
                    "codex_child_invalid",
                    "native child record",
                    OSError,
                    ValueError,
                ),
                _decode,
            )


def _decode(record: Any) -> Result[CodexChildBinding]:
    match record:
        case {
            "version": 1,
            "parent_native_session": str() as parent,
            "child_native_session": str() as child,
            "project": str() as project,
            "work_session_id": str() as scope,
            "status": "active" | "stopped" | "interrupted" | "conflicted" as status,
        } if all((parent, child, project, scope)):
            return Ok(CodexChildBinding(parent, child, project, scope, status))
        case _:
            return err("codex_child_invalid", "native child binding is invalid")


def _save(repo: Path, record: CodexChildBinding) -> Result[CodexChildBinding]:
    return fmap(
        attempt(
            lambda: state.write_json(
                _path(repo, record.child_native_session), asdict(record)
            ),
            "codex_child_unwritable",
            "native child binding",
            OSError,
        ),
        lambda _: record,
    )


def _parent_scope(repo: Path, payload: dict[str, Any]) -> Result[str]:
    return bind(
        require(
            bool(_identity(payload, "session_id"))
            and bool(_identity(payload, "cwd"))
            and project_paths.root(Path(_identity(payload, "cwd"))) == repo.resolve(),
            "codex_child_lineage",
            "native child parent/project identity is missing or contradictory",
        ),
        lambda _: bind(
            work_session_context.resolve_session(
                repo, "codex", _identity(payload, "session_id")
            ),
            lambda scope: _active_scope(repo, scope),
        ),
    )


def _active_scope(repo: Path, scope: str | None) -> Result[str]:
    match scope:
        case str() if scope:
            return bind(
                work_sessions.select(repo, scope),
                lambda session: fmap(
                    require(
                        session.status == work_sessions.Status.ACTIVE,
                        "codex_child_inactive",
                        "the child's parent work session is not active",
                    ),
                    lambda _: scope,
                ),
            )
        case _:
            return err(
                "codex_child_lineage",
                "the native parent has no bound work session; the root must choose one before delegation",
            )


def observe_lifecycle(repo: Path, payload: dict[str, Any]) -> Result[CodexChildBinding]:
    """Called exclusively by native hook dispatch, never from a model-facing receipt."""
    match payload.get("hook_event_name"):
        case "SubagentStop":
            return bind(
                _load(repo, _identity(payload, "agent_id")),
                lambda record: _stop(repo, payload, record),
            )
        case _:
            pass
    return bind(
        require(
            bool(_identity(payload, "agent_id")),
            "codex_child_lineage",
            "native child identity is missing",
        ),
        lambda _: bind(
            _parent_scope(repo, payload),
            lambda scope: bind(
                _load(repo, _identity(payload, "agent_id")),
                lambda previous: _observe(repo, payload, scope, previous),
            ),
        ),
    )


def _stop(
    repo: Path, payload: dict[str, Any], record: CodexChildBinding | None
) -> Result[CodexChildBinding]:
    match record:
        case CodexChildBinding() if (
            record.parent_native_session == _identity(payload, "session_id")
            and record.child_native_session == _identity(payload, "agent_id")
            and record.project == str(repo.resolve())
            and bool(_identity(payload, "cwd"))
            and project_paths.root(Path(_identity(payload, "cwd"))) == repo.resolve()
        ):
            return _save(repo, replace(record, status="stopped"))
        case _:
            return err(
                "codex_child_lineage", "native stop has no matching child lineage"
            )


def _observe(
    repo: Path, payload: dict[str, Any], scope: str, previous: CodexChildBinding | None
) -> Result[CodexChildBinding]:
    expected = CodexChildBinding(
        _identity(payload, "session_id"),
        _identity(payload, "agent_id"),
        str(repo.resolve()),
        scope,
    )
    match payload.get("hook_event_name"), previous:
        case "SubagentStart", None:
            return _save(repo, expected)
        case "SubagentStart", CodexChildBinding(status="active") if (
            previous == expected
        ):
            return Ok(previous)
        case _, CodexChildBinding():
            return bind(
                _save(repo, replace(previous, status="conflicted")),
                lambda _: err(
                    "codex_child_lineage",
                    "native child lifecycle conflicts with its saved lineage; effects are blocked",
                ),
            )
        case _:
            return err(
                "codex_child_lineage",
                "native child lifecycle is missing, conflicting, or already ended",
            )


def resolve_child_scope(repo: Path, payload: dict[str, Any]) -> Result[str]:
    return bind(
        _parent_scope(repo, payload),
        lambda scope: bind(
            _load(repo, _identity(payload, "agent_id")),
            lambda record: fmap(
                require(
                    record
                    == CodexChildBinding(
                        _identity(payload, "session_id"),
                        _identity(payload, "agent_id"),
                        str(repo.resolve()),
                        scope,
                    ),
                    "codex_child_lineage",
                    "native child binding is missing, conflicting, stopped, or interrupted",
                ),
                lambda _: scope,
            ),
        ),
    )


def interrupt(
    repo: Path, payload: dict[str, Any]
) -> Result[tuple[CodexChildBinding, ...]]:
    """Revoke observed children on Interrupt; this does not claim successful cancellation."""
    return bind(
        require(
            bool(_identity(payload, "session_id")),
            "codex_child_lineage",
            "interrupt has no native parent",
        ),
        lambda _: bind(
            attempt(
                lambda: tuple((repo / ROOT).glob("*.json")),
                "codex_child_invalid",
                "native child records",
                OSError,
            ),
            lambda paths: fmap(
                sequence(tuple(_interrupt_path(repo, payload, path) for path in paths)),
                lambda records: tuple(
                    record for record in records if record is not None
                ),
            ),
        ),
    )


def _interrupt_path(
    repo: Path, payload: dict[str, Any], source: Path
) -> Result[CodexChildBinding | None]:
    match _load_path(repo, source):
        case Ok(record) if record.parent_native_session == _identity(
            payload, "session_id"
        ) and (
            not is_child(payload)
            or record.child_native_session == _identity(payload, "agent_id")
        ):
            return _save(repo, replace(record, status="interrupted"))
        case Err() as failed:
            return failed
        case _:
            return Ok(None)


def _load_path(repo: Path, source: Path) -> Result[CodexChildBinding]:
    return bind(
        attempt(
            lambda: json.loads(source.read_text(encoding="utf-8")),
            "codex_child_invalid",
            "native child record",
            OSError,
            ValueError,
        ),
        _decode,
    )


def _harness_control(command: str) -> bool:
    return any(
        invocation.name == "harness"
        or any(
            argument.endswith("/scripts/harness/cli.py")
            or argument in {"harness.cli", "harness"}
            for argument in invocation.args
        )
        for invocation in shellscan.invocations(command)
    ) or bool(re.search(r"\bharness\.cli\b|\bscripts/harness/cli\.py\b", command))


def guard(
    repo: Path, payload: dict[str, Any], call: rules.ToolCall
) -> rules.Decision | None:
    match is_child(payload):
        case True:
            match resolve_child_scope(repo, payload):
                case Err(failure) if rules.is_write_class(call):
                    return rules.Decision.deny("codex-child-lineage", failure.message)
                case _:
                    pass
            match call.kind, call.command:
                case "shell", command if _harness_control(command):
                    return rules.Decision.deny(
                        "codex-child-authority",
                        "children return harness control and decision needs to their root; they cannot bind, switch, or advance work sessions",
                    )
                case _ if call.name.startswith("collaboration"):
                    return rules.Decision.deny(
                        "codex-child-authority",
                        "native child delegation/control requires the governing root",
                    )
                case _:
                    return None
        case _:
            return None
