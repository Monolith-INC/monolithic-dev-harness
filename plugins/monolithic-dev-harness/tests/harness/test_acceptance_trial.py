from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPOSITORY = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY / "scripts"))

import acceptance_trial  # noqa: E402


class AcceptanceTrialTests(unittest.TestCase):
    def test_local_planning_profile_builds_private_settings_and_tracker(self):
        project = acceptance_trial.prepare("local-planning")
        try:
            settings = json.loads((project / ".harness/settings.json").read_text())
            self.assertEqual(settings["tracker"]["name"], "local")
            self.assertEqual(settings["artifacts_path"], "docs/planning")
            self.assertTrue((project / ".harness/tracker/backlog").is_dir())
            environment = acceptance_trial.runner_environment(str(project))
            self.assertEqual(Path(environment["TMPDIR"]).stat().st_mode & 0o777, 0o700)
            self.assertEqual(
                Path(environment["HARNESS_USER_STATE_DIR"]).stat().st_mode & 0o777,
                0o700,
            )
            codex_home = Path(environment["CODEX_HOME"])
            self.assertEqual(codex_home.stat().st_mode & 0o777, 0o700)
            auth_source = (
                Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
            )
            if auth_source.is_file():
                self.assertTrue((codex_home / "auth.json").is_symlink())
        finally:
            acceptance_trial.discard(str(project))

    def test_settings_merge_does_not_change_profile_inputs(self):
        base = {"tracker": {"name": "local", "values": {"one": "1"}}}
        override = {"tracker": {"values": {"two": "2"}}}
        merged = acceptance_trial.merge(base, override)
        self.assertEqual(
            merged["tracker"],
            {"name": "local", "values": {"one": "1", "two": "2"}},
        )
        self.assertEqual(base["tracker"]["values"], {"one": "1"})

    def test_runner_command_cleans_its_copy_after_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run.json"
            code = (
                "import json,os,pathlib; "
                "pathlib.Path(os.environ['TRIAL_OUTPUT']).write_text(json.dumps({"
                "'cwd':os.getcwd(),'tmp':os.environ['TMPDIR'],"
                "'prefs':os.environ['HARNESS_USER_STATE_DIR'],"
                "'thread':os.getenv('CODEX_THREAD_ID',''),"
                "'pipe':os.getenv('CODEX_APP_TOOLS_PIPE_PATH','')}))"
            )
            with patch.dict(
                os.environ,
                {
                    "TRIAL_OUTPUT": str(output),
                    "CODEX_THREAD_ID": "parent-thread",
                    "CODEX_APP_TOOLS_PIPE_PATH": "/tmp/parent.sock",
                },
            ):
                result = acceptance_trial.run_trial(
                    "local-planning", None, [sys.executable, "-c", code]
                )
            self.assertEqual(result, 0)
            details = json.loads(output.read_text())
            self.assertFalse(Path(details["cwd"]).exists())
            self.assertFalse(Path(details["tmp"]).exists())
            self.assertFalse(Path(details["prefs"]).exists())
            self.assertEqual(details["thread"], "")
            self.assertEqual(details["pipe"], "")

    def test_run_command_dispatches_the_requested_process(self):
        result = subprocess.run(
            [
                sys.executable,
                str(REPOSITORY / "scripts" / "acceptance_trial.py"),
                "run",
                "--profile",
                "local-planning",
                "--",
                sys.executable,
                "-c",
                "print('trial command started')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("trial command started", result.stdout)

    def test_startup_cleanup_removes_only_abandoned_owned_run_directories(self):
        old = acceptance_trial.prepare(
            root_prefix=acceptance_trial.RUN_PREFIX, kind="run"
        )
        old_root = old.parent
        active = acceptance_trial.prepare(
            root_prefix=acceptance_trial.RUN_PREFIX, kind="run"
        )
        active_root = active.parent
        marker_path = old_root / acceptance_trial.MARKER_NAME
        marker = json.loads(marker_path.read_text())
        marker["process_id"] = 2**30
        marker_path.write_text(json.dumps(marker))
        prepared = acceptance_trial.prepare()
        try:
            result = acceptance_trial.run_trial(
                "unconfigured", None, [sys.executable, "-c", "pass"]
            )
            self.assertEqual(result, 0)
            self.assertFalse(old_root.exists())
            self.assertTrue(active_root.exists())
            self.assertTrue(prepared.exists())
        finally:
            acceptance_trial.discard(str(prepared))
            acceptance_trial.discard(str(active))

    def test_transcript_summary_counts_explicit_reads_and_deduplicates_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            transcript = Path(folder) / "run.jsonl"
            events = (
                {
                    "type": "item.started",
                    "item": {
                        "id": "cmd-1",
                        "type": "command_execution",
                        "command": "cat README.md",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "cmd-1",
                        "type": "command_execution",
                        "command": "/bin/bash -lc 'cat README.md'",
                        "status": "completed",
                        "exit_code": 0,
                    },
                },
                {
                    "type": "item.completed",
                    "item": {"type": "file_read", "path": "docs/plan.md"},
                },
                {
                    "type": "item.completed",
                    "item": {"type": "file_read", "path": "docs/plan.md"},
                },
            )
            transcript.write_text("\n".join(json.dumps(event) for event in events))
            summary = acceptance_trial.summarize_transcript(str(transcript))
        self.assertEqual(summary["command_execution_items"], 1)
        self.assertEqual(summary["simple_shell_read_requests"], 1)
        self.assertEqual(summary["simple_shell_read_paths"], ["README.md"])
        self.assertEqual(summary["explicit_file_read_requests"], 2)
        self.assertEqual(summary["unique_read_paths"], 1)

    def test_transcript_summary_counts_reads_inside_chained_shell_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            transcript = Path(folder) / "chained.jsonl"
            event = {
                "type": "item.completed",
                "item": {
                    "id": "cmd-1",
                    "type": "command_execution",
                    "command": "/bin/bash -lc 'cat README.md && cat lib/state.dart; sed -n 1,10p app.dart; rg --files test'",
                    "status": "completed",
                    "exit_code": 0,
                },
            }
            transcript.write_text(json.dumps(event))

            summary = acceptance_trial.summarize_transcript(str(transcript))

        self.assertEqual(summary["simple_shell_read_requests"], 3)
        self.assertEqual(
            summary["simple_shell_read_paths"],
            ["README.md", "lib/state.dart", "app.dart"],
        )
        self.assertEqual(summary["unique_simple_shell_read_paths"], 3)

    def test_transcript_summary_does_not_count_failed_command_operands_as_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            transcript = Path(folder) / "failed.jsonl"
            event = {
                "type": "item.completed",
                "item": {
                    "id": "cmd-1",
                    "type": "command_execution",
                    "command": "/bin/bash -lc 'cat available.md && cat missing.md && cat skipped.md'",
                    "status": "failed",
                    "exit_code": 1,
                },
            }
            transcript.write_text(json.dumps(event))

            summary = acceptance_trial.summarize_transcript(str(transcript))

        self.assertEqual(summary["simple_shell_read_requests"], 0)
        self.assertEqual(summary["failed_command_execution_items"], 1)
        self.assertEqual(
            summary["unverified_shell_read_operands"],
            ["available.md", "missing.md", "skipped.md"],
        )

    def test_transcript_summary_counts_non_json_runner_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            transcript = Path(folder) / "mixed-output.jsonl"
            transcript.write_text(
                "runner warning\n"
                + json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "file_read", "path": "README.md"},
                    }
                )
            )
            summary = acceptance_trial.summarize_transcript(str(transcript))
        self.assertEqual(summary["non_json_lines"], 1)
        self.assertEqual(summary["explicit_file_read_requests"], 1)


if __name__ == "__main__":
    unittest.main()
