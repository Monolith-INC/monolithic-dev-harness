import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from orchestrator_core.capacity import plan_iteration
from orchestrator_core.ingest import ArtifactRecord
from orchestrator_core.providers import PROVIDERS, get_provider
from orchestrator_core.providers.azure_devops import AzureDevOpsProvider
from orchestrator_core.providers.azure_devops import fields as f
from orchestrator_core.providers.azure_devops.client import AzureCapacityClient
from orchestrator_core.providers.azure_devops.mapping import (
    map_capacities,
    map_days_off,
    map_iteration,
    map_weekend_days,
    map_work_item,
    map_work_items,
)
from orchestrator_core.providers.base import CapacityProvider, WorkItemWriter, WriteOp
from orchestrator_core.providers.filesystem import FilesystemProvider
from orchestrator_core.providers.linear import LinearProvider

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
            "daysOff": [{"start": "2026-08-05T00:00:00Z", "end": "2026-08-06T00:00:00Z"}],
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
    "attributes": {"startDate": "2026-08-03T00:00:00Z", "finishDate": "2026-08-14T00:00:00Z"},
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


class TestProviderRegistry(unittest.TestCase):
    """Tests for provider lookup."""

    def test_known_providers_registered(self):
        """Both shipped adapters are discoverable by name."""
        self.assertIn("azure-devops", PROVIDERS)
        self.assertIn("filesystem", PROVIDERS)
        self.assertIn("linear", PROVIDERS)

    def test_unknown_provider_returns_none(self):
        """An unknown name degrades to None rather than raising."""
        self.assertIsNone(get_provider("jira"))

    def test_get_filesystem_provider(self):
        """The filesystem provider is built with the configured artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = get_provider("filesystem", artifacts_dir=Path(tmpdir))
            self.assertIsInstance(provider, FilesystemProvider)

    def test_providers_satisfy_the_protocols(self):
        """Both adapters structurally match the seam they are meant to fill."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for provider in (FilesystemProvider(Path(tmpdir)), AzureDevOpsProvider()):
                self.assertIsInstance(provider, CapacityProvider)
                self.assertIsInstance(provider, WorkItemWriter)


class TestLinearWorkItemHierarchy(unittest.TestCase):
    def test_create_and_read_preserves_four_level_parent_chain_and_labels(self):
        provider = LinearProvider(team="team-1")
        chain = (
            ("Epic", "epic-1", None),
            ("Feature", "feature-1", "epic-1"),
            ("User Story", "story-1", "feature-1"),
            ("Task", "task-1", "story-1"),
        )
        for item_type, provider_id, parent_id in chain:
            with self.subTest(item_type=item_type):
                artifact = ArtifactRecord(
                    type=item_type,
                    title=f"{item_type} title",
                    body=f"{item_type} body",
                    story_points=None,
                    parent_id=parent_id,
                    provider="linear",
                    provider_id=None,
                    source="test",
                    filename=None,
                )
                create = provider.create_request(artifact)
                self.assertTrue(create.ok, create.error)
                self.assertEqual(create.data.payload["labels"], [f"agile:{item_type.lower().replace(' ', '-')}"])
                self.assertNotIn("project", create.data.payload, "Linear Projects are not Agile Epics")
                self.assertEqual(create.data.payload.get("parentId"), parent_id)

                read = provider.read_result(
                    {
                        "id": provider_id,
                        "title": artifact.title,
                        "description": artifact.body,
                        "labels": create.data.payload["labels"],
                        "parentId": parent_id,
                    }
                )
                self.assertTrue(read.ok, read.error)
                self.assertEqual(
                    (read.data.type, read.data.provider, read.data.provider_id, read.data.parent_id),
                    (item_type, "linear", provider_id, parent_id),
                )


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
        self.assertEqual(f.field_ref(f.REMAINING_WORK), "/fields/Microsoft.VSTS.Scheduling.RemainingWork")


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
        settings = {"workingDays": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]}
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


