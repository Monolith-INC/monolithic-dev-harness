"""Contract tests for how the Azure tracker reads Azure's replies.

The translation is private to the Azure tracker's adapter.py; these tests reach it through the
tracker's planning operations. The fixtures in test_providers.py are shaped from Microsoft's
published response examples.
Real payloads carry extra keys, richer identity objects, and occasionally a type nobody
expected. These tests assert the mappers degrade rather than raise when reality differs
from the documented example -- which is what protects the plugin when Azure's payload
drifts, or when a field arrives as a string instead of a number.

Rule under test: a mapper may return less, but it must never raise and must never invent.
"""

import unittest
from datetime import date

from azure_tracker import days_off, item, items, members, reading, sprint, weekend

from integrations.planning import DEFAULT_WEEKEND_DAYS, DateRange
from orchestrator_core.capacity import plan_iteration

# A capacity entry as a real organisation returns it: full identity object, _links, descriptor.
REALISTIC_CAPACITY_ENTRY = {
    "teamMember": {
        "displayName": "Chuck Reinhart",
        "url": "https://sps1.vssps.vsts.me/A.../_apis/Identities/73a2309e",
        "_links": {
            "avatar": {
                "href": "https://codedev.ms/fabrikam/_apis/GraphProfile/MemberAvatars/aad.Nz"
            }
        },
        "id": "73a2309e-d0b3-6bf5-9500-9af8bcc805ec",
        "uniqueName": "fabrikamfiber3@hotmail.com",
        "imageUrl": "https://codedev.ms/fabrikam/_api/_common/identityImage?id=73a2309e",
        "descriptor": "aad.NzNhMjMwOWUtZDBiMy03YmY1LTk1MDAtOWFmOGJjYzgwNWVj",
    },
    "activities": [{"capacityPerDay": 4, "name": "Design"}],
    "daysOff": [],
    "url": "https://dev.azure.com/fabrikam/.../capacities/73a2309e",
}


class TestCapacityMapperDegradation(unittest.TestCase):
    """The capacity mapper against shapes the documented example does not show."""

    def test_realistic_identity_object_maps(self):
        """A full identity object with _links and descriptor maps cleanly."""
        team = members([REALISTIC_CAPACITY_ENTRY])
        self.assertEqual(len(team), 1)
        self.assertEqual(team[0].member_id, "73a2309e-d0b3-6bf5-9500-9af8bcc805ec")
        self.assertEqual(team[0].display_name, "Chuck Reinhart")
        self.assertEqual(team[0].daily_hours, 4.0)

    def test_unknown_top_level_keys_are_ignored(self):
        """Extra keys the API adds later must not break the mapping."""
        entry = dict(
            REALISTIC_CAPACITY_ENTRY, somethingNew={"nested": True}, anotherField=42
        )
        self.assertEqual(len(members([entry])), 1)

    def test_missing_team_member_yields_blank_identity_not_a_crash(self):
        """A capacity row with no identity still maps, with empty ids."""
        team = members([{"activities": [{"capacityPerDay": 5, "name": "Dev"}]}])
        self.assertEqual(team[0].member_id, "")
        self.assertEqual(team[0].daily_hours, 5.0)

    def test_team_member_as_a_string_does_not_raise(self):
        """A non-object identity degrades to a blank one."""
        team = members([{"teamMember": "chuck", "activities": []}])
        self.assertEqual(team[0].member_id, "")

    def test_missing_activities_yields_zero_capacity(self):
        """A member with no activities contributes nothing, rather than failing."""
        team = members([{"teamMember": {"id": "u1"}}])
        self.assertEqual(team[0].activities, ())
        self.assertEqual(team[0].daily_hours, 0.0)

    def test_capacity_per_day_as_a_string_is_coerced(self):
        """Numbers arriving as strings are coerced rather than dropped."""
        team = members(
            [
                {
                    "teamMember": {"id": "u1"},
                    "activities": [{"capacityPerDay": "6", "name": "Dev"}],
                }
            ]
        )
        self.assertEqual(team[0].daily_hours, 6.0)

    def test_null_capacity_becomes_zero_not_an_error(self):
        """A null capacity is zero hours, not a crash."""
        team = members(
            [
                {
                    "teamMember": {"id": "u1"},
                    "activities": [{"capacityPerDay": None, "name": "Dev"}],
                }
            ]
        )
        self.assertEqual(team[0].daily_hours, 0.0)

    def test_missing_activity_name_is_the_unassigned_bucket(self):
        """An activity with no name is Azure's unassigned bucket."""
        team = members(
            [{"teamMember": {"id": "u1"}, "activities": [{"capacityPerDay": 6}]}]
        )
        self.assertTrue(team[0].activities[0].is_unassigned)

    def test_null_activity_name_does_not_become_the_string_none(self):
        """A null name must not render as the literal text 'None'."""
        team = members(
            [
                {
                    "teamMember": {"id": "u1"},
                    "activities": [{"capacityPerDay": 6, "name": None}],
                }
            ]
        )
        self.assertEqual(team[0].activities[0].name, "")

    def test_hostile_inputs_return_empty(self):
        """Anything unmappable yields nothing rather than raising."""
        for payload in (
            None,
            "text",
            42,
            [],
            {},
            {"value": None},
            [None],
            [[]],
            {"value": "text"},
        ):
            self.assertEqual(members(payload), ())


