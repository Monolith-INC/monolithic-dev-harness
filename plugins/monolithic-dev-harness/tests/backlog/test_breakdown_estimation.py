import unittest
from datetime import date

from azure_tracker import (
    ORIGINAL_ESTIMATE,
    REMAINING_WORK,
    reading,
    refused,
    select_azure,
    sprint,
)

from orchestrator_core.capacity import (
    ActivityCapacity,
    DateRange,
    EstimableItem,
    IterationCapacity,
    MemberCapacity,
    availability_for,
    find_member,
)
from orchestrator_core.estimation import (
    EstimationConfig,
    TaskInput,
    estimate_breakdown,
    recompute_breakdown,
)
from tests.settings_fixture import write_settings


def _sprint(members=()):
    """Mon 3 Aug 2026 to Fri 14 Aug 2026 -- ten working days."""
    return IterationCapacity(
        iteration_ref="Sprint 42",
        start_date=date(2026, 8, 3),
        finish_date=date(2026, 8, 14),
        members=tuple(members),
    )


def _member(member_id="u1", name="Ana Silva", per_day=6.0, days_off=()):
    return MemberCapacity(
        member_id=member_id,
        display_name=name,
        activities=(ActivityCapacity("", per_day),),
        days_off=tuple(days_off),
    )


def _tasks(n=3, current=None):
    return [
        TaskInput(f"t{i}", f"Task {i}", current_hours=current) for i in range(1, n + 1)
    ]


class TestFindMember(unittest.TestCase):
    """Matching a work-item assignee to a capacity entry."""

    def test_matches_on_display_name(self):
        """Azure usually gives the assignee as a display name."""
        sprint = _sprint([_member(name="Ana Silva")])
        self.assertIsNotNone(find_member(sprint, "Ana Silva"))

    def test_matches_on_member_id(self):
        """Capacity data identifies people by id."""
        self.assertIsNotNone(find_member(_sprint([_member(member_id="u1")]), "u1"))

    def test_match_is_case_insensitive(self):
        """Case differences between payloads must not lose a person."""
        self.assertIsNotNone(
            find_member(_sprint([_member(name="Ana Silva")]), "ana silva")
        )

    def test_matches_email_local_part(self):
        """A unique name like ana@corp.com resolves to the member called ana."""
        sprint = _sprint([_member(name="ana")])
        self.assertIsNotNone(find_member(sprint, "ana@corp.com"))

    def test_unmatched_assignee_returns_none_not_a_guess(self):
        """An unknown assignee must be reported, never silently attributed."""
        self.assertIsNone(find_member(_sprint([_member(name="Ana")]), "Someone Else"))
        self.assertIsNone(find_member(_sprint([_member()]), None))
        self.assertIsNone(find_member(_sprint([_member()]), "  "))


class TestAvailability(unittest.TestCase):
    """One person's hours in one sprint."""

    def test_available_hours_for_a_full_sprint(self):
        """Daily capacity times working days."""
        availability = availability_for(_sprint([_member(per_day=6.0)]), "Ana Silva")
        self.assertEqual(availability.available_hours, 60.0)
        self.assertEqual(availability.working_days, 10)
        self.assertEqual(availability.days_off, 0)

    def test_personal_days_off_reduce_only_that_person(self):
        """Leave comes off the individual's hours, not the team's."""
        away = _member(
            per_day=5.0, days_off=[DateRange(date(2026, 8, 5), date(2026, 8, 6))]
        )
        availability = availability_for(_sprint([away]), "Ana Silva")
        self.assertEqual(availability.working_days, 8)
        self.assertEqual(availability.days_off, 2)
        self.assertEqual(availability.available_hours, 40.0)

    def test_existing_commitments_reduce_what_is_left(self):
        """A second Story is checked against what remains, not the full sprint."""
        items = [
            EstimableItem(item_id="1", remaining_hours=20.0, assigned_to="Ana Silva"),
            EstimableItem(
                item_id="2", remaining_hours=99.0, assigned_to="Someone Else"
            ),
        ]
        availability = availability_for(
            _sprint([_member(per_day=6.0)]), "Ana Silva", items=items
        )
        self.assertEqual(availability.committed_hours, 20.0)
        self.assertEqual(availability.remaining_hours, 40.0)

    def test_unmatched_assignee_yields_no_availability(self):
        """Without a match there is no capacity figure, and callers must say so."""
        self.assertIsNone(availability_for(_sprint([_member()]), "Nobody"))


