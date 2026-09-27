import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from azure_tracker import azure, tracker

from orchestrator_core.capacity import plan_iteration
from orchestrator_core.providers import (
    CapacityProvider,
    FilesystemProvider,
    TrackerProvider,
)

f = azure
map_capacities = azure.map_capacities
map_days_off = azure.map_days_off
map_iteration = azure.map_iteration
map_weekend_days = azure.map_weekend_days
map_work_item = azure.map_work_item
map_work_items = azure.map_work_items

# Shaped after the responses documented for the Azure DevOps work/capacities API.
CAPACITIES_PAYLOAD = {
    "count": 2,
    "value": [
        {
            "teamMember": {"id": "u1", "displayName": "Chuck Reinhart"},
            "activities": [
                {"capacityPerDay": 5, "name": "Development"},
                {"capacityPerDay": 3, "name": "Testing"},
            ],
            "daysOff": [
                {"start": "2026-08-05T00:00:00Z", "end": "2026-08-06T00:00:00Z"}
            ],
        },
        {
            "teamMember": {"id": "u2", "displayName": "Ana Souza"},
            "activities": [{"capacityPerDay": 6, "name": "Development"}],
            "daysOff": [],
        },
    ],
}

ITERATION_PAYLOAD = {
    "id": "it1",
    "name": "Sprint 42",
    "attributes": {
        "startDate": "2026-08-03T00:00:00Z",
        "finishDate": "2026-08-14T00:00:00Z",
    },
}

TEAM_SETTINGS_PAYLOAD = {
    "workingDays": ["monday", "tuesday", "wednesday", "thursday", "friday"]
}

WORK_ITEMS_PAYLOAD = {
    "value": [
        {
            "id": 101,
            "fields": {
                "System.Title": "Wire the form",
                "System.WorkItemType": "Task",
                "System.State": "Active",
                "Microsoft.VSTS.Scheduling.RemainingWork": 12,
                "Microsoft.VSTS.Common.Activity": "Development",
                "System.AssignedTo": {"displayName": "Chuck Reinhart"},
            },
        },
        {
            "id": 102,
            "fields": {
                "System.Title": "Login story",
                "System.WorkItemType": "User Story",
                "Microsoft.VSTS.Scheduling.StoryPoints": 5,
            },
        },
    ]
}


