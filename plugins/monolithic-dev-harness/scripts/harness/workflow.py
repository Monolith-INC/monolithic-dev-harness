"""Durable, clone-local workflow checkpoints and pure navigation transitions.

The record describes progress; it never grants permission to write to a tracker or SCM.
"""

from __future__ import annotations

import hashlib
import secrets
import subprocess
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from core.result import Err, Ok, Result, attempt, bind, err, fmap, require
from harness import state

VERSION = 1
STAGES = ("setup", "discover", "ideate", "backlog", "technical-plan", "build", "verify")
STATUSES = ("active", "paused", "cancelled", "completed")
TERMINAL_STATUSES = frozenset({"cancelled", "completed"})
RELATIVE_PATH = Path(".harness/state/workflow.json")


@dataclass(frozen=True)
class Point:
    id: int
    label: str
    stage: str
    artifacts: tuple[tuple[str, str], ...] = ()
    decisions: tuple[tuple[str, str], ...] = ()
    pending: str = ""
    next_action: str = ""
    completed_writes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Workflow:
    version: int
    status: str
    request: str
    language: str
    points: tuple[Point, ...]
    cursor: int

    @property
    def current(self) -> Point:
        return self.points[self.cursor]


def path(repo: Path, session_id: str | None = None) -> Path:
    match session_id:
        case None:
            return repo / RELATIVE_PATH
        case identifier:
            from harness import work_sessions

            return work_sessions.root(repo) / state.safe_name(identifier) / "workflow.json"


def archive_terminal(repo: Path, session_id: str | None = None) -> Result[Path]:
    """Retain a finished run before a new run replaces the current pointer."""
    return bind(
        load(repo, session_id),
        lambda current: bind(
            require(
                current.status in TERMINAL_STATUSES,
                "workflow_active",
                "only a completed or cancelled workflow can be archived",
            ),
            lambda _: _archive_if_active(repo, current, session_id),
        ),
    )


def _archive_if_active(
    repo: Path, current: Workflow, session_id: str | None
) -> Result[Path]:
    from harness import work_sessions

    return bind(
        Ok(None)
        if session_id is None
        else fmap(work_sessions.require_active(repo, session_id), lambda _: None),
        lambda _: attempt(
            lambda: _archive(repo, current, session_id),
            "workflow_unwritable",
            str(path(repo, session_id)),
            OSError,
        ),
    )


def _archive(repo: Path, current: Workflow, session_id: str | None = None) -> Path:
    source = path(repo, session_id)
    destination = source.parent / "workflows" / f"{secrets.token_hex(8)}.json"
    state.write_json(destination, asdict(current))
    source.unlink()
    return destination


def start(request: str, language: str = "") -> Result[Workflow]:
    match request.strip(), language:
        case "", _:
            return err("invalid_workflow", "the original request is required")
        case _, "" | "en" | "pt-br":
            return Ok(
                Workflow(
                    VERSION,
                    "active",
                    request.strip(),
                    language,
                    (Point(1, "First request", "setup", next_action="Check setup"),),
                    0,
                )
            )
        case _:
            return err("invalid_workflow", "language must be en or pt-br")


def add_point(
    workflow: Workflow,
    label: str,
    stage: str,
    artifacts: tuple[tuple[str, str], ...] = (),
    decisions: tuple[tuple[str, str], ...] = (),
    pending: str = "",
    next_action: str = "",
    completed_writes: tuple[str, ...] = (),
) -> Result[Workflow]:
    match workflow.status, label.strip(), stage:
        case "active", str() as name, str() as selected if name and selected in STAGES:
            kept = workflow.points[: workflow.cursor + 1]
            point = Point(
                max(item.id for item in workflow.points) + 1,
                name,
                selected,
                artifacts,
                decisions,
                pending,
                next_action,
                tuple(
                    dict.fromkeys(
                        (
                            *(
                                write
                                for point in workflow.points
                                for write in point.completed_writes
                            ),
                            *completed_writes,
                        )
                    )
                ),
            )
            return Ok(replace(workflow, points=(*kept, point), cursor=len(kept)))
        case "active", _, _:
            return err("invalid_workflow", "a label and known stage are required")
        case _:
            return err("invalid_workflow", "resume the workflow before saving a point")


def navigate(workflow: Workflow, point_id: int | None = None) -> Result[Workflow]:
    target = next(
        (index for index, point in enumerate(workflow.points) if point.id == point_id),
        workflow.cursor - 1 if point_id is None else -1,
    )
    match workflow.status, target:
        case status, _ if status in TERMINAL_STATUSES:
            return err("invalid_workflow", "a finished workflow cannot go back")
        case _, int() as index if 0 <= index < workflow.cursor:
            return Ok(replace(workflow, status="active", cursor=index))
        case _:
            return err("invalid_workflow", "choose an earlier saved review point")


def pause(workflow: Workflow) -> Result[Workflow]:
    match workflow.status:
        case "active":
            return Ok(replace(workflow, status="paused"))
        case _:
            return err("invalid_workflow", "only an active workflow can be paused")