class TestEstimateBreakdown(unittest.TestCase):
    """Deriving hours for every Task under one Story."""

    def test_hours_are_split_across_tasks_and_sum_to_the_whole(self):
        """Rounding must never lose or invent time."""
        estimate = estimate_breakdown("US-1", 3.0, _tasks(3), config=EstimationConfig())
        self.assertEqual(len(estimate.tasks), 3)
        self.assertEqual(
            round(sum(t.hours for t in estimate.tasks), 2), estimate.total_hours
        )
        self.assertEqual(
            estimate.total_hours, 5.0
        )  # midpoint of the 4-6h band for 3 points

    def test_weights_shift_the_split(self):
        """A Task known to be larger takes a larger share."""
        tasks = [TaskInput("a", "A", weight=1.0), TaskInput("b", "B", weight=3.0)]
        estimate = estimate_breakdown("US-1", 3.0, tasks)
        hours = {t.task_id: t.hours for t in estimate.tasks}
        self.assertLess(hours["a"], hours["b"])
        self.assertEqual(round(hours["a"] + hours["b"], 2), estimate.total_hours)

    def test_no_points_yields_no_estimate(self):
        """An unestimated Story produces nothing, never a fabricated figure."""
        self.assertIsNone(estimate_breakdown("US-1", None, _tasks()))
        self.assertIsNone(estimate_breakdown("US-1", 0, _tasks()))

    def test_no_tasks_yields_no_estimate(self):
        """Nothing to split hours across."""
        self.assertIsNone(estimate_breakdown("US-1", 3.0, []))

    def test_seed_provenance_is_surfaced_as_a_warning(self):
        """An uncalibrated figure must announce itself."""
        estimate = estimate_breakdown("US-1", 3.0, _tasks())
        self.assertEqual(estimate.provenance, "seed-default")
        self.assertTrue(any("seed-default" in w for w in estimate.warnings))

    def test_missing_capacity_is_warned_not_assumed(self):
        """Without an availability figure the estimate says it was not checked."""
        estimate = estimate_breakdown("US-1", 3.0, _tasks())
        self.assertFalse(estimate.capacity_known)
        self.assertTrue(any("capacity not checked" in w for w in estimate.warnings))
        self.assertFalse(estimate.blocked)


class TestCapacityConstraint(unittest.TestCase):
    """Capacity is a ceiling: work that cannot fit stops rather than being written."""

    def _availability(self, per_day=6.0):
        return availability_for(_sprint([_member(per_day=per_day)]), "Ana Silva")

    def test_fits_within_capacity(self):
        """A Story inside the assignee's hours is not blocked."""
        estimate = estimate_breakdown(
            "US-1", 3.0, _tasks(), availability=self._availability()
        )
        self.assertFalse(estimate.blocked)
        self.assertEqual(estimate.overflow_hours, 0.0)
        self.assertEqual(estimate.resolution_options(), ())

    def test_exceeding_capacity_blocks_with_the_overflow_named(self):
        """60h available, 21 points deriving 120h -> blocked by 60h."""
        estimate = estimate_breakdown(
            "US-1", 21.0, _tasks(), availability=self._availability()
        )
        self.assertTrue(estimate.blocked)
        self.assertEqual(estimate.overflow_hours, round(estimate.total_hours - 60.0, 2))
        self.assertIn("BLOCKED", estimate.describe())

    def test_blocked_estimate_offers_choices_and_decides_nothing(self):
        """The plugin names the options; a person picks."""
        estimate = estimate_breakdown(
            "US-1", 21.0, _tasks(), availability=self._availability()
        )
        options = estimate.resolution_options()
        self.assertTrue(any("split" in o for o in options))
        self.assertTrue(any("reassign" in o for o in options))
        self.assertTrue(any("later sprint" in o for o in options))

    def test_existing_commitments_count_against_the_ceiling(self):
        """A Story that would fit an empty sprint can still overflow a busy one."""
        items = [
            EstimableItem(item_id="x", remaining_hours=58.0, assigned_to="Ana Silva")
        ]
        availability = availability_for(
            _sprint([_member(per_day=6.0)]), "Ana Silva", items=items
        )
        estimate = estimate_breakdown("US-1", 3.0, _tasks(), availability=availability)
        self.assertEqual(availability.remaining_hours, 2.0)
        self.assertTrue(estimate.blocked)

    def test_unknown_capacity_never_blocks(self):
        """An unmatched assignee is a warning, not a stop -- absence of data is not a failure."""
        estimate = estimate_breakdown("US-1", 21.0, _tasks(), availability=None)
        self.assertFalse(estimate.blocked)


