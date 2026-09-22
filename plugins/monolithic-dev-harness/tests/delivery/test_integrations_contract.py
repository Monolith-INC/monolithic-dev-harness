import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.integrations.adapters import tracker_adapter
from scripts.integrations.config import load_config
from scripts.integrations.contracts import IntegrationError
from scripts.integrations.gateway import handle_call, process_message
from scripts.integrations.local_tracker import LOCAL_TRACKER_BINDINGS


class IntegrationContractTests(unittest.TestCase):
    def _config(self, root: Path) -> None:
        path = root / ".codex-workflows" / "integrations.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "branchTemplate": "{category}/{key}-{slug}",
                    "tracker": {
                        "adapter": "linear",
                        "connection": {"command": "true", "args": []},
                        "bindings": {},
                    },
                    "scm": {
                        "adapter": "github",
                        "connection": {"command": "true", "args": []},
                    },
                }
            )
        )

    def test_branch_convention_maps_linear_and_azure_keys(self):
        adapter = tracker_adapter(
            {
                "adapter": "linear",
                "branchPattern": "{category}/{key}-{slug}",
                "connection": {"command": "true", "args": []},
            }
        )
        self.assertEqual(adapter.resolve_branch_key("feature/ENG-42-work"), "ENG-42")
        self.assertEqual(adapter.resolve_branch_key("bug/123-fix"), "123")
        self.assertIsNone(adapter.resolve_branch_key("feature/no-key"))

    def test_config_requires_generic_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._config(root)
            config = load_config(root)
            self.assertEqual(config.branch_template, "{category}/{key}-{slug}")
            self.assertTrue(config.tracking_enabled)

    def test_gateway_advertises_tracker_and_scm_boundaries(self):
        response = json.loads(
            process_message(
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            )
        )
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertIn("tracker_create_work_item", names)
        self.assertIn("tracker_publish_artifact", names)
        self.assertIn("tracker_list_children", names)
        self.assertIn("scm_create_pull_request", names)
        self.assertIn("scm_list_review_threads", names)

    def test_paused_tracking_hides_tracker_tools_and_preserves_local_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".codex-workflows" / "integrations.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "branchTemplate": "{category}/{key}-{slug}",
                        "tracker": {
                            "adapter": "local_tracker",
                            "root": ".local-tracker",
                            "connection": {
                                "command": sys.executable,
                                "args": [
                                    str(
                                        Path(__file__).parents[2]
                                        / "scripts"
                                        / "integrations"
                                        / "run_local_tracker.py"
                                    ),
                                    "--project-root",
                                    str(root),
                                    "--root",
                                    ".local-tracker",
                                ],
                            },
                            "bindings": dict(LOCAL_TRACKER_BINDINGS),
                            "mappings": {
                                "kinds": {
                                    "epic": "epic",
                                    "feature": "feature",
                                    "user_story": "user_story",
                                    "task": "task",
                                    "bug": "bug",
                                },
                                "states": {
                                    "backlog": "backlog",
                                    "ready": "ready",
                                    "in_progress": "in_progress",
                                    "done": "done",
                                    "canceled": "canceled",
                                },
                            },
                        },
                        "scm": {
                            "adapter": "github",
                            "connection": {"command": "true", "args": []},
                        },
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                handle_call("workflow_tracking_status", {}, project_root=root)[
                    "enabled"
                ]
            )
            skipped = handle_call("workflow_skip_tracker", {}, project_root=root)
            self.assertEqual(
                skipped,
                {"mode": "skipped", "enabled": False, "adapter": "local_tracker"},
            )
            tools = json.loads(
                process_message(
                    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
                    project_root=root,
                )
            )
            names = {tool["name"] for tool in tools["result"]["tools"]}
            self.assertNotIn("tracker_create_work_item", names)
            self.assertIn("scm_create_pull_request", names)
            with self.assertRaises(IntegrationError) as raised:
                handle_call(
                    "tracker_create_work_item",
                    {"kind": "epic", "title": "Blocked"},
                    project_root=root,
                )
            self.assertEqual(raised.exception.code, "tracking_paused")

            resumed = handle_call("workflow_resume_tracker", {}, project_root=root)
            self.assertEqual(
                resumed,
                {"mode": "enforced", "enabled": True, "adapter": "local_tracker"},
            )
            created = handle_call(
                "tracker_create_work_item",
                {"kind": "epic", "title": "Quality"},
                project_root=root,
            )
            self.assertEqual(created["key"], "EPIC-0001")


if __name__ == "__main__":
    unittest.main()
