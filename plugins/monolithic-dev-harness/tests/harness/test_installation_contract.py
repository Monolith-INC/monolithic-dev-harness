"""The installation lifecycle is one product contract across registered adapters."""

import pytest

from core.result import Ok
from host_adapters.installation_contract import adapter_for
from host_adapters.subagents import ADAPTERS


@pytest.mark.parametrize("host", tuple(ADAPTERS))
def test_each_supported_host_implements_installation_contract(host):
    result = adapter_for(host)
    assert isinstance(result, Ok)
    assert result.value.host == host
    assert result.value.version == 1
    assert callable(result.value.locations)
    assert callable(result.value.discover_projects)
    assert callable(result.value.removal_commands)
    assert callable(result.value.verify_user)
    assert callable(result.value.preflight_user)


@pytest.mark.parametrize("host", tuple(ADAPTERS))
def test_every_adapter_supplies_project_translation(host):
    assert callable(adapter_for(host).value.project_assets)


@pytest.mark.parametrize("host", tuple(ADAPTERS))
def test_every_adapter_installs_the_same_service_catalog(host, tmp_path):
    import json
    from pathlib import Path

    from harness.installation_inventory import scan
    from host_adapters.installation_contract import InstallationContext

    plugin = Path(__file__).resolve().parents[2]
    project = tmp_path / "project"
    project.mkdir()
    planned = adapter_for(host).value.project_assets(project, plugin)
    assert isinstance(planned, Ok)
    tuple(
        (
            asset.path.parent.mkdir(parents=True, exist_ok=True),
            asset.path.write_text(asset.text),
        )
        for asset in planned.value
        if asset.kind == "file"
    )
    inventory = scan(InstallationContext(tmp_path / "home", (project,)))
    assert not inventory.errors
    expected = set(json.loads((plugin / "codex.mcp.json").read_text())["mcpServers"])
    assert {
        component.selector[-1]
        for component in inventory.components
        if component.kind == "mcp" and component.scope == "local"
    } == expected