class TestRecompute(unittest.TestCase):
    """Recomputed hours are applied automatically and always reported."""

    def test_changed_tasks_are_identified(self):
        """A change in the breakdown surfaces as a per-Task delta."""
        before = estimate_breakdown("US-1", 3.0, _tasks(3))
        after = estimate_breakdown("US-1", 8.0, _tasks(3))
        changes = recompute_breakdown(before, after)
        self.assertEqual(len(changes), 3)
        for change in changes:
            self.assertTrue(change.changed)
            self.assertIsNotNone(change.previous_hours)

    def test_unchanged_tasks_are_not_reported(self):
        """Recomputing the same inputs reports nothing."""
        before = estimate_breakdown("US-1", 3.0, _tasks(3))
        after = estimate_breakdown("US-1", 3.0, _tasks(3))
        self.assertEqual(recompute_breakdown(before, after), ())

    def test_added_task_is_reported_as_new(self):
        """A Task that did not exist before has no previous figure."""
        before = estimate_breakdown("US-1", 3.0, _tasks(2))
        after = estimate_breakdown("US-1", 3.0, _tasks(3))
        new = [c for c in recompute_breakdown(before, after) if c.is_new]
        self.assertTrue(new)

    def test_first_run_reports_every_task(self):
        """With nothing to compare against, all estimates are new."""
        after = estimate_breakdown("US-1", 3.0, _tasks(3))
        self.assertEqual(len(recompute_breakdown(None, after)), 3)

    def test_no_current_estimate_reports_nothing(self):
        """Nothing to say when there is no new estimate."""
        self.assertEqual(
            recompute_breakdown(estimate_breakdown("US-1", 3.0, _tasks()), None), ()
        )

    def test_report_names_every_change(self):
        """The user is told what moved, since nothing asked their permission."""
        estimate = estimate_breakdown(
            "US-1", 3.0, [TaskInput("t1", "Wire it", current_hours=2.0)]
        )
        report = estimate.describe()
        self.assertIn("Wire it", report)
        self.assertIn("2h", report)
        self.assertIn("estimate(s) changed and were updated", report)

    def test_task_change_description_shows_both_figures(self):
        """Old and new appear together so a reader can judge the move."""
        estimate = estimate_breakdown(
            "US-1", 8.0, [TaskInput("t1", "Wire it", current_hours=2.0)]
        )
        self.assertIn("2h → 32h", estimate.tasks[0].describe_change())


def _listed(name, time_frame=None, start="2026-08-03"):
    attributes = {
        "startDate": start,
        **({} if time_frame is None else {"timeFrame": time_frame}),
    }
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "attributes": attributes,
    }


LISTING = {
    "value": [
        _listed("Sprint 58", 0, "2026-07-20"),
        _listed("Sprint 59", 1, "2026-08-03"),
        _listed("Sprint 60", 2, "2026-08-17"),
    ]
}


