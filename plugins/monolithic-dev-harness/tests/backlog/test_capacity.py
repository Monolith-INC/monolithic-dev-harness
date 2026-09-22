import unittest
from datetime import date

from orchestrator_core.capacity import (
    ActivityCapacity,
    DateRange,
    EstimableItem,
    IterationCapacity,
    MemberCapacity,
    available_by_activity,
    available_hours,
    format_plan,
    parse_date,
    plan_iteration,
    planned_by_activity,
)
from orchestrator_core.capacity.planner import UNASSIGNED_ACTIVITY


def _sprint(members=(), team_days_off=()):
    """Two-week sprint, Mon 3 Aug 2026 to Fri 14 Aug 2026 -- ten working days."""
    return IterationCapacity(
        iteration_ref="sprint-42",
        start_date=date(2026, 8, 3),
        finish_date=date(2026, 8, 14),
        members=tuple(members),
        team_days_off=tuple(team_days_off),
    )


def _member(member_id="u1", per_day=6.0, activity="Development", days_off=()):
    return MemberCapacity(
        member_id=member_id,
        display_name=member_id,
        activities=(ActivityCapacity(name=activity, capacity_per_day=per_day),),
        days_off=tuple(days_off),
    )


class TestParseDate(unittest.TestCase):
    """Tests for lenient date parsing."""

    def test_parses_iso_date_and_datetime(self):
        """Both a bare date and a full timestamp resolve to the same day."""
        self.assertEqual(parse_date("2026-08-03"), date(2026, 8, 3))
        self.assertEqual(parse_date("2026-08-03T00:00:00Z"), date(2026, 8, 3))

    def test_bad_input_returns_none(self):
        """Unparseable input degrades to None rather than raising."""
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date("not-a-date"))


class TestDateRange(unittest.TestCase):
    """Tests for the inclusive day span."""

    def test_days_are_inclusive(self):
        """A range covering Monday to Friday is five days, not four."""
        self.assertEqual(len(DateRange(date(2026, 8, 3), date(2026, 8, 7)).days()), 5)

    def test_inverted_range_is_empty(self):
        """An end before its start yields no days rather than an error."""
        self.assertEqual(DateRange(date(2026, 8, 7), date(2026, 8, 3)).days(), [])

    def test_contains(self):
        """Boundaries are inside the range."""
        span = DateRange(date(2026, 8, 3), date(2026, 8, 7))
        self.assertTrue(span.contains(date(2026, 8, 3)))
        self.assertTrue(span.contains(date(2026, 8, 7)))
        self.assertFalse(span.contains(date(2026, 8, 8)))


class TestWorkingDays(unittest.TestCase):
    """Tests for working-day arithmetic."""

    def test_weekends_are_excluded(self):
        """A two-week sprint has ten working days, not fourteen."""
        self.assertEqual(len(_sprint().working_days()), 10)

    def test_team_days_off_are_excluded(self):
        """A team-wide holiday removes a day for everyone."""
        sprint = _sprint(team_days_off=[DateRange(date(2026, 8, 5), date(2026, 8, 5))])
        self.assertEqual(len(sprint.working_days()), 9)

    def test_personal_days_off_reduce_only_that_member(self):
        """One person's leave does not shorten anyone else's sprint."""
        away = _member("u1", days_off=[DateRange(date(2026, 8, 5), date(2026, 8, 6))])
        present = _member("u2")
        sprint = _sprint([away, present])
        self.assertEqual(len(sprint.working_days_for(away)), 8)
        self.assertEqual(len(sprint.working_days_for(present)), 10)

    def test_missing_dates_yield_no_working_days(self):
        """An iteration with no dates cannot have working days."""
        self.assertEqual(IterationCapacity(iteration_ref="x").working_days(), [])


class TestAvailableHours(unittest.TestCase):
    """Tests for capacity totals."""

    def test_sums_daily_capacity_over_present_days(self):
        """Availability is capacity per day times days actually present."""
        self.assertEqual(available_hours(_sprint([_member(per_day=6.0)])), 60.0)

    def test_days_off_reduce_availability(self):
        """Two days of leave remove two days of capacity."""
        away = _member(per_day=6.0, days_off=[DateRange(date(2026, 8, 5), date(2026, 8, 6))])
        self.assertEqual(available_hours(_sprint([away])), 48.0)

    def test_multiple_activities_sum_per_member(self):
        """A person split across activities contributes the sum of both."""
        member = MemberCapacity(
            member_id="u1",
            activities=(
                ActivityCapacity("Development", 5.0),
                ActivityCapacity("Testing", 3.0),
            ),
        )
        self.assertEqual(available_hours(_sprint([member])), 80.0)

    def test_empty_team_has_no_capacity(self):
        """No members means no hours."""
        self.assertEqual(available_hours(_sprint()), 0.0)

    def test_available_by_activity_splits_correctly(self):
        """Per-activity availability keeps the buckets separate."""
        member = MemberCapacity(
            member_id="u1",
            activities=(
                ActivityCapacity("Development", 5.0),
                ActivityCapacity("Testing", 3.0),
            ),
        )
        by_activity = available_by_activity(_sprint([member]))
        self.assertEqual(by_activity["Development"], 50.0)
        self.assertEqual(by_activity["Testing"], 30.0)

    def test_unnamed_activity_is_bucketed_as_unassigned(self):
        """Azure's empty-name activity is the unassigned bucket."""
        member = MemberCapacity(member_id="u1", activities=(ActivityCapacity("", 6.0),))
        self.assertIn(UNASSIGNED_ACTIVITY, available_by_activity(_sprint([member])))


