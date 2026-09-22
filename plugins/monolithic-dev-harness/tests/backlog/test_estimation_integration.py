import json
import tempfile
import unittest
from pathlib import Path

from orchestrator_core.artifact_validator import validate_artifact
from orchestrator_core.handlers import HANDLERS, handle_plan_capacity
from orchestrator_core.ingest import coerce_float, ingest_from_text, ingest_file
from orchestrator_core.project_config import update_config

AZURE_PAYLOADS = {
    "iteration": {"id": "it1", "attributes": {"startDate": "2026-08-03", "finishDate": "2026-08-14"}},
    "capacities": {
        "value": [
            {
                "teamMember": {"id": "u1", "displayName": "Ana"},
                "activities": [{"capacityPerDay": 6, "name": "Development"}],
                "daysOff": [],
            }
        ]
    },
    "team_settings": {"workingDays": ["monday", "tuesday", "wednesday", "thursday", "friday"]},
    "work_items": {
        "value": [
            {
                "id": 101,
                "fields": {
                    "System.Title": "Task A",
                    "Microsoft.VSTS.Scheduling.RemainingWork": 40,
                    "Microsoft.VSTS.Common.Activity": "Development",
                },
            }
        ]
    },
}


def _effort_check(text):
    record = ingest_from_text(text)
    return next(c for c in validate_artifact(record) if c.name == "content-effort-hours-plausible")


class TestCoerceFloat(unittest.TestCase):
    """Tests for frontmatter numeric coercion."""

    def test_numbers_and_numeric_strings(self):
        """Both a real number and its string form coerce."""
        self.assertEqual(coerce_float(4), 4.0)
        self.assertEqual(coerce_float("4.5"), 4.5)

    def test_non_numeric_returns_none(self):
        """Anything unparseable is None, never a guessed value."""
        self.assertIsNone(coerce_float(None))
        self.assertIsNone(coerce_float("many"))
        self.assertIsNone(coerce_float(True))