class TestCapacitySources(unittest.TestCase):
    """The planner reads from the user's planning files or from the selected tracker."""

    def test_both_sources_satisfy_the_protocol(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for provider in (
                FilesystemProvider(Path(tmpdir)),
                TrackerProvider(tracker(), {}),
            ):
                self.assertIsInstance(provider, CapacityProvider)


class TestAzureFields(unittest.TestCase):
    """Tests for the field-reference constants and process guards."""

    def test_process_normalisation(self):
        """Process names resolve case-insensitively and default to Agile."""
        self.assertEqual(f.normalize_process("Scrum"), f.PROCESS_SCRUM)
        self.assertEqual(f.normalize_process("Agile"), f.PROCESS_AGILE)
        self.assertEqual(f.normalize_process("CMMI"), f.PROCESS_CMMI)
        self.assertEqual(f.normalize_process(None), f.PROCESS_AGILE)
        self.assertEqual(f.normalize_process("something else"), f.PROCESS_AGILE)

    def test_points_field_varies_by_process(self):
        """Each process keeps its relative-size field under a different name."""
        self.assertEqual(f.points_field("agile"), f.STORY_POINTS)
        self.assertEqual(f.points_field("scrum"), f.EFFORT)
        self.assertEqual(f.points_field("cmmi"), f.SIZE)

    def test_scrum_lacks_original_estimate(self):
        """The guard that stops a silent write failure on Scrum projects."""
        self.assertFalse(f.supports_original_estimate("scrum"))
        self.assertTrue(f.supports_original_estimate("agile"))
        self.assertTrue(f.supports_original_estimate("cmmi"))

    def test_cmmi_uses_discipline_not_activity(self):
        """CMMI names the activity field Discipline."""
        self.assertEqual(f.activity_field("cmmi"), f.DISCIPLINE)
        self.assertEqual(f.activity_field("agile"), f.ACTIVITY)

    def test_field_ref_builds_patch_path(self):
        """Writes address fields by JSON-Patch path."""
        self.assertEqual(
            f.field_ref(f.REMAINING_WORK),
            "/fields/Microsoft.VSTS.Scheduling.RemainingWork",
        )


class TestAzureMapping(unittest.TestCase):
    """Tests for pure Azure JSON translation."""

    def test_map_capacities_reads_members_and_activities(self):
        """Team members, their activities, and their leave all survive the mapping."""
        members = map_capacities(CAPACITIES_PAYLOAD)
        self.assertEqual(len(members), 2)
        self.assertEqual(members[0].display_name, "Chuck Reinhart")
        self.assertEqual(members[0].daily_hours, 8.0)
        self.assertEqual(len(members[0].days_off), 1)

    def test_map_capacities_accepts_bare_list(self):
        """Both the {count,value} envelope and a bare list are accepted."""
        self.assertEqual(len(map_capacities(CAPACITIES_PAYLOAD["value"])), 2)

    def test_map_capacities_tolerates_garbage(self):
        """Malformed payloads yield nothing instead of raising."""
        self.assertEqual(map_capacities(None), ())
        self.assertEqual(map_capacities("nonsense"), ())
        self.assertEqual(map_capacities({"value": ["not-an-object"]}), ())

    def test_map_days_off_single_day(self):
        """A one-day absence with no end date is still a valid range."""
        ranges = map_days_off([{"start": "2026-08-05T00:00:00Z"}])
        self.assertEqual(ranges[0].start, date(2026, 8, 5))
        self.assertEqual(ranges[0].end, date(2026, 8, 5))

    def test_map_weekend_days_is_complement_of_working_days(self):
        """Azure states which days are worked; the model wants the rest."""
        self.assertEqual(map_weekend_days(TEAM_SETTINGS_PAYLOAD), (5, 6))

    def test_map_weekend_days_absent_setting_keeps_default(self):
        """Absent settings report None, so map_iteration keeps its default weekend."""
        self.assertIsNone(map_weekend_days({}))
        self.assertIsNone(map_weekend_days({"workingDays": []}))
        self.assertIsNone(map_weekend_days(None))

    def test_map_weekend_days_six_day_week(self):
        """A team working Saturdays leaves only Sunday as weekend."""
        settings = {
            "workingDays": [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
            ]
        }
        self.assertEqual(map_weekend_days(settings), (6,))

    def test_map_iteration_assembles_dates_and_team(self):
        """The three payloads combine into one iteration."""
        iteration = map_iteration(
            "it1",
            iteration=ITERATION_PAYLOAD,
            capacities=CAPACITIES_PAYLOAD,
            team_settings=TEAM_SETTINGS_PAYLOAD,
        )
        self.assertEqual(iteration.start_date, date(2026, 8, 3))
        self.assertEqual(iteration.finish_date, date(2026, 8, 14))
        self.assertEqual(len(iteration.working_days()), 10)

    def test_map_iteration_without_payloads_degrades(self):
        """Nothing to map is not an error."""
        iteration = map_iteration("it1")
        self.assertEqual(iteration.members, ())
        self.assertIsNone(iteration.start_date)

    def test_map_work_item_reads_scheduling_fields(self):
        """Remaining work, activity, and assignee come through."""
        item = map_work_item(WORK_ITEMS_PAYLOAD["value"][0])
        self.assertEqual(item.item_id, "101")
        self.assertEqual(item.remaining_hours, 12.0)
        self.assertEqual(item.activity, "Development")
        self.assertEqual(item.assigned_to, "Chuck Reinhart")

    def test_map_work_item_reads_points(self):
        """Story points map to the generic points field."""
        self.assertEqual(map_work_item(WORK_ITEMS_PAYLOAD["value"][1]).points, 5.0)

    def test_map_work_item_finds_points_across_processes(self):
        """A Scrum project stores size under Effort, not StoryPoints."""
        payload = {"id": 7, "fields": {"Microsoft.VSTS.Scheduling.Effort": 8}}
        self.assertEqual(map_work_item(payload, process="scrum").points, 8.0)

    def test_map_work_item_without_id_is_dropped(self):
        """An item with no id cannot be addressed, so it is not returned."""
        self.assertIsNone(map_work_item({"fields": {"System.Title": "orphan"}}))
        self.assertIsNone(map_work_item("nonsense"))

    def test_map_work_items_filters_unmappable(self):
        """A mixed payload yields only the items that mapped."""
        payload = {"value": [{"id": 1}, {"no": "id"}]}
        self.assertEqual(len(map_work_items(payload)), 1)


class TestAzurePlanning(unittest.TestCase):
    """The Azure tracker's planning capability, driven by the replies a skill fetched."""

    REPLIES = {
        "iteration": ITERATION_PAYLOAD,
        "capacities": CAPACITIES_PAYLOAD,
        "team_settings": TEAM_SETTINGS_PAYLOAD,
        "work_items": WORK_ITEMS_PAYLOAD,
    }

    def _provider(self, process="agile"):
        return TrackerProvider(tracker(process), self.REPLIES)

    def test_fetch_iteration_from_the_replies(self):
        """The replies are all it needs; there is no credential and no network."""
        result = self._provider().fetch_iteration("it1")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.data.members), 2)

    def test_fetch_work_items_from_the_replies(self):
        result = self._provider().fetch_work_items("it1")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.data), 2)

    def test_end_to_end_plan_from_azure_replies(self):
        """Azure JSON in, capacity plan out.

        u1 gives 8h/day over 8 present days (two days off) and u2 gives 6h/day over 10,
        so availability is 64 + 60 = 124h.
        """
        provider = self._provider()
        iteration = provider.fetch_iteration("it1").data
        items = provider.fetch_work_items("it1").data
        plan = plan_iteration(iteration, items)
        self.assertEqual(plan.available_hours, 124.0)
        self.assertEqual(plan.planned_hours, 12.0)
        self.assertEqual(plan.items_estimated, 1)

    def test_hour_fields_target_remaining_work(self):
        """Remaining Work is the field capacity and burndown actually read."""
        self.assertIn(f.field_ref(f.REMAINING_WORK), tracker().hour_fields(6.0, False))

    def test_original_estimate_is_set_once_and_never_on_scrum(self):
        original = f.field_ref(f.ORIGINAL_ESTIMATE)
        self.assertIn(original, tracker("agile").hour_fields(4.0, True))
        self.assertNotIn(original, tracker("agile").hour_fields(4.0, False))
        self.assertNotIn(original, tracker("scrum").hour_fields(4.0, True))
        self.assertNotIn(original, tracker("agile").hour_fields(0.0, True))


