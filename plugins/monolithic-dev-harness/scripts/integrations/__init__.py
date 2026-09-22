"""Provider-neutral tracker and SCM integration contracts."""

from .config import IntegrationConfig, load_config
from .contracts import (
    ArtifactRef,
    LogicalState,
    PullRequest,
    ReviewThread,
    WorkItem,
    WorkItemKind,
)

__all__ = [
    "ArtifactRef",
    "IntegrationConfig",
    "LogicalState",
    "PullRequest",
    "ReviewThread",
    "WorkItem",
    "WorkItemKind",
    "load_config",
]