class TestSprintSelection(unittest.TestCase):
    """Which sprint an iteration listing gives, so nobody has to pass an id."""

    def _start(self, listing, ref="current"):
        return sprint(ref, iteration=listing).start_date

    def test_current_takes_the_sprint_marked_current(self):
        """Azure marks the active sprint with timeFrame 1."""
        self.assertEqual(str(self._start(LISTING)), "2026-08-03")

    def test_a_named_sprint_is_found_by_name_id_or_path(self):
        """Asking for another sprint must not quietly give the current one's dates."""
        self.assertEqual(str(self._start(LISTING, "Sprint 60")), "2026-08-17")
        self.assertEqual(str(self._start(LISTING, "sprint-58")), "2026-07-20")

    def test_a_named_sprint_missing_from_the_listing_is_reported(self):
        found = reading("Sprint 99", iteration=LISTING)
        self.assertIsNone(found.capacity.start_date)
        self.assertTrue(any("Sprint 99" in warning for warning in found.warnings))

    def test_single_unmarked_entry_is_taken_as_current(self):
        """A timeframe=current query returns only the active sprint."""
        listing = {"value": [_listed("Sprint 59", start="2026-08-03")]}
        self.assertEqual(str(self._start(listing)), "2026-08-03")

    def test_one_sprint_object_is_the_sprint_asked_for(self):
        self.assertEqual(
            str(self._start(_listed("Sprint 60", 2, "2026-08-17"), "it")), "2026-08-17"
        )

    def test_no_current_sprint_gives_no_dates_and_says_so(self):
        """Between sprints there may be no active one."""
        listing = {"value": [_listed("Sprint 58", 0), _listed("Sprint 60", 2)]}
        found = reading("current", iteration=listing)
        self.assertIsNone(found.capacity.start_date)
        self.assertTrue(
            any("no current sprint" in warning for warning in found.warnings)
        )

    def test_listings_without_a_sprint_give_no_dates(self):
        for payload in ({"value": []}, [None]):
            self.assertIsNone(self._start(payload))

    def test_a_reply_that_holds_no_sprint_is_refused(self):
        for payload in (None, {}, "text"):
            self.assertEqual(refused("current", iteration=payload), "unreadable_reply")


if __name__ == "__main__":
    unittest.main()


class TestRoleWeights(unittest.TestCase):
    """The three default Tasks are not the same size as the work they bracket."""

    def test_roles_are_classified_from_titles(self):
        """Staging, Review and Breakdown are recognised; anything else is work."""
        from orchestrator_core.estimation import task_role

        self.assertEqual(task_role("Staging"), "staging")
        self.assertEqual(task_role("Review"), "review")
        self.assertEqual(task_role("Breakdown"), "breakdown")
        self.assertEqual(task_role("Wire the login form"), "implementation")

    def test_role_matching_is_case_and_locale_tolerant(self):
        """Titles may be localised or suffixed and must still be recognised."""
        from orchestrator_core.estimation import task_role

        self.assertEqual(task_role("REVIEW"), "review")
        self.assertEqual(task_role("Revisão"), "review")
        self.assertEqual(task_role("Review: acceptance criteria"), "review")

    def test_a_title_merely_containing_a_keyword_is_still_work(self):
        """'Review queue endpoint' is implementation, not the Review marker."""
        from orchestrator_core.estimation import task_role

        self.assertEqual(task_role("Build the review queue endpoint"), "implementation")

    def test_breakdown_marker_carries_no_hours(self):
        """It signals completion; giving it time would take time from real work."""
        tasks = [TaskInput("1", "Wire it"), TaskInput("2", "Breakdown")]
        estimate = estimate_breakdown("US-1", 3.0, tasks)
        hours = {t.title: t.hours for t in estimate.tasks}
        self.assertEqual(hours["Breakdown"], 0.0)
        self.assertEqual(hours["Wire it"], estimate.total_hours)

    def test_staging_and_review_are_lighter_than_implementation(self):
        """Bracketing tasks take a smaller share than the work itself."""
        tasks = [
            TaskInput("1", "Wire it"),
            TaskInput("2", "Staging"),
            TaskInput("3", "Review"),
        ]
        estimate = estimate_breakdown("US-1", 5.0, tasks)
        hours = {t.title: t.hours for t in estimate.tasks}
        self.assertGreater(hours["Wire it"], hours["Staging"])
        self.assertEqual(hours["Staging"], hours["Review"])

    def test_explicit_weight_overrides_the_role_default(self):
        """A caller that read the plan knows better than the title does."""
        tasks = [
            TaskInput("1", "Breakdown", weight=2.0),
            TaskInput("2", "Wire it", weight=1.0),
        ]
        estimate = estimate_breakdown("US-1", 3.0, tasks)
        hours = {t.title: t.hours for t in estimate.tasks}
        self.assertGreater(hours["Breakdown"], hours["Wire it"])

    def test_total_is_preserved_despite_zero_weights(self):
        """The parts still sum to the whole when one task is weighted out."""
        tasks = [
            TaskInput(str(i), t) for i, t in enumerate(["A", "B", "C", "Breakdown"])
        ]
        estimate = estimate_breakdown("US-1", 8.0, tasks)
        self.assertEqual(
            round(sum(t.hours for t in estimate.tasks), 2), estimate.total_hours
        )

    def test_rounding_drift_never_lands_on_a_zero_weight_task(self):
        """The regression: drift used to go to the last entry, which is Breakdown."""
        from orchestrator_core.estimation import distribute_hours

        parts = distribute_hours(10.0, [1, 1, 1, 0])
        self.assertEqual(parts[-1], 0.0)
        self.assertEqual(round(sum(parts), 2), 10.0)


