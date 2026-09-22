from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskState(Enum):
    READY = "Ready"
    IN_PROGRESS = "In_Progress"
    COMPLETED = "Completed"
    BLOCKED = "Blocked"
    BLOCKED_REQUIRES_REVIEW = "Blocked_Requires_Review"


@dataclass(frozen=True)
class Event:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Task:
    id: str
    skill_name: str
    state: TaskState = TaskState.READY
    inputs: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    critiques: List[str] = field(default_factory=list)
    output: Optional[Any] = None

    def copy_with(self, **kwargs: Any) -> Task:
        return dataclasses.replace(self, **kwargs)


@dataclass(frozen=True)
class QueueState:
    tasks: Dict[str, Task] = field(default_factory=dict)
    events_history: List[Event] = field(default_factory=list)

    def copy_with(self, **kwargs: Any) -> QueueState:
        return dataclasses.replace(self, **kwargs)
