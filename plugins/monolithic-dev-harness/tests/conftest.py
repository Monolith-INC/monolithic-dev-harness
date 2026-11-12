"""No test reaches a real tracker server, or reads the machine's git configuration.

A tracker opened through the registry would start its provider's server (for Azure DevOps, `npx
@azure-devops/mcp`), which signs in through the user's browser. Every test talks to a fake
server instead: one it hands over (`tests/backlog/azure_tracker.serving`) or none at all.

The repositories tests create use git's defaults only. A global ignore such as `**/.harness/`
would otherwise keep `.harness/` out of their commits, and the tests would fail on that machine
alone."""

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


@pytest.fixture(autouse=True)
def no_machine_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Harness Tests")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "tests@example.invalid")