def resume(workflow: Workflow, point_id: int | None = None) -> Result[Workflow]:
    target = next(
        (index for index, point in enumerate(workflow.points) if point.id == point_id),
        workflow.cursor if point_id is None else -1,
    )
    match workflow.status, target:
        case status, _ if status in TERMINAL_STATUSES:
            return err("invalid_workflow", "a finished workflow cannot resume")
        case _, int() as index if 0 <= index < len(workflow.points):
            return Ok(replace(workflow, status="active", cursor=index))
        case _:
            return err("invalid_workflow", "choose a saved review point")


def cancel(workflow: Workflow) -> Result[Workflow]:
    match workflow.status:
        case status if status in TERMINAL_STATUSES:
            return err("invalid_workflow", "the workflow is already finished")
        case _:
            return Ok(replace(workflow, status="cancelled"))


def complete(workflow: Workflow) -> Result[Workflow]:
    match workflow.status:
        case "active":
            return Ok(replace(workflow, status="completed"))
        case _:
            return err("invalid_workflow", "only an active workflow can be completed")


def from_dict(raw: Any) -> Result[Workflow]:
    match raw:
        case {
            "version": 1,
            "status": str() as status,
            "request": str() as request,
            "language": str() as language,
            "points": list() as points,
            "cursor": int() as cursor,
        } if (
            status in STATUSES
            and language in ("", "en", "pt-br")
            and request.strip()
            and points
            and 0 <= cursor < len(points)
        ):
            return bind(
                _points(points),
                lambda parsed: Ok(
                    Workflow(VERSION, status, request, language, parsed, cursor)
                ),
            )
        case _:
            return err(
                "invalid_workflow", "saved workflow has an invalid format or version"
            )


def _points(raw: list[Any]) -> Result[tuple[Point, ...]]:
    parsed = tuple(_point(item) for item in raw)
    match tuple(item for item in parsed if isinstance(item, Err)):
        case (Err() as failure, *_):
            return failure
        case ():
            return Ok(tuple(item.value for item in parsed if isinstance(item, Ok)))


def _point(raw: Any) -> Result[Point]:
    match raw:
        case {
            "id": int() as point_id,
            "label": str() as label,
            "stage": str() as stage,
            "artifacts": list() as artifacts,
            "decisions": list() as decisions,
            "pending": str() as pending,
            "next_action": str() as next_action,
            "completed_writes": list() as writes,
        } if (
            point_id > 0
            and label.strip()
            and stage in STAGES
            and all(
                isinstance(pair, list)
                and len(pair) == 2
                and all(isinstance(part, str) for part in pair)
                for pair in (*artifacts, *decisions)
            )
            and all(isinstance(item, str) for item in writes)
        ):
            return Ok(
                Point(
                    point_id,
                    label,
                    stage,
                    tuple(tuple(pair) for pair in artifacts),
                    tuple(tuple(pair) for pair in decisions),
                    pending,
                    next_action,
                    tuple(writes),
                )
            )
        case _:
            return err("invalid_workflow", "saved review point is invalid")


def load(repo: Path, session_id: str | None = None) -> Result[Workflow]:
    if session_id is not None:
        from harness import work_sessions

        return bind(
            work_sessions.select(repo, session_id),
            lambda selected: _load_file(selected.folder / "workflow.json"),
        )
    return _load_file(path(repo))


def _load_file(file: Path) -> Result[Workflow]:
    match file.is_file():
        case False:
            return err("workflow_absent", "no workflow has been saved")
        case True:
            return from_dict(state.read_json(file))


def save(
    repo: Path, workflow: Workflow, session_id: str | None = None
) -> Result[Path]:
    if session_id is not None:
        from harness import work_sessions

        return bind(
            work_sessions.require_active(repo, session_id),
            lambda selected: _save_scoped(repo, workflow, selected.folder / "workflow.json"),
        )
    return _save_scoped(repo, workflow, path(repo))


def _save_scoped(repo: Path, workflow: Workflow, destination: Path) -> Result[Path]:
    return bind(
        attempt(
            lambda: state.ensure_local_exclude(repo),
            "workflow_unwritable",
            str(repo),
            OSError,
            subprocess.TimeoutExpired,
        ),
        lambda _: attempt(
            lambda: _save(destination, workflow),
            "workflow_unwritable",
            str(destination),
            OSError,
        ),
    )


def _save(destination: Path, workflow: Workflow) -> Path:
    state.write_json(destination, asdict(workflow))
    return destination


def file_digest(file: Path) -> Result[str]:
    return fmap(
        attempt(lambda: file.read_bytes(), "artifact_unreadable", str(file), OSError),
        lambda content: hashlib.sha256(content).hexdigest(),
    )


def stale_artifacts(repo: Path, point: Point) -> tuple[str, ...]:
    return tuple(
        name
        for name, expected in point.artifacts
        if file_digest(repo / name) != Ok(expected)
    )