class TestEstimateBreakdownHandler(unittest.TestCase):
    """The orchestrator handler -- deterministic, and it performs no writes."""

    def _run(self, arguments, setup=select_azure):
        """Runs in a fresh repository prepared by `setup` (Azure DevOps, agile, by default)."""
        import tempfile
        from pathlib import Path as P

        from orchestrator_core.handlers import handle_estimate_breakdown

        with tempfile.TemporaryDirectory() as tmpdir:
            root = P(tmpdir)
            setup(root)
            state = root / ".harness" / "backlog"
            state.mkdir(parents=True)
            return handle_estimate_breakdown(
                arguments, skills_dir=P("."), state_dir=state, instructions=""
            )

    SPRINT = {
        "iteration": {
            "attributes": {"startDate": "2026-08-03", "finishDate": "2026-08-14"}
        },
        "team_settings": {"workingDays": [1, 2, 3, 4, 5]},
        "capacities": {
            "teamMembers": [
                {
                    "teamMember": {"id": "u1", "displayName": "Ana"},
                    "activities": [{"capacityPerDay": 1, "name": ""}],
                }
            ]
        },
    }

    def test_a_missing_reply_stops_the_run_instead_of_skipping_the_ceiling(self):
        """The regression: without work_items the check used to switch off and the hours were
        written past the assignee's capacity."""
        result = self._run(
            dict(self.BASE, story_points=21, assignee="Ana", replies=self.SPRINT)
        )
        self.assertFalse(result["ok"])
        self.assertIn("work_items", result["error"])
        self.assertIn("get_batch", result["error"])

    def test_an_ids_only_work_items_reply_stops_the_run(self):
        """The round-two regression: the adapter refused the reply, and the handler then counted
        the assignee's existing work as none and wrote the hours."""
        replies = dict(
            self.SPRINT, work_items={"workItemRelations": [{"target": {"id": 9}}]}
        )
        result = self._run(dict(self.BASE, assignee="Ana", replies=replies))
        self.assertFalse(result["ok"])
        self.assertIn("get_batch", result["error"])

    def test_a_reply_that_holds_no_data_stops_the_run(self):
        """An error text in place of the capacities is not "no team capacity"."""
        replies = dict(self.SPRINT, capacities="Error: 401", work_items=[])
        result = self._run(dict(self.BASE, assignee="Ana", replies=replies))
        self.assertFalse(result["ok"])
        self.assertIn("capacities", result["error"])

    def test_the_command_line_prints_every_note(self):
        """What the check found reaches the person running the command, and an empty write list
        is not announced."""
        import contextlib
        import io
        import json
        import os
        import tempfile
        from pathlib import Path as P
        from unittest import mock

        from orchestrator_core.main import main

        with tempfile.TemporaryDirectory() as tmpdir:
            root = P(tmpdir)
            write_settings(root, tracker={"name": "linear", "values": {"team": "ENG"}})
            (root / "in.json").write_text(json.dumps(dict(self.BASE, assignee="Ana")))
            (root / "replies.json").write_text('{"cycle": [], "issues": []}')
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": tmpdir}):
                with contextlib.redirect_stdout(out):
                    code = main(
                        [
                            "estimate-breakdown",
                            "--input",
                            str(root / "in.json"),
                            "--replies",
                            str(root / "replies.json"),
                        ]
                    )
        self.assertEqual(code, 0)
        self.assertIn("record these hours by hand", out.getvalue())
        self.assertIn("records no team capacity", out.getvalue())
        self.assertNotIn("Write these to the tracker", out.getvalue())

    def test_capacity_is_not_checked_unless_asked(self):
        """No replies and no sprint named: the estimate stands, with no invented warnings."""
        result = self._run(dict(self.BASE, assignee="Ana"))
        self.assertTrue(result["ok"])
        self.assertEqual(result["capacity_errors"], [])
        self.assertFalse(result["capacity_known"])

    def test_the_local_tracker_writes_its_own_hour_fields(self):
        result = self._run(
            dict(self.BASE, assignee="Ana"),
            write_settings,
        )
        fields = {name for op in result["write_ops"] for name in op["fields"]}
        self.assertEqual(fields, {"remaining_hours", "effort_hours"})
        self.assertEqual(result["capacity_errors"], [])

    def test_the_local_tracker_checks_capacity_for_a_named_sprint(self):
        def sprint_file(root):
            folder = root / ".harness" / "tracker" / "capacity"
            folder.mkdir(parents=True)
            (folder / "S1.json").write_text(
                '{"startDate": "2026-08-03", "finishDate": "2026-08-14", '
                '"members": [{"name": "Ana", "activities": [{"capacityPerDay": 1}]}]}'
            )

        result = self._run(
            dict(self.BASE, story_points=21, assignee="Ana", iteration_ref="S1"),
            lambda root: (write_settings(root), sprint_file(root)),
        )
        self.assertTrue(result["blocked"])
        self.assertEqual(result["write_ops"], [])

    def test_linear_says_it_has_no_capacity_rather_than_blaming_the_assignee(self):
        result = self._run(
            dict(self.BASE, assignee="Ana", replies={"cycle": [], "issues": []}),
            lambda root: write_settings(
                root, tracker={"name": "linear", "values": {"team": "ENG"}}
            ),
        )
        self.assertEqual(
            result["capacity_errors"],
            ["the sprint records no team capacity, so it was not checked"],
        )
        self.assertEqual(result["write_ops"], [])
        self.assertTrue(any("by hand" in w for w in result["warnings"]))

    def test_no_usable_tracker_means_no_writes_and_says_why(self):
        """Nobody gets a field the tracker does not have, not even a neutral one."""
        result = self._run(dict(self.BASE), lambda root: None)
        self.assertTrue(result["estimated"])
        self.assertEqual(result["write_ops"], [])
        self.assertTrue(any("by hand" in w for w in result["warnings"]))

    BASE = {
        "story_id": "US-1",
        "story_points": 5,
        "tasks": [
            {"id": "101", "title": "Wire it"},
            {"id": "102", "title": "Breakdown"},
        ],
    }

    def test_handler_is_registered(self):
        """It joins the existing registry rather than hijacking a skill name."""
        from orchestrator_core.handlers import HANDLERS

        self.assertIn("estimate-breakdown", HANDLERS)
        self.assertNotIn("generate-breakdown-work-items", HANDLERS)

    def test_produces_write_ops_for_tasks_with_hours(self):
        """Remaining Work is the field that makes a Task visible to the sprint."""
        result = self._run(dict(self.BASE))
        self.assertTrue(result["ok"])
        self.assertTrue(result["estimated"])
        paths = {f for op in result["write_ops"] for f in op["fields"]}
        self.assertIn(REMAINING_WORK, paths)

    def test_new_zero_hour_task_is_not_written(self):
        """A Breakdown marker that never had hours needs no write."""
        base = dict(self.BASE)
        base["tasks"] = [
            {"id": "101", "title": "Wire it"},
            {"id": "102", "title": "Breakdown"},
        ]
        result = self._run(base)
        self.assertNotIn("102", {op["item_id"] for op in result["write_ops"]})

    def test_task_dropping_to_zero_is_written(self):
        """Clearing stale hours is the whole point: leaving 6h on a marker misleads the burndown."""
        base = dict(self.BASE)
        base["tasks"] = [
            {"id": "101", "title": "Wire it"},
            {"id": "102", "title": "Breakdown", "current_hours": 6.0},
        ]
        result = self._run(base)
        ops = {op["item_id"]: op["fields"] for op in result["write_ops"]}
        self.assertIn("102", ops)
        self.assertEqual(ops["102"][REMAINING_WORK], 0.0)

    def test_original_estimate_omitted_on_scrum(self):
        """The process guard applies to the handler's write ops too."""
        scrum = self._run(dict(self.BASE), lambda root: select_azure(root, "scrum"))
        agile = self._run(dict(self.BASE), lambda root: select_azure(root, "agile"))
        scrum_paths = {f for op in scrum["write_ops"] for f in op["fields"]}
        agile_paths = {f for op in agile["write_ops"] for f in op["fields"]}
        self.assertNotIn(ORIGINAL_ESTIMATE, scrum_paths)
        self.assertIn(ORIGINAL_ESTIMATE, agile_paths)

    def test_blocked_estimate_produces_no_write_ops(self):
        """Work that cannot fit is never written."""
        replies = {
            "iteration": {
                "attributes": {"startDate": "2026-08-03", "finishDate": "2026-08-14"}
            },
            "team_settings": {"workingDays": [1, 2, 3, 4, 5]},
            "capacities": {
                "teamMembers": [
                    {
                        "teamMember": {"id": "u1", "displayName": "Ana"},
                        "activities": [{"capacityPerDay": 1, "name": ""}],
                        "daysOff": [],
                    }
                ]
            },
            "work_items": {"value": []},
        }
        result = self._run(
            dict(self.BASE, story_points=21, assignee="Ana", replies=replies)
        )
        self.assertTrue(result["blocked"])
        self.assertEqual(result["write_ops"], [])
        self.assertTrue(result["resolution_options"])

    def test_capacity_cross_check_warning_reaches_the_handler(self):
        """A mismatch with Azure's reported total must not disappear at the provider seam."""
        replies = {
            "iteration": {
                "attributes": {"startDate": "2026-08-03", "finishDate": "2026-08-14"}
            },
            "team_settings": {"workingDays": [1, 2, 3, 4, 5]},
            "capacities": {
                "teamMembers": [
                    {
                        "teamMember": {"id": "u1", "displayName": "Ana"},
                        "activities": [{"capacityPerDay": 6, "name": ""}],
                    }
                ],
                "totalCapacityPerDay": 8,
            },
            "work_items": {"value": []},
        }
        result = self._run(dict(self.BASE, assignee="Ana", replies=replies))
        self.assertTrue(
            any("capacity mismatch" in warning for warning in result["warnings"])
        )

    def test_missing_inputs_error_cleanly(self):
        """Bad arguments are an error message, not an exception."""
        self.assertFalse(self._run({"tasks": [{"id": "1"}]})["ok"])
        self.assertFalse(self._run({"story_id": "US-1"})["ok"])
        self.assertFalse(self._run({"story_id": "US-1", "tasks": []})["ok"])

    def test_unestimatable_story_is_reported_not_invented(self):
        """No points means no estimate, and the handler says why."""
        result = self._run(dict(self.BASE, story_points=None))
        self.assertTrue(result["ok"])
        self.assertFalse(result["estimated"])
        self.assertIn("honest state", result["reason"])

    def test_same_inputs_give_the_same_hours(self):
        """Deterministic: this is the point of computing rather than reasoning."""
        first = self._run(dict(self.BASE))
        second = self._run(dict(self.BASE))
        self.assertEqual(
            [t["hours"] for t in first["tasks"]], [t["hours"] for t in second["tasks"]]
        )

    def test_changes_are_always_reported(self):
        """Nothing asked permission, so every moved figure must be named."""
        tasks = [{"id": "101", "title": "Wire it", "current_hours": 2.0}]
        result = self._run(dict(self.BASE, tasks=tasks))
        self.assertTrue(result["changes"])
        self.assertIn("2h", result["changes"][0])
