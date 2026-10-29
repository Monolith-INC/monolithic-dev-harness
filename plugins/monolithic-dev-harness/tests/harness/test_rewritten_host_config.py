"""Uninstall still finds the harness's tables after a host rewrites its config without markers."""

from __future__ import annotations

import tomllib

import pytest

from harness.installation_files import BEGIN, END, _restore_toml

BEFORE = '[features]\nx = true\n\n[mcp_servers."Azure DevOps"]\ncommand = "npx"\n'
AFTER = (
    "[features]\nx = true\n\n"
    + BEGIN
    + '[mcp_servers."workflow-integrations"]\ncommand = "sh"\nargs = ["/p/harness-python", "gw"]\n'
    + '[mcp_servers."workflow-integrations".env]\n"PYTHONPATH" = "/p"\n'
    + END
)
# Codex writes it back sorted, unquoted and without the markers.
REWRITTEN = (
    '[features]\nx = true\n\n[mcp_servers.workflow-integrations]\ncommand = "sh"\n'
    'args = [\n    "/p/harness-python",\n    "gw",\n]\n\n'
    '[mcp_servers.workflow-integrations.env]\nPYTHONPATH = "/p"\n\n'
    '[mcp_servers."Azure DevOps"]\ncommand = "npx"\n'
)
RECORD = {"before": BEFORE, "after": AFTER}


def test_a_rewritten_config_returns_to_its_original() -> None:
    assert tomllib.loads(_restore_toml(REWRITTEN, RECORD)) == tomllib.loads(BEFORE)


def test_a_table_the_user_added_since_is_kept() -> None:
    added = REWRITTEN + '\n[mcp_servers.mine]\ncommand = "keep"\n'
    restored = tomllib.loads(_restore_toml(added, RECORD))
    assert restored["mcp_servers"]["mine"] == {"command": "keep"}
    assert "workflow-integrations" not in restored["mcp_servers"]


def test_an_edited_harness_table_is_refused() -> None:
    edited = REWRITTEN.replace('command = "sh"', 'command = "sh"\ntimeout = 9')
    with pytest.raises(ValueError, match="owned TOML block changed"):
        _restore_toml(edited, RECORD)