class TestAzureProvider(unittest.TestCase):
    """Tests for the Azure adapter, driven by injected payloads."""

    def _provider(self, process="Agile"):
        return AzureDevOpsProvider(
            process=process,
            payloads={
                "iteration": ITERATION_PAYLOAD,
                "capacities": CAPACITIES_PAYLOAD,
                "team_settings": TEAM_SETTINGS_PAYLOAD,
                "work_items": WORK_ITEMS_PAYLOAD,
            },
        )

    def test_fetch_iteration_from_injected_payloads(self):
        """Injection is the primary path and needs no credentials."""
        result = self._provider().fetch_iteration("it1")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.data.members), 2)

    def test_fetch_work_items_from_injected_payloads(self):
        """Work items map without any network access."""
        result = self._provider().fetch_work_items("it1")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.data), 2)

    def test_end_to_end_plan_from_azure_payloads(self):
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

    def test_no_payloads_and_no_client_fails_cleanly(self):
        """A provider with no way to read reports why instead of raising."""
        result = AzureDevOpsProvider().fetch_iteration("it1")
        self.assertFalse(result.ok)
        self.assertIn("no payloads injected", result.error)

    def test_plan_hour_write_targets_remaining_work(self):
        """Remaining Work is the field capacity and burndown actually read."""
        ops = self._provider().plan_hour_write("101", 6.0)
        paths = [op.field_path for op in ops]
        self.assertIn(f.field_ref(f.REMAINING_WORK), paths)

    def test_plan_hour_write_omits_original_estimate_on_scrum(self):
        """The Scrum guard, at the level that matters."""
        agile = AzureDevOpsProvider(process="Agile").plan_hour_write("1", 4.0)
        scrum = AzureDevOpsProvider(process="Scrum").plan_hour_write("1", 4.0)
        self.assertIn(f.field_ref(f.ORIGINAL_ESTIMATE), [o.field_path for o in agile])
        self.assertNotIn(f.field_ref(f.ORIGINAL_ESTIMATE), [o.field_path for o in scrum])

    def test_plan_hour_write_includes_activity_when_given(self):
        """Activity is written only when the caller could determine one."""
        with_activity = self._provider().plan_hour_write("1", 4.0, activity="Development")
        without = self._provider().plan_hour_write("1", 4.0)
        self.assertIn(f.field_ref(f.ACTIVITY), [o.field_path for o in with_activity])
        self.assertNotIn(f.field_ref(f.ACTIVITY), [o.field_path for o in without])

    def test_writes_are_planned_not_performed(self):
        """Every planned write demands confirmation before anything happens."""
        for op in self._provider().plan_hour_write("1", 4.0, provenance="seed-default"):
            self.assertIsInstance(op, WriteOp)
            self.assertTrue(op.requires_confirmation)
            self.assertIn("seed-default", op.describe())


class TestAzureClientConfiguration(unittest.TestCase):
    """Tests for the optional direct client. No network is touched."""

    def test_client_without_pat_is_not_configured(self):
        """Missing credentials are detected before any request is attempted."""
        client = AzureCapacityClient("org", "proj", pat=None)
        if client.pat is None:  # a real PAT in the environment would defeat this
            self.assertFalse(client.configured)

    def test_unconfigured_client_returns_error_not_exception(self):
        """A misconfigured client reports the problem, following never-raise."""
        client = AzureCapacityClient("", "", pat=None)
        data, error = client.get_capacities("it1")
        self.assertIsNone(data)
        self.assertIn("not configured", error)

    def test_scope_includes_team_when_given(self):
        """Capacity endpoints are team-scoped when a team is supplied."""
        self.assertNotIn("/myteam", AzureCapacityClient("org", "proj", pat="x")._scope())
        self.assertIn("/myteam", AzureCapacityClient("org", "proj", team="myteam", pat="x")._scope())


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
            (meta / "capacity-sprint-1.json").write_text(json.dumps(capacity), encoding="utf-8")
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
            artifacts = self._artifacts(tmpdir, {"1-in.md": in_sprint, "2-out.md": other})
            self.assertEqual(len(FilesystemProvider(artifacts).fetch_work_items("sprint-1").data), 1)

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
            "members": [{"id": "u1", "name": "Ana", "activities": [{"name": "Development", "capacityPerDay": 6}]}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts = self._artifacts(tmpdir, {}, capacity=capacity)
            iteration = FilesystemProvider(artifacts).fetch_iteration("sprint-1").data
            self.assertEqual(len(iteration.members), 1)
            self.assertEqual(iteration.members[0].daily_hours, 6.0)

    def test_plan_hour_write_targets_frontmatter(self):
        """The filesystem adapter writes to frontmatter keys, not Azure fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ops = FilesystemProvider(Path(tmpdir)).plan_hour_write("1", 4.0, activity="Development")
            self.assertEqual(ops[0].field_path, "frontmatter.effort_hours")
            self.assertEqual(ops[1].field_path, "frontmatter.activity")


if __name__ == "__main__":
    unittest.main()