class TestFilesystemProvider(unittest.TestCase):
    """Tests for the filesystem adapter."""

    def _artifacts(self, tmpdir, drafts, capacity=None):
        artifacts = Path(tmpdir)
        tickets = artifacts / "Tickets" / "Ready"
        tickets.mkdir(parents=True)
        for name, text in drafts.items():
            (tickets / name).write_text(text, encoding="utf-8")
        if capacity is not None:
            meta = artifacts
            meta.mkdir(exist_ok=True)
            (meta / "capacity-sprint-1.json").write_text(
                json.dumps(capacity), encoding="utf-8"
            )
        return artifacts

    def test_reads_points_and_hours_from_frontmatter(self):
        """Estimation data comes from the draft's own frontmatter."""
        draft = "---\nwork_item_type: User Story\nstory_points: 3\neffort_hours: 5\n---\n\n# Draft\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = self._artifacts(tmpdir, {"1234-a-draft.md": draft})
            result = FilesystemProvider(artifacts).fetch_work_items("")
            self.assertTrue(result.ok)
            self.assertEqual(result.data[0].points, 3.0)
            self.assertEqual(result.data[0].estimated_hours, 5.0)

    def test_filters_by_iteration_when_given(self):
        """A named iteration selects only the drafts that claim it."""
        in_sprint = "---\nstory_points: 2\niteration: sprint-1\n---\n\n# In\n"
        other = "---\nstory_points: 2\niteration: sprint-9\n---\n\n# Out\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = self._artifacts(
                tmpdir, {"1-in.md": in_sprint, "2-out.md": other}
            )
            self.assertEqual(
                len(FilesystemProvider(artifacts).fetch_work_items("sprint-1").data), 1
            )

    def test_empty_directory_warns_but_succeeds(self):
        """An empty directory is a warning, not a failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FilesystemProvider(Path(tmpdir)).fetch_work_items("")
            self.assertTrue(result.ok)
            self.assertEqual(result.data, [])
            self.assertTrue(result.warnings)

    def test_missing_capacity_file_warns_but_succeeds(self):
        """No capacity file yields an empty iteration plus an explanation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = FilesystemProvider(Path(tmpdir)).fetch_iteration("sprint-1")
            self.assertTrue(result.ok)
            self.assertEqual(result.data.members, ())
            self.assertTrue(any("no capacity file" in w for w in result.warnings))

    def test_reads_capacity_file(self):
        """A capacity file supplies dates and team members."""
        capacity = {
            "startDate": "2026-08-03",
            "finishDate": "2026-08-14",
            "members": [
                {
                    "id": "u1",
                    "name": "Ana",
                    "activities": [{"name": "Development", "capacityPerDay": 6}],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = self._artifacts(tmpdir, {}, capacity=capacity)
            iteration = FilesystemProvider(artifacts).fetch_iteration("sprint-1").data
            self.assertEqual(len(iteration.members), 1)
            self.assertEqual(iteration.members[0].daily_hours, 6.0)


if __name__ == "__main__":
    unittest.main()
