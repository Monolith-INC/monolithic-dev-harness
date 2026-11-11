"""No test reaches a real tracker server.

A tracker opened through the registry would start its provider's server (for Azure DevOps, `npx
@azure-devops/mcp`), which signs in through the user's browser. Every test talks to a fake
server instead: one it hands over (`tests/backlog/azure_tracker.serving`) or none at all."""

import pytest


@pytest.fixture(autouse=True)
def no_real_tracker_server(monkeypatch: pytest.MonkeyPatch) -> None:
    from integrations import registry, transport

    monkeypatch.setattr(
        registry,
        "_transport",
        lambda active, repo: transport.unavailable(
            f"tests never reach the real {active.manifest.name} server"
        ),
    )
