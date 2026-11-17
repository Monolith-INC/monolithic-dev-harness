from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from harness import cli

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


class HostMcpConfigTest(unittest.TestCase):
    def test_hosts_register_gateway_without_native_azure_server(self) -> None:
        for config_name, host in (
            (".mcp.json", "claude"),
            ("codex.mcp.json", "codex"),
            ("cursor.mcp.json", "cursor"),
        ):
            with self.subTest(config=config_name):
                servers = json.loads(
                    (PLUGIN_ROOT / config_name).read_text(encoding="utf-8")
                )["mcpServers"]
                self.assertIn("workflow-integrations", servers)
                self.assertNotIn("azure-devops", servers)
                self.assertEqual(
                    servers["workflow-integrations"]["env"]["MDH_GATEWAY_HOST"],
                    host,
                )

    def test_markerless_legacy_gateway_config_uses_default_owner(self) -> None:
        from integrations.run_gateway import gateway_host

        with mock.patch.dict(os.environ):
            os.environ.pop("MDH_GATEWAY_HOST", None)
            self.assertEqual(gateway_host(), "default")
            os.environ["MDH_GATEWAY_HOST"] = "kimi"
            self.assertEqual(gateway_host(), "kimi")

    def test_doctor_does_not_start_a_second_azure_provider_connection(self) -> None:
        active = SimpleNamespace(
            manifest=SimpleNamespace(
                name="azure-devops", connection={"kind": "mcp"}, tools={}
            ),
            values={},
        )
        with mock.patch.object(
            cli.registry,
            "connection_command",
            side_effect=AssertionError("must not start the provider directly"),
        ):
            result = cli._tools(Path("."), active)
        self.assertEqual(result[0], "skip")
        self.assertIn("workflow-integrations", result[2])
