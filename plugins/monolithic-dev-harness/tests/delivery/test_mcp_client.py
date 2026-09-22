import json
import os
import unittest
from unittest.mock import MagicMock, patch

from scripts.integrations.contracts import IntegrationError
from scripts.integrations.mcp_client import StdioMcpClient, client_from_connection


class StdioMcpClientTests(unittest.TestCase):
    def test_client_from_connection_expandvars(self):
        with patch.dict(os.environ, {"AZURE_DEVOPS_ORG": "contoso"}, clear=False):
            client = client_from_connection(
                {"command": "echo", "args": ["${AZURE_DEVOPS_ORG}", "x"], "timeout": 1}
            )
        self.assertEqual(client.args, ["contoso", "x"])

    def test_initialize_params_include_required_fields(self):
        client = StdioMcpClient("true", [], timeout=0.2)
        sent = []

        process = MagicMock()
        process.stdin = MagicMock()
        process.stdout = MagicMock()
        process.stdout.readline.side_effect = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}) + "\n",
            json.dumps({"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}) + "\n",
        ]

        def capture_send(proc, payload):
            sent.append(payload)

        with (
            patch(
                "scripts.integrations.mcp_client.subprocess.Popen", return_value=process
            ),
            patch.object(StdioMcpClient, "_send", side_effect=capture_send),
            patch(
                "scripts.integrations.mcp_client.select.select",
                return_value=([process.stdout], [], []),
            ),
        ):
            client.list_tools()

        init = next(item for item in sent if item.get("method") == "initialize")
        self.assertEqual(init["params"]["protocolVersion"], "2024-11-05")
        self.assertIn("capabilities", init["params"])
        self.assertEqual(
            init["params"]["clientInfo"]["name"], "codex-workflows-integrations"
        )

    def test_read_response_times_out_when_select_idle(self):
        client = StdioMcpClient("true", [], timeout=0.05)
        process = MagicMock()
        process.stdout = MagicMock()
        with (
            patch(
                "scripts.integrations.mcp_client.select.select",
                return_value=([], [], []),
            ),
            self.assertRaises(IntegrationError) as ctx,
        ):
            client._read_response(process, 1)
        self.assertEqual(ctx.exception.code, "provider_timeout")


if __name__ == "__main__":
    unittest.main()
