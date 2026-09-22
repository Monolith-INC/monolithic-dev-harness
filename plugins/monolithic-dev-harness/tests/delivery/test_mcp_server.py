import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.orchestrator.engine import OrchestratorEngine
from scripts.orchestrator.mcp_server import (
    default_skills_dir,
    process_message,
    resolve_skills_dir,
)


class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.skills_dir = Path(self.test_dir.name)

        skill_path = self.skills_dir / "mock-skill"
        skill_path.mkdir()
        manifest_path = skill_path / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "name": "mock-skill",
                    "description": "A mock skill for testing",
                    "input_schema": {
                        "type": "object",
                        "properties": {"arg1": {"type": "string"}},
                    },
                    "output_signature": {"type": "object", "properties": {}},
                },
                f,
            )
        (skill_path / "SKILL.md").write_text(
            "# Mock skill\n\nRun mock.\n", encoding="utf-8"
        )
        self.engine = OrchestratorEngine(self.skills_dir)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_initialize(self):
        request = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        response_str = process_message(request, self.engine)

        response = json.loads(response_str)
        self.assertEqual(response["id"], 1)
        self.assertIn("capabilities", response["result"])
        self.assertEqual(
            response["result"]["serverInfo"]["name"], "agentic-orchestrator"
        )

    def test_tools_list(self):
        request = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        response_str = process_message(request, self.engine)

        response = json.loads(response_str)
        tools = response["result"]["tools"]

        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "mock-skill")
        self.assertEqual(tools[0]["description"], "A mock skill for testing")
        self.assertIn("arg1", tools[0]["inputSchema"]["properties"])

    def test_resolve_skills_dir_uses_repo_default(self):
        resolved = resolve_skills_dir()
        self.assertTrue(resolved.is_dir())
        self.assertEqual(resolved, default_skills_dir())

    def test_non_dict_json_payload_is_ignored(self):
        response_str = process_message("123", self.engine)
        self.assertEqual(response_str, "")

    def test_tools_call(self):
        request = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "mock-skill",
                    "arguments": {"arg1": "value"},
                },
            }
        )
        response_str = process_message(request, self.engine)

        response = json.loads(response_str)
        content = response["result"]["content"]

        self.assertEqual(len(content), 1)
        payload = json.loads(content[0]["text"])
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["output"]["skill"], "mock-skill")
        self.assertIn("prompt", payload["output"])

    def test_run_mcp_server_launcher_works_from_foreign_cwd(self):
        """Cursor spawns MCP without plugin root on PYTHONPATH/cwd; launcher must still import."""
        import subprocess
        import sys

        launcher = (
            Path(__file__).resolve().parents[2]
            / "scripts"
            / "orchestrator"
            / "run_mcp_server.py"
        )
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["ORCHESTRATOR_SKILLS_DIR"] = str(self.skills_dir)
        request = (
            json.dumps(
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
            )
            + "\n"
        )
        proc = subprocess.run(
            [sys.executable, str(launcher)],
            input=request,
            capture_output=True,
            text=True,
            cwd="/tmp",
            env=env,
            timeout=20,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ModuleNotFoundError", proc.stderr)
        response = json.loads(proc.stdout.strip().splitlines()[0])
        self.assertEqual(
            response["result"]["serverInfo"]["name"], "agentic-orchestrator"
        )


if __name__ == "__main__":
    unittest.main()
