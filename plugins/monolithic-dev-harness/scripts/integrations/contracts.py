"""The one contract every tracker and SCM adapter meets.

A tracker is two things in its folder (`trackers/<name>/`): `tracker.json`, checked against
`config/tracker.schema.json`, says what the tracker is; `adapter.py` exports
`adapter(context: AdapterContext) -> TrackerOps`, which says how to talk to it. `TrackerOps` is a
record of functions, so an adapter that leaves one out cannot be built. Every function returns an
`Ok`/`Err` value; none raises for an expected condition.

Every tracker plans too: it reads a sprint and its items into the model in `planning.py` and names
the fields that record hours. The replies it reads are the ones its manifest lists under
`planning.replies`, fetched by a skill through the host's tools and handed over as a mapping.

Values are plain and immutable. Text that is absent is `""`, never `None`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from core.result import Ok, Result, err

from .planning import EstimableItem, HourFields, IterationReading

EMPTY: Mapping[str, Any] = MappingProxyType({})


class WorkItemKind(str, Enum):
    """The harness's work vocabulary; each tracker maps it to its own types in `kinds`."""

    EPIC = "epic"
    FEATURE = "feature"
    USER_STORY = "user_story"
    TASK = "task"
    BUG = "bug"


# What a work session implements, and what an implementation plan is approved for.
BUILDABLE_KINDS = frozenset({WorkItemKind.USER_STORY, WorkItemKind.BUG})
# What work may start from (the item a work session tracks).
ENTRY_KINDS = frozenset(
    {WorkItemKind.EPIC, WorkItemKind.FEATURE, WorkItemKind.USER_STORY, WorkItemKind.BUG}
)


class LogicalState(str, Enum):
    """The harness's states; each tracker maps them to its own in `states`."""

    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"


@dataclass(frozen=True)
class WorkItem:
    id: str
    key: str
    title: str
    kind: WorkItemKind
    state: LogicalState
    url: str = ""
    description: str = ""
    parent_id: str = ""
    provider_data: Mapping[str, Any] = field(
        default_factory=lambda: EMPTY, compare=False
    )

    def is_child_of(self, parent: WorkItem) -> bool:
        """Whether this item names `parent` as its parent, by id or key."""
        return bool(self.parent_id) and self.parent_id.casefold() in {
            parent.id.casefold(),
            parent.key.casefold(),
        }


@dataclass(frozen=True)
class Page:
    items: tuple[WorkItem, ...]
    next_cursor: str = ""
    truncated: bool = False


@dataclass(frozen=True)
class ArtifactDraft:
    """A workflow artifact to attach to a work item. One (title, revision) is published once."""

    kind: str
    title: str
    content: str
    revision: str


@dataclass(frozen=True)
class ArtifactRef:
    id: str
    kind: str
    title: str
    revision: str
    url: str = ""
    content: str = ""
    provider_data: Mapping[str, Any] = field(
        default_factory=lambda: EMPTY, compare=False
    )


@dataclass(frozen=True)
class PullRequestDraft:
    title: str
    description: str
    source_branch: str
    target_branch: str
    draft: bool = True


@dataclass(frozen=True)
class PullRequest:
    id: str
    number: str
    title: str
    url: str
    source_branch: str
    target_branch: str
    state: str
    provider_data: Mapping[str, Any] = field(
        default_factory=lambda: EMPTY, compare=False
    )


@dataclass(frozen=True)
class ReviewThread:
    id: str
    file: str
    line: int
    reviewer: str
    comment: str
    status: str
    provider_data: Mapping[str, Any] = field(
        default_factory=lambda: EMPTY, compare=False
    )


# A call to the provider: tool name and arguments in, the decoded reply (or why not) out.
Transport = Callable[[str, Mapping[str, Any]], Result[Any]]


@dataclass(frozen=True)
class IdRules:
    """How the tracker writes its ids, finds them in branch names, and links them from text."""

    pattern: str
    branch_key: str
    mention: tuple[str, ...]
    mentions_link: bool


@dataclass(frozen=True)
class WriteRules:
    """The provider tools, as the host exposes them, that change the tracker."""

    server: str
    tools: tuple[str, ...]


@dataclass(frozen=True)
class Artifact:
    name: str
    children: tuple[str, ...]
    estimate: str = ""


@dataclass(frozen=True)
class PlanningReply:
    """A provider reply the tracker's planning operations read, and what to fetch for it."""

    key: str
    description: str