class TestPlannedHours(unittest.TestCase):
    """Tests for summing what the team has taken on."""

    def test_remaining_work_preferred_over_estimate(self):
        """Remaining work is the live number; the original estimate is history."""
        item = EstimableItem(item_id="1", estimated_hours=10.0, remaining_hours=3.0)
        self.assertEqual(item.planned_hours, 3.0)

    def test_estimate_used_when_no_remaining_work(self):
        """Without remaining work, the estimate stands in."""
        item = EstimableItem(item_id="1", estimated_hours=10.0)
        self.assertEqual(item.planned_hours, 10.0)

    def test_unestimated_item_has_no_planned_hours(self):
        """An item with neither figure contributes nothing and is not counted as zero."""
        item = EstimableItem(item_id="1")
        self.assertIsNone(item.planned_hours)
        self.assertFalse(item.has_estimate)

    def test_planned_by_activity_groups_and_buckets(self):
        """Items group by activity; unset activity falls into the unassigned bucket."""
        items = [
            EstimableItem(item_id="1", remaining_hours=4.0, activity="Development"),
            EstimableItem(item_id="2", remaining_hours=6.0, activity="Development"),
            EstimableItem(item_id="3", remaining_hours=2.0),
        ]
        planned = planned_by_activity(items)
        self.assertEqual(planned["Development"], 10.0)
        self.assertEqual(planned[UNASSIGNED_ACTIVITY], 2.0)


class TestPlanIteration(unittest.TestCase):
    """Integration tests for the capacity plan."""

    def test_utilisation_and_fit(self):
        """A sprint within capacity is not flagged as overcommitted."""
        sprint = _sprint([_member(per_day=6.0)])  # 60h available
        plan = plan_iteration(sprint, [EstimableItem(item_id="1", remaining_hours=30.0)])
        self.assertEqual(plan.available_hours, 60.0)
        self.assertEqual(plan.planned_hours, 30.0)
        self.assertEqual(plan.utilisation, 0.5)
        self.assertFalse(plan.overcommitted)

    def test_overcommitment_is_detected_and_warned(self):
        """Taking on more than the team can do produces an explicit warning."""
        sprint = _sprint([_member(per_day=6.0)])  # 60h
        plan = plan_iteration(sprint, [EstimableItem(item_id="1", remaining_hours=90.0)])
        self.assertTrue(plan.overcommitted)
        self.assertTrue(any("overcommitted" in w for w in plan.warnings))

    def test_unestimated_items_are_reported_not_assumed_zero(self):
        """Missing estimates must be surfaced, since they make the total a floor."""
        sprint = _sprint([_member()])
        items = [
            EstimableItem(item_id="1", remaining_hours=5.0),
            EstimableItem(item_id="2"),
        ]
        plan = plan_iteration(sprint, items)
        self.assertEqual(plan.items_total, 2)
        self.assertEqual(plan.items_estimated, 1)
        self.assertEqual(plan.items_unestimated, 1)
        self.assertEqual(plan.coverage, 0.5)
        self.assertTrue(any("carry no estimate" in w for w in plan.warnings))

    def test_no_estimates_at_all_says_so_plainly(self):
        """A plan where nothing is estimated must admit it says nothing."""
        plan = plan_iteration(_sprint([_member()]), [EstimableItem(item_id="1")])
        self.assertTrue(any("says nothing about fit" in w for w in plan.warnings))

    def test_missing_dates_warn_and_do_not_raise(self):
        """An iteration without dates degrades to warnings, following never-raise."""
        plan = plan_iteration(IterationCapacity(iteration_ref="x"), [])
        self.assertEqual(plan.available_hours, 0.0)
        self.assertIsNone(plan.utilisation)
        self.assertTrue(any("no start/finish date" in w for w in plan.warnings))
        self.assertTrue(any("no team members" in w for w in plan.warnings))

    def test_empty_plan_has_no_coverage(self):
        """With no items at all, coverage is undefined rather than zero."""
        self.assertIsNone(plan_iteration(_sprint([_member()]), []).coverage)

    def test_activity_breakdown_covers_both_sides(self):
        """An activity that is planned but has no capacity still appears."""
        sprint = _sprint([_member(per_day=5.0, activity="Development")])
        items = [EstimableItem(item_id="1", remaining_hours=4.0, activity="Testing")]
        activities = {row.activity for row in plan_iteration(sprint, items).by_activity}
        self.assertEqual(activities, {"Development", "Testing"})

    def test_format_plan_renders_key_figures(self):
        """The terminal report shows the numbers a reader needs."""
        plan = plan_iteration(_sprint([_member()]), [EstimableItem(item_id="1", remaining_hours=12.0)])
        report = format_plan(plan)
        self.assertIn("sprint-42", report)
        self.assertIn("Available", report)
        self.assertIn("Utilisation", report)

    def test_format_plan_handles_undefined_utilisation(self):
        """A zero-capacity plan renders without dividing by zero."""
        self.assertIn("n/a", format_plan(plan_iteration(IterationCapacity(iteration_ref="x"), [])))


if __name__ == "__main__":
    unittest.main()
