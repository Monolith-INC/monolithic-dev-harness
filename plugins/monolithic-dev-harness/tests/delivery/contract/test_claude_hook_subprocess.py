import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = PLUGIN_ROOT / "scripts" / "harness" / "hook.py"


class TestClaudeHookSubprocess(unittest.TestCase):
    """The Claude entry point runs as a subprocess and stays silent when it allows a call."""

    def _run_hook(self, payload: dict) -> str:
        process = subprocess.run(
            [sys.executable, str(HOOK_PATH), "--host", "claude", "--event", "pre-tool"],
            input=json.dumps({"cwd": str(PLUGIN_ROOT), **payload}),
            capture_output=True,
            text=True,
            cwd=PLUGIN_ROOT,
            timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return process.stdout

    def test_bash_allow_emits_no_output(self):
        self.assertEqual(
            self._run_hook({"tool_name": "Bash", "tool_input": {"command": "echo hi"}}),
            "",
        )

    def test_markdown_read_is_allowed(self):
        stdout = self._run_hook(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": str(PLUGIN_ROOT / "README.md")},
            }
        )
        self.assertEqual(stdout, "")


if __name__ == "__main__":
    unittest.main()
