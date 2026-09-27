"""The shipped Azure DevOps tracker adapter, loaded the way the registry loads it.

Its planning operations, capacity mapping, and field names live in
`trackers/azure-devops/adapter.py`, the one place that knows Azure's replies; these tests exercise
them there.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType

import orchestrator_core  # noqa: F401 - puts the plugin's scripts/ on the import path
from integrations import registry
from integrations.contracts import AdapterContext
from integrations.transport import unavailable

azure = registry._import(
    "test_backlog_azure_tracker",
    registry.SHIPPED_ROOT / "azure-devops" / registry.ADAPTER,
)
MANIFEST = registry.read_manifest(
    registry.SHIPPED_ROOT / "azure-devops", "shipped"
).value


def tracker(process: str = "agile"):
    """The Azure adapter's `TrackerOps`, with no server behind it."""
    values = MappingProxyType({"organization": "o", "project": "p", "process": process})
    return azure.adapter(
        AdapterContext(MANIFEST, values, registry.PLUGIN_ROOT, unavailable("tests"))
    )


def select_azure(root: Path, process: str = "agile") -> None:
    """Write the repository's settings, selecting Azure DevOps with this process."""
    settings = {
        "schemaVersion": 1,
        "tracker": {
            "name": "azure-devops",
            "values": {"organization": "o", "project": "p", "process": process},
        },
        "scm": {"name": "github", "values": {"owner": "o", "repo": "r"}},
        "branch_template": "feature/{key}-{slug}",
    }
    (root / ".harness").mkdir(parents=True, exist_ok=True)
    (root / ".harness" / "settings.json").write_text(json.dumps(settings))
