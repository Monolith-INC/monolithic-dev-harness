"""Provider adapters.

The seam between the generic estimation/capacity core and the systems that hold real
backlogs. Adding Jira or Linear means adding a module here and one registry entry --
nothing in `estimation/` or `capacity/` needs to change.

Follows the `HANDLERS` registry idiom already used for skill handlers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .azure_devops import AzureDevOpsProvider
from .base import ProviderResult, WorkItemWriter, WriteOp
from .filesystem import FilesystemProvider
from .linear import LinearProvider
from .work_items import AzureWorkItemAdapter, LinearWorkItemAdapter, ProviderCreateRequest

__all__ = [
    "AzureDevOpsProvider",
    "FilesystemProvider",
    "LinearProvider",
    "AzureWorkItemAdapter",
    "LinearWorkItemAdapter",
    "ProviderCreateRequest",
    "PROVIDERS",
    "ProviderResult",
    "WorkItemWriter",
    "WriteOp",
    "get_provider",
]

PROVIDERS = {
    AzureDevOpsProvider.name: AzureDevOpsProvider,
    FilesystemProvider.name: FilesystemProvider,
    LinearProvider.name: LinearProvider,
}

DEFAULT_PROVIDER = FilesystemProvider.name


def get_provider(
    name: str | None,
    *,
    artifacts_dir: Path | None = None,
    **kwargs: Any,
) -> Any | None:
    """Build a provider by name. Returns None for an unknown name rather than raising.

    `artifacts_dir` may be None: the filesystem provider then reports that no path has been
    configured, rather than defaulting to somewhere the user did not choose.
    """
    key = (name or DEFAULT_PROVIDER).strip().lower()
    provider_cls = PROVIDERS.get(key)
    if provider_cls is None:
        return None
    if provider_cls is FilesystemProvider:
        return FilesystemProvider(artifacts_dir)
    return provider_cls(**kwargs)
