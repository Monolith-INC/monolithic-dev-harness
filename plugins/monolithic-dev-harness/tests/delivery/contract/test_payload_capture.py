import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.payload_capture import capture_hook_payload


class TestPayloadCapture(unittest.TestCase):
    def test_writes_capture_file_with_payload_and_metadata(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "echo hi"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            capture_path = capture_hook_payload(
                client="codex",
                payload=payload,
                capture_dir=tmpdir,
                project_root="/workspace/project",
            )

            self.assertIsNotNone(capture_path)
            recorded = json.loads(Path(capture_path).read_text(encoding="utf-8"))

            self.assertEqual(recorded["client"], "codex")
            self.assertEqual(recorded["project_root"], "/workspace/project")
            self.assertEqual(recorded["payload"], payload)
            self.assertIsNotNone(datetime.fromisoformat(recorded["captured_at"]).tzinfo)

    def test_skips_capture_when_directory_is_missing(self):
        payload = {"tool_name": "Bash"}

        capture_path = capture_hook_payload(
            client="codex",
            payload=payload,
            capture_dir=None,
            project_root="/workspace/project",
        )

        self.assertIsNone(capture_path)


if __name__ == "__main__":
    unittest.main()