class TestDaysOffDegradation(unittest.TestCase):
    """Days off carry dates, which are the easiest thing for a payload to get wrong."""

    def test_malformed_dates_are_dropped_not_guessed(self):
        """An unparseable date is discarded; it must never become today."""
        self.assertEqual(days_off([{"start": "not-a-date", "end": "also-not"}]), ())

    def test_partial_range_uses_start_for_both_ends(self):
        """A start with no end is a single day off."""
        ranges = days_off([{"start": "2026-08-05T00:00:00Z"}])
        self.assertEqual(
            (ranges[0].start, ranges[0].end), (date(2026, 8, 5), date(2026, 8, 5))
        )

    def test_null_start_is_dropped(self):
        """A range with no start cannot be placed, so it is dropped."""
        self.assertEqual(days_off([{"start": None, "end": "2026-08-05"}]), ())

    def test_mixed_valid_and_invalid_keeps_the_valid(self):
        """One bad entry must not discard the good ones."""
        ranges = days_off(
            [{"start": "bad"}, {"start": "2026-08-05", "end": "2026-08-06"}]
        )
        self.assertEqual(len(ranges), 1)

    def test_hostile_inputs_return_empty(self):
        """Unmappable days-off payloads yield nothing."""
        for payload in (None, "text", 42, [None], [42], {"daysOff": None}):
            self.assertEqual(days_off(payload), ())

    def test_a_bare_date_is_one_day_off(self):
        """Days off share one reader with capacity files, where a bare date means that day."""
        self.assertEqual(
            days_off(["2026-08-05"]),
            (DateRange(date(2026, 8, 5), date(2026, 8, 5)),),
        )


class TestWeekendDegradation(unittest.TestCase):
    """Working-days configuration varies per team and per locale."""

    def test_unreadable_day_names_report_not_stated(self):
        """Entries none of which parse are 'not stated', so the caller keeps its default."""
        self.assertEqual(
            weekend({"workingDays": ["segunda", "terça"]}), DEFAULT_WEEKEND_DAYS
        )

    def test_case_and_whitespace_tolerated(self):
        """Day names arrive in mixed case in practice."""
        self.assertEqual(
            weekend({"workingDays": [" Monday ", "TUESDAY"]}), (2, 3, 4, 5, 6)
        )

    def test_all_seven_days_worked_means_no_weekend(self):
        """An empty tuple is a real answer, distinct from None: this team has no weekend.

        Collapsing it into 'unknown' silently deleted two days of their capacity.
        """
        every = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        self.assertEqual(weekend({"workingDays": every}), ())

    def test_empty_working_days_does_not_declare_every_day_a_weekend(self):
        """The dangerous case: an absent setting must not zero out capacity."""
        self.assertEqual(weekend({"workingDays": []}), DEFAULT_WEEKEND_DAYS)
        iteration = sprint(
            "it1",
            iteration={
                "attributes": {"startDate": "2026-08-03", "finishDate": "2026-08-14"}
            },
            team_settings={"workingDays": []},
        )
        self.assertEqual(len(iteration.working_days()), 10)


