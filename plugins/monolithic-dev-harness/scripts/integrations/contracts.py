from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkItemKind(str, Enum):
    EPIC = "epic"
    FEATURE = "feature"
    USER_STORY = "user_story"
    TASK = "task"
    BUG = "bug"


class LogicalState(str, Enum):
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"


@dataclass(frozen=True)
class WorkItemRole:
    """A workflow role and the kinds it may directly contain."""

    kind: WorkItemKind
    child_kinds: frozenset[WorkItemKind]


EPIC = WorkItemRole(WorkItemKind.EPIC, frozenset({WorkItemKind.FEATURE}))
FEATURE = WorkItemRole(
    WorkItemKind.FEATURE,
    frozenset({WorkItemKind.USER_STORY, WorkItemKind.BUG}),
)
USER_STORY = WorkItemRole(WorkItemKind.USER_STORY, frozenset({WorkItemKind.TASK}))
TASK = WorkItemRole(WorkItemKind.TASK, frozenset())
BUG = WorkItemRole(WorkItemKind.BUG, frozenset({WorkItemKind.TASK}))
WORK_ITEM_ROLES = {role.kind: role for role in (EPIC, FEATURE, USER_STORY, TASK, BUG)}


@dataclass(frozen=True)
class WorkItem:
    id: str
    key: str
    title: str
    kind: WorkItemKind
    state: LogicalState
    url: str | None = None
    description: str = ""
    parent_id: str | None = None
    provider_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactRef:
    id: str
    kind: str
    title: str
    revision: str
    url: str | None = None
    provider_data: dict[str, Any] = field(default_factory=dict)
    outcome: str | None = None
    attempts: int | None = None


@dataclass(frozen=True)
class PullRequest:
    id: str
    number: str
    title: str
    url: str
    source_branch: str
    target_branch: str
    state: str
    provider_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewThread:
    id: str
    file: str | None
    line: int | None
    reviewer: str
    comment: str
    status: str
    provider_data: dict[str, Any] = field(default_factory=dict)


class IntegrationError(RuntimeError):
    """A normalized error safe to expose to workflows and hooks."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "retryable": self.retryable}
