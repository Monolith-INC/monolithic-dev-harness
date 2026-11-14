"""Sprint reads through the host gateway: a client (the backlog runtime) never starts a provider.

The client's sprint operations are forwarded reads; what comes back is rebuilt into the same
values the adapter returns, so planning cannot tell the difference."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from core.result import fmap
from harness import settings as repo_settings
from integrations import gateway, gateway_client, registry
from integrations.contracts import WorkItemChanges, WorkItemKind
from tests.settings_fixture import write_settings

from .fakes import FakeTransport, ops
from .trackers import AzureBoard

AZURE = {"organization": "o", "project": "proj"}


def _project(tmp_path: Path) -> FakeTransport:
    """An Azure DevOps project whose server is a fake, holding a story in the current sprint."""
    write_settings(tmp_path, tracker={"name": "azure-devops", "values": AZURE})
    server = FakeTransport(AzureBoard().answers)
    azure = ops("azure-devops", AZURE, server)
    story = azure.create_work_item(WorkItemKind.USER_STORY, "S", "s", "").value
    sprint = azure.current_sprint().value
    azure.update_work_item(
        story.key, WorkItemChanges(iteration=sprint.path, story_points=3)
    )
    return server


def _forwarded(repo: Path, operation: str, arguments: dict):
    """The gateway's answer, as the bus carries it: JSON."""
    return fmap(
        gateway.handle_call(operation, arguments, repo),
        lambda value: json.loads(json.dumps(value)),
    )


def test_sprint_reads_through_the_gateway_match_the_adapter(tmp_path: Path) -> None:
    server = _project(tmp_path)
    direct = ops("azure-devops", AZURE, server)
    active = registry.selected(tmp_path, repo_settings.load(tmp_path)).value
    # The gateway owns the provider (here the fake); the client only forwards reads to it.
    with (
        mock.patch.object(gateway_client, "call", _forwarded),
        mock.patch.object(registry, "_transport", lambda active, repo: server),
    ):
        client = gateway_client.open_selected(active, tmp_path).value
        assert client.current_sprint().value == direct.current_sprint().value
        assert (
            client.sprint_capacity("current").value
            == direct.sprint_capacity("current").value
        )
        assert (
            client.sprint_items("current").value == direct.sprint_items("current").value
        )


def test_the_sprint_reads_are_forwarded_reads() -> None:
    from harness.process_messages import INTEGRATION_READS

    assert {
        "tracker_current_sprint",
        "tracker_sprint_items",
        "tracker_sprint_capacity",
    } <= INTEGRATION_READS