class TestWorkItemDegradation(unittest.TestCase):
    """The work-item mapper against realistic and hostile field payloads."""

    def test_id_as_string_or_int_both_map(self):
        """Azure returns ints; WIQL results sometimes carry strings."""
        self.assertEqual(item({"id": 101, "fields": {}}).item_id, "101")
        self.assertEqual(item({"id": "101", "fields": {}}).item_id, "101")

    def test_missing_fields_block_maps_to_an_empty_item(self):
        """An item with no fields is still addressable."""
        found = item({"id": 101})
        self.assertEqual(found.item_id, "101")
        self.assertIsNone(found.points)
        self.assertFalse(found.has_estimate)

    def test_assigned_to_as_identity_object_or_string(self):
        """Assignment arrives as an object normally and a string in older payloads."""
        as_object = item(
            {"id": 1, "fields": {"System.AssignedTo": {"displayName": "Ana"}}}
        )
        as_string = item({"id": 1, "fields": {"System.AssignedTo": "Ana"}})
        self.assertEqual(as_object.assigned_to, "Ana")
        self.assertEqual(as_string.assigned_to, "Ana")

    def test_assigned_to_falls_back_to_unique_name(self):
        """An identity with no display name still identifies someone."""
        found = item(
            {
                "id": 1,
                "fields": {"System.AssignedTo": {"uniqueName": "ana@example.com"}},
            }
        )
        self.assertEqual(found.assigned_to, "ana@example.com")

    def test_numeric_fields_as_strings_are_coerced(self):
        """Scheduling values arriving as strings must not be lost."""
        found = item(
            {
                "id": 1,
                "fields": {
                    "Microsoft.VSTS.Scheduling.RemainingWork": "8",
                    "Microsoft.VSTS.Scheduling.StoryPoints": "3",
                },
            }
        )
        self.assertEqual(found.remaining_hours, 8.0)
        self.assertEqual(found.points, 3.0)

    def test_zero_remaining_work_is_preserved_not_treated_as_absent(self):
        """A Task genuinely at zero hours differs from one never estimated."""
        found = item(
            {"id": 1, "fields": {"Microsoft.VSTS.Scheduling.RemainingWork": 0}}
        )
        self.assertEqual(found.remaining_hours, 0.0)
        self.assertTrue(found.has_estimate)

    def test_points_found_regardless_of_which_process_field_is_present(self):
        """A payload from an unexpected process still yields points."""
        for field in (
            "Microsoft.VSTS.Scheduling.StoryPoints",
            "Microsoft.VSTS.Scheduling.Size",
            "Microsoft.VSTS.Scheduling.Effort",
        ):
            self.assertEqual(item({"id": 1, "fields": {field: 5}}).points, 5.0)

    def test_explicit_zero_points_are_preserved(self):
        """A zero must survive: it is falsy, so a naive `or` chain would discard it."""
        found = item({"id": 1, "fields": {"Microsoft.VSTS.Scheduling.StoryPoints": 0}})
        self.assertEqual(found.points, 0.0)

    def test_zero_points_do_not_fall_through_to_another_process_field(self):
        """The process's own field wins even at zero, rather than reading a foreign one."""
        found = item(
            {
                "id": 1,
                "fields": {
                    "Microsoft.VSTS.Scheduling.StoryPoints": 0,
                    "Microsoft.VSTS.Scheduling.Effort": 5,
                },
            },
            process="agile",
        )
        self.assertEqual(found.points, 0.0)

    def test_process_field_takes_precedence_when_several_are_present(self):
        """A payload carrying both fields resolves by the declared process."""
        fields = {
            "Microsoft.VSTS.Scheduling.StoryPoints": 3,
            "Microsoft.VSTS.Scheduling.Effort": 8,
        }
        self.assertEqual(item({"id": 1, "fields": fields}, process="agile").points, 3.0)
        self.assertEqual(item({"id": 1, "fields": fields}, process="scrum").points, 8.0)

    def test_cmmi_discipline_is_read_as_activity(self):
        """CMMI names the activity field Discipline."""
        found = item(
            {"id": 1, "fields": {"Microsoft.VSTS.Common.Discipline": "Analysis"}},
            process="cmmi",
        )
        self.assertEqual(found.activity, "Analysis")

    def test_empty_iteration_path_becomes_none(self):
        """An empty string is not an iteration."""
        self.assertIsNone(
            item({"id": 1, "fields": {"System.IterationPath": ""}}).iteration
        )

    def test_unknown_fields_are_ignored(self):
        """Custom organisation fields must not break the mapping."""
        found = item(
            {"id": 1, "fields": {"Custom.MyOrg.Whatever": "x", "System.Title": "T"}}
        )
        self.assertEqual(found.title, "T")

    def test_hostile_inputs_return_none_or_empty(self):
        """Unmappable work-item payloads yield nothing."""
        for payload in (None, "text", 42, [], {}, {"fields": {}}):
            self.assertIsNone(item(payload))
        for payload in (None, "text", {"value": None}, [None]):
            self.assertEqual(items(payload), ())