@dataclass(frozen=True)
class Manifest:
    """A checked `tracker.json`. `document` keeps the file as read, for `tracker_describe`."""

    name: str
    label: str
    root: Path
    source: str
    kinds: Mapping[WorkItemKind, str]
    states: Mapping[LogicalState, str]
    artifacts: tuple[Artifact, ...]
    ids: IdRules
    writes: WriteRules
    tools: Mapping[str, str]
    connection: Mapping[str, Any]
    settings: tuple[str, ...]
    required_settings: tuple[str, ...]
    text_format: str
    planning: tuple[PlanningReply, ...]
    document: Mapping[str, Any] = field(compare=False)


@dataclass(frozen=True)
class AdapterContext:
    manifest: Manifest
    values: Mapping[str, str]
    repo: Path
    call: Transport


@dataclass(frozen=True)
class Hours:
    """A Task's effort; `first_estimate` also records it as the original estimate where the
    tracker keeps one."""

    value: float
    first_estimate: bool = False


@dataclass(frozen=True)
class WorkItemChanges:
    """The fields of an existing work item to change; `None` leaves a field as it is.

    `description` carries the whole refined body, acceptance criteria included.
    """

    title: str | None = None
    description: str | None = None
    story_points: float | None = None
    hours: Hours | None = None
    assignee: str | None = None
    iteration: str | None = None


@dataclass(frozen=True)
class FieldNames:
    """A tracker's own name for each field `WorkItemChanges` can set."""

    title: str
    description: str
    story_points: str
    assignee: str
    iteration: str


def changed_fields(
    changes: WorkItemChanges, names: FieldNames, hours: HourFields
) -> Result[dict[str, Any]]:
    """The tracker fields to write for `changes`: only the named ones, hours in the tracker's own
    hour fields. Refused when nothing changes, or when hours change on a tracker that keeps none."""
    named = {
        names.title: changes.title,
        names.description: changes.description,
        names.story_points: changes.story_points,
        names.assignee: changes.assignee,
        names.iteration: changes.iteration,
    }
    fields: dict[str, Any] = {
        name: value for name, value in named.items() if value is not None
    }
    match changes.hours:
        case Hours(value, first) if not hours(value, first):
            return err("unsupported", "this tracker records no hours on a work item")
        case Hours(value, first):
            fields.update(hours(value, first))
        case None:
            pass
    return (
        Ok(fields)
        if fields
        else err("invalid_request", "name at least one field to change")
    )


@dataclass(frozen=True)
class TrackerOps:
    get_work_item: Callable[[str], Result[WorkItem]]
    search_work_items: Callable[[str, str], Result[Page]]
    create_work_item: Callable[[WorkItemKind, str, str, str], Result[WorkItem]]
    # Changes the named fields of an existing item and returns it as the tracker now holds it.
    update_work_item: Callable[[str, WorkItemChanges], Result[WorkItem]]
    transition_work_item: Callable[[str, LogicalState], Result[WorkItem]]
    list_children: Callable[[str], Result[tuple[WorkItem, ...]]]
    list_artifacts: Callable[[str], Result[tuple[ArtifactRef, ...]]]
    add_artifact: Callable[[str, ArtifactDraft], Result[ArtifactRef]]
    link_development_artifact: Callable[[str, str, str], Result[Mapping[str, Any]]]
    # Planning: (replies, sprint reference) in. The reference "current", or none, means the active
    # sprint (`planning.CURRENT`); a tracker that cannot tell which that is refuses it. A reply
    # that was given but holds no data is refused, never read as an empty sprint.
    # `records_hours`: whether a Task's hours can be written (`update_work_item`) at all.
    read_iteration: Callable[[Mapping[str, Any], str], Result[IterationReading]]
    iteration_items: Callable[
        [Mapping[str, Any], str], Result[tuple[EstimableItem, ...]]
    ]
    records_hours: bool


def _unsupported(operation: str) -> Callable[..., Result[Mapping[str, Any]]]:
    """An operation a code host leaves out: every call is refused, naming what is missing."""
    return lambda *_: err(
        "unsupported_capability", f"{operation} is not supported by this code host"
    )


@dataclass(frozen=True)
class ScmOps:
    get_pull_request: Callable[[str], Result[PullRequest]]
    create_pull_request: Callable[[PullRequestDraft], Result[PullRequest]]
    list_review_threads: Callable[[str], Result[tuple[ReviewThread, ...]]]
    reply_to_thread: Callable[[str, str, str], Result[Mapping[str, Any]]]
    link_work_item: Callable[[str, str], Result[Mapping[str, Any]]]
    create_review_thread: Callable[
        [str, str, int, int, int, str], Result[Mapping[str, Any]]
    ] = _unsupported("inline review threads")
    update_thread_comment: Callable[[str, str, str], Result[Mapping[str, Any]]] = (
        _unsupported("editing review comments")
    )
    set_thread_status: Callable[[str, str, str], Result[Mapping[str, Any]]] = (
        _unsupported("changing a review thread's status")
    )
