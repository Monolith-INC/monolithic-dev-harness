"""Conflicting native providers are diagnosed by command, not display label."""

import json

from harness import installation_inventory as inventory
from harness import preferences, state
from host_adapters.installation_contract import Inventory
from tests.settings_fixture import write_settings


def test_preflight_uses_owner_gateway_without_starting_a_provider(
    tmp_path, monkeypatch, capsys
):
    from core.result import Ok
    from harness import cli
    from integrations import gateway_client

    write_settings(
        tmp_path,
        tracker={
            "name": "azure-devops",
            "values": {"organization": "o", "project": "p"},
        },
    )
    calls = []
    monkeypatch.setattr(
        gateway_client,
        "call",
        lambda repo, operation, args: (calls.append(operation), Ok({"ready": True}))[1],
    )
    assert cli._tracker_preflight(tmp_path) == 0
    assert calls == ["tracker_preflight"]


def test_direct_provider_is_reported_without_claiming_ownership(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "workflow-integrations": {
                        "command": "/plugins/monolithic-dev-harness/bin/harness-python"
                    },
                    "Azure DevOps": {
                        "command": "npx",
                        "args": ["-y", "@azure-devops/mcp@latest", "org"],
                    },
                    "personal": {"command": "other"},
                }
            }
        )
    )
    components = inventory._settings("codex", config, "local", "mcp")
    assert any(
        finding.code == "private-provider-registration"
        for finding in inventory.findings(Inventory(components))
    )
    assert not next(
        item for item in components if item.kind == "provider-conflict"
    ).owned


def test_language_request_changes_future_controls_not_project_artifact_language(
    tmp_path, monkeypatch
):
    write_settings(tmp_path)
    state.write_json(tmp_path / preferences.LANGUAGE_STATE, {"language": "pt-br"})
    monkeypatch.setenv("CODEX_THREAD_ID", "conversation")
    preferences.observe_language(tmp_path, "conversation", "english please")
    assert preferences.language_for(tmp_path).value == "en"
    assert state.read_json(tmp_path / preferences.LANGUAGE_STATE)["language"] == "pt-br"


def test_selected_conflict_repair_preserves_other_servers_and_original_backup(
    tmp_path, monkeypatch
):
    from core.result import Ok
    from harness.installation_files import apply_repairs
    from host_adapters.installation_contract import (
        InstallationAdapter,
        InstallationContext,
        Location,
    )

    project = tmp_path / "project"
    project.mkdir()
    config = project / "config.json"
    original = {
        "mcpServers": {
            "workflow-integrations": {
                "command": "/plugins/monolithic-dev-harness/bin/harness-python"
            },
            "Azure DevOps": {"command": "npx", "args": ["@azure-devops/mcp", "org"]},
            "personal": {"command": "other"},
        }
    }
    config.write_text(json.dumps(original))
    monkeypatch.setattr(inventory, "ADAPTERS", {"fake": "fake"})
    monkeypatch.setattr(
        inventory,
        "adapter_for",
        lambda _: Ok(
            InstallationAdapter("fake", lambda _: (Location(config, "local", "mcp"),))
        ),
    )
    context = InstallationContext(tmp_path / "home", (project,))
    repair = next(
        finding.repairs[0]
        for finding in inventory.findings(inventory.scan(context))
        if finding.code == "private-provider-registration"
    )
    assert isinstance(apply_repairs((repair,), context), Ok)
    assert json.loads(config.read_text())["mcpServers"] == {
        key: value
        for key, value in original["mcpServers"].items()
        if key != "Azure DevOps"
    }
    assert (
        json.loads(next((project / ".harness/repair-backups").iterdir()).read_text())
        == original
    )