class TestMcpServerShapes(unittest.TestCase):
    """Shapes captured from a real organisation through the Azure DevOps MCP server.

    These differ from the REST reference examples in two ways that both silently produced
    wrong answers before they were caught by a live read:

    1. Capacity arrives under `teamMembers`, not the REST `{count, value}` envelope.
    2. `workingDays` arrives as integers using JavaScript's Sunday-is-0 numbering, not as
       the day-name strings the REST documentation shows.
    """

    CAPACITY = {
        "teamMembers": [
            {
                "teamMember": {
                    "displayName": "Ana",
                    "id": "u1",
                    "uniqueName": "ana@example.com",
                },
                "activities": [{"capacityPerDay": 5, "name": ""}],
                "daysOff": [],
            },
            {
                "teamMember": {
                    "displayName": "Bruno",
                    "id": "u2",
                    "uniqueName": "bruno@example.com",
                },
                "activities": [{"capacityPerDay": 3, "name": ""}],
                "daysOff": [
                    {
                        "start": "2026-07-23T00:00:00.000Z",
                        "end": "2026-07-23T00:00:00.000Z",
                    }
                ],
            },
            {
                "teamMember": {
                    "displayName": "Carla",
                    "id": "u3",
                    "uniqueName": "carla@example.com",
                },
                "activities": [
                    {"capacityPerDay": 0, "name": "Design"},
                    {"capacityPerDay": 0, "name": "Testing"},
                ],
                "daysOff": [],
            },
        ],
        "totalCapacityPerDay": 8,
        "totalDaysOff": 1,
    }

    def test_team_members_envelope_is_understood(self):
        """The regression: this envelope previously mapped to zero members."""
        team = members(self.CAPACITY)
        self.assertEqual(len(team), 3)

    def test_mapped_total_agrees_with_azures_own_total(self):
        """Azure reports its own daily total; the mapping must reproduce it, so no warning."""
        self.assertEqual(sum(m.daily_hours for m in members(self.CAPACITY)), 8.0)
        self.assertEqual(reading(capacities=self.CAPACITY).warnings, ())

    def test_a_total_that_disagrees_is_reported(self):
        """A member Azure counts but the mapping could not read shows up as a mismatch."""
        short = dict(self.CAPACITY, totalCapacityPerDay=11)
        self.assertTrue(
            any("capacity mismatch" in w for w in reading(capacities=short).warnings)
        )

    def test_reported_total_absent_offers_no_cross_check(self):
        """A payload without the total simply offers no cross-check."""
        self.assertEqual(reading(capacities={"teamMembers": []}).warnings, ())
        self.assertEqual(reading(capacities="garbage").warnings, ())

    def test_rest_envelope_still_works(self):
        """Supporting the MCP shape must not break the raw REST shape."""
        rest = {"count": 1, "value": [{"teamMember": {"id": "u1"}, "activities": []}]}
        self.assertEqual(len(members(rest)), 1)

    def test_zero_capacity_members_are_kept_not_dropped(self):
        """A member allocated zero hours is still on the team."""
        team = members(self.CAPACITY)
        carla = [m for m in team if m.display_name == "Carla"][0]
        self.assertEqual(carla.daily_hours, 0.0)
        self.assertEqual(len(carla.activities), 2)

    def test_numeric_working_days_use_javascript_numbering(self):
        """[1,2,3,4,5] means Monday-Friday, so the weekend is Saturday and Sunday."""
        self.assertEqual(weekend({"workingDays": [1, 2, 3, 4, 5]}), (5, 6))

    def test_numeric_sunday_is_zero(self):
        """Sunday is 0 in Azure's numbering, which is 6 in Python's."""
        self.assertEqual(weekend({"workingDays": [0]}), (0, 1, 2, 3, 4, 5))

    def test_numeric_six_day_week(self):
        """Including Saturday (6) leaves only Sunday as weekend."""
        self.assertEqual(weekend({"workingDays": [1, 2, 3, 4, 5, 6]}), (6,))

    def test_numeric_and_named_days_agree(self):
        """The two representations of Monday-Friday must produce the same weekend."""
        named = weekend(
            {"workingDays": ["monday", "tuesday", "wednesday", "thursday", "friday"]}
        )
        self.assertEqual(weekend({"workingDays": [1, 2, 3, 4, 5]}), named)

    def test_out_of_range_day_numbers_are_ignored(self):
        """A nonsense index must not silently shift the week."""
        self.assertEqual(weekend({"workingDays": [9, 42]}), DEFAULT_WEEKEND_DAYS)

    def test_booleans_are_not_treated_as_day_numbers(self):
        """True is 1 in Python; it must not be read as Monday."""
        self.assertEqual(weekend({"workingDays": [True]}), DEFAULT_WEEKEND_DAYS)

    def test_end_to_end_against_captured_sprint(self):
        """The whole pipeline on real shapes: 8h/day, 10 working days, one day off at 3h."""
        iteration = sprint(
            "Sprint 59",
            iteration={
                "attributes": {
                    "startDate": "2026-07-21T00:00:00.000Z",
                    "finishDate": "2026-08-03T00:00:00.000Z",
                }
            },
            capacities=self.CAPACITY,
            team_settings={"workingDays": [1, 2, 3, 4, 5]},
        )
        plan = plan_iteration(iteration, [])
        self.assertEqual(plan.working_days, 10)
        self.assertEqual(plan.member_count, 3)
        # 8h/day x 10 days = 80h, less Bruno's single day off at 3h = 77h
        self.assertEqual(plan.available_hours, 77.0)