class TestIngestEffortHours(unittest.TestCase):
    """Tests for reading effort_hours off an artifact."""

    def test_effort_hours_read_from_frontmatter(self):
        """The new key lands on the record."""
        record = ingest_from_text("---\nstory_points: 3\neffort_hours: 5\n---\n\n# Draft\n")
        self.assertEqual(record.effort_hours, 5.0)

    def test_absent_effort_hours_is_none_not_zero(self):
        """Unestimated must be distinguishable from estimated-at-zero."""
        self.assertIsNone(ingest_from_text("---\nstory_points: 3\n---\n\n# Draft\n").effort_hours)

    def test_file_reads_effort_hours(self):
        """The file path and the text path agree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "1234-draft.md"
            path.write_text("---\nstory_points: 2\neffort_hours: 3.5\n---\n\n# Draft\n", encoding="utf-8")
            self.assertEqual(ingest_file(path).effort_hours, 3.5)


class TestEffortHoursCheck(unittest.TestCase):
    """Tests for the advisory plausibility check."""

    def test_missing_estimate_skips_rather_than_fails(self):
        """Leaving the field empty is honest and must not fail validation."""
        self.assertEqual(_effort_check("---\nstory_points: 3\n---\n\n# X\n").result, "SKIP")

    def test_plausible_estimate_passes(self):
        """A figure inside the band for its points is fine."""
        self.assertEqual(_effort_check("---\nstory_points: 3\neffort_hours: 5\n---\n\n# X\n").result, "PASS")

    def test_implausible_estimate_warns(self):
        """A figure contradicting its own points is surfaced, not blocked."""
        check = _effort_check("---\nstory_points: 3\neffort_hours: 40\n---\n\n# X\n")
        self.assertEqual(check.result, "WARN")
        self.assertIn("outside", check.detail)

    def test_non_positive_estimate_warns(self):
        """Zero hours is not a valid estimate."""
        self.assertEqual(_effort_check("---\nstory_points: 3\neffort_hours: 0\n---\n\n# X\n").result, "WARN")

    def test_hours_without_points_passes(self):
        """With nothing to compare against, the check cannot object."""
        self.assertEqual(_effort_check("---\neffort_hours: 7\n---\n\n# X\n").result, "PASS")

    def test_check_never_fails_validation(self):
        """This check is advisory by design; it must never emit FAIL."""
        for body in (
            "---\nstory_points: 3\n---\n\n# X\n",
            "---\nstory_points: 3\neffort_hours: 999\n---\n\n# X\n",
            "---\nstory_points: 3\neffort_hours: -1\n---\n\n# X\n",
        ):
            self.assertNotEqual(_effort_check(body).result, "FAIL")

    def test_validator_uses_team_estimation_bands(self):
        """Validation compares hours with the configured team band, not seed defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            (state_dir / "estimation.json").write_text(
                json.dumps({"bands": {"3": [30, 50]}}), encoding="utf-8"
            )
            record = ingest_from_text(
                "---\nstory_points: 3\neffort_hours: 40\n---\n\n# X\n"
            )
            checks = validate_artifact(record, state_dir=state_dir)
            effort = next(c for c in checks if c.name == "content-effort-hours-plausible")
            self.assertEqual(effort.result, "PASS")

    def test_validator_reports_rejected_estimation_bands(self):
        """Invalid custom bands fall back safely and remain visible as a diagnostic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            (state_dir / "estimation.json").write_text(
                json.dumps({"bands": {"3": [4, 6], "five": "invalid"}}), encoding="utf-8"
            )
            checks = validate_artifact(ingest_from_text("# X\n"), state_dir=state_dir)
            diagnostic = next(c for c in checks if c.name == "config-estimation-bands-valid")
            self.assertEqual(diagnostic.result, "WARN")
            self.assertIn("five", diagnostic.detail)


class TestPlanCapacityHandler(unittest.TestCase):
    """Tests for the orchestrator handler."""

    def test_handler_is_registered(self):
        """The handler joins the existing registry."""
        self.assertIn("plan-capacity", HANDLERS)

    def _run(self, arguments, project_root, *, artifacts_path=None):
        """state_dir is <project>/.agile-backlog-toolkit; the handler derives the root from it."""
        root = Path(project_root)
        state_dir = root / ".agile-backlog-toolkit"
        state_dir.mkdir(parents=True, exist_ok=True)
        if artifacts_path:
            update_config(root, artifacts_path=artifacts_path)
        return handle_plan_capacity(
            arguments, skills_dir=Path("."), state_dir=state_dir, instructions=""
        )

    def test_azure_payloads_produce_a_plan(self):
        """Injected Azure JSON flows through to a capacity plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(
                {
                    "iteration_ref": "it1",
                    "provider": "azure-devops",
                    "payloads": AZURE_PAYLOADS,
                    "process": "agile",
                },
                Path(tmpdir),
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["available_hours"], 60.0)
            self.assertEqual(result["planned_hours"], 40.0)
            self.assertFalse(result["overcommitted"])

    def test_overcommitment_is_reported(self):
        """Planning beyond capacity is flagged on the result."""
        payloads = json.loads(json.dumps(AZURE_PAYLOADS))
        payloads["work_items"]["value"][0]["fields"]["Microsoft.VSTS.Scheduling.RemainingWork"] = 90
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(
                {"iteration_ref": "it1", "provider": "azure-devops", "payloads": payloads},
                Path(tmpdir),
            )
            self.assertTrue(result["overcommitted"])

    def test_unknown_provider_errors_cleanly(self):
        """An unknown provider is an error message, not an exception."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run({"provider": "jira"}, Path(tmpdir))
            self.assertFalse(result["ok"])
            self.assertIn("unknown provider", result["error"])

    def test_suggestions_require_confirmation(self):
        """Every suggested figure is marked as needing a human before it is used."""
        draft = "---\nwork_item_type: User Story\nstory_points: 3\n---\n\n# Draft\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            tickets = Path(tmpdir) / "Tickets" / "Ready"
            tickets.mkdir(parents=True)
            (tickets / "1234-draft.md").write_text(draft, encoding="utf-8")
            result = self._run({"provider": "filesystem"}, Path(tmpdir), artifacts_path=".")
            self.assertTrue(result["suggestions"])
            for suggestion in result["suggestions"]:
                self.assertTrue(suggestion["requires_confirmation"])
                self.assertEqual(suggestion["provenance"], "seed-default")

    def test_no_suggestion_for_already_estimated_items(self):
        """An item that already has hours is left alone."""
        draft = "---\nwork_item_type: User Story\nstory_points: 3\neffort_hours: 5\n---\n\n# Draft\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            tickets = Path(tmpdir) / "Tickets" / "Ready"
            tickets.mkdir(parents=True)
            (tickets / "1234-draft.md").write_text(draft, encoding="utf-8")
            result = self._run({"provider": "filesystem"}, Path(tmpdir), artifacts_path=".")
            self.assertEqual(result["suggestions"], [])

    def test_filesystem_provider_refuses_to_guess_a_location(self):
        """With no artifacts path configured, the plugin asks rather than assuming one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run({"provider": "filesystem"}, Path(tmpdir))
            self.assertFalse(result["ok"])
            self.assertIn("No artifacts path configured", result["error"])

    def test_no_directories_are_created_outside_the_plugin_state(self):
        """Running the handler must not provision anything in the project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self._run({"provider": "filesystem"}, root)
            created = {p.name for p in root.iterdir()}
            self.assertEqual(created, {".agile-backlog-toolkit"})


if __name__ == "__main__":
    unittest.main()