class TestFullPipelineDegradation(unittest.TestCase):
    """A whole plan built from partial and malformed payloads must still be honest."""

    def test_plan_survives_entirely_malformed_payloads(self):
        """Garbage in produces an empty plan with warnings, never an exception."""
        iteration = sprint(
            "it1", iteration="garbage", capacities="garbage", team_settings="garbage"
        )
        plan = plan_iteration(iteration, items("garbage"))
        self.assertEqual(plan.available_hours, 0.0)
        self.assertIsNone(plan.utilisation)
        self.assertTrue(plan.warnings)

    def test_partial_payload_reports_what_is_missing(self):
        """Capacity without dates cannot compute availability, and says so."""
        iteration = sprint("it1", capacities=[REALISTIC_CAPACITY_ENTRY])
        plan = plan_iteration(iteration, [])
        self.assertEqual(plan.member_count, 1)
        self.assertEqual(plan.available_hours, 0.0)
        self.assertTrue(any("no start/finish date" in w for w in plan.warnings))

    def test_unestimated_items_never_inflate_the_plan(self):
        """Items with no hours must contribute zero, not a guessed value."""
        iteration = sprint(
            "it1",
            iteration={
                "attributes": {"startDate": "2026-08-03", "finishDate": "2026-08-14"}
            },
            capacities=[REALISTIC_CAPACITY_ENTRY],
        )
        unestimated = items(
            {"value": [{"id": 1, "fields": {}}, {"id": 2, "fields": {}}]}
        )
        plan = plan_iteration(iteration, unestimated)
        self.assertEqual(plan.planned_hours, 0.0)
        self.assertEqual(plan.items_estimated, 0)
        self.assertTrue(any("says nothing about fit" in w for w in plan.warnings))


if __name__ == "__main__":
    unittest.main()
