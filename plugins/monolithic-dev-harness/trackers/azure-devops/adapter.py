"""Azure Boards through the `@azure-devops/mcp` server.

The server has one tool per area and an `action` argument per operation (`wit_query` + `wiql`,
`wit_work_item_write` + `create`, ...); every call names the project. Work items come back in the
REST shape (`id`, `fields["System.Title"]`, ...), sometimes as JSON text in a `body` field.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from core.result import (
    Ok,
    Result,
    attempt,
    bind,
    err,
    fmap,
    require,
    sequence,
    value_or,
)
from integrations import artifacts, payloads
from integrations.contracts import (
    AdapterContext,
    ArtifactDraft,
    ArtifactRef,
    LogicalState,
    Page,
    TrackerOps,
    WorkItem,
    WorkItemKind,
)
from integrations.payloads import as_float, first_number, parse_date
from integrations.planning import (
    DEFAULT_WEEKEND_DAYS,
    ActivityCapacity,
    DateRange,
    EstimableItem,
    HourFields,
    IterationCapacity,
    IterationReading,
    MemberCapacity,
    date_ranges,
    hour_writer,
    pick_sprint,
)

# The single home of the Azure DevOps field reference names this tracker reads and writes.
# -- Backlog tier: relative size ------------------------------------------
# All three map to the same `Effort` slot in the project's process configuration, which is
# why any of them can feed velocity and the burndown's "sum of" selector. Which one exists
# depends on the process the project was created from.
STORY_POINTS = "Microsoft.VSTS.Scheduling.StoryPoints"  # Agile: User Story, Bug
EFFORT = "Microsoft.VSTS.Scheduling.Effort"  # Scrum: Product Backlog Item, Bug
SIZE = "Microsoft.VSTS.Scheduling.Size"  # CMMI: Requirement

# -- Task tier: absolute hours --------------------------------------------
REMAINING_WORK = "Microsoft.VSTS.Scheduling.RemainingWork"
"""Drives capacity bars and the sprint burndown. Present on every process."""

ORIGINAL_ESTIMATE = "Microsoft.VSTS.Scheduling.OriginalEstimate"
"""NOT present on Scrum projects -- guard every write with `_supports_original_estimate`."""

COMPLETED_WORK = "Microsoft.VSTS.Scheduling.CompletedWork"
"""NOT present on Scrum projects."""

ACTIVITY = "Microsoft.VSTS.Common.Activity"
"""Named `Discipline` in CMMI. Allowed values are configured per project."""

DISCIPLINE = "Microsoft.VSTS.Common.Discipline"  # CMMI equivalent of Activity

# -- System fields ---------------------------------------------------------
ID = "System.Id"
TITLE = "System.Title"
DESCRIPTION = "System.Description"
WORK_ITEM_TYPE = "System.WorkItemType"
STATE = "System.State"
PARENT = "System.Parent"
ASSIGNED_TO = "System.AssignedTo"
ITERATION_PATH = "System.IterationPath"
TEAM_PROJECT = "System.TeamProject"
CHANGED_DATE = "System.ChangedDate"
FIELDS = (ID, TITLE, WORK_ITEM_TYPE, STATE, DESCRIPTION, PARENT)

# -- Sprints ---------------------------------------------------------------
WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
TIMEFRAME_CURRENT = 1  # Azure's iteration timeFrame: 0 past, 1 current, 2 future
SPRINT_MARKERS = (
    "attributes",
    "startDate",
    "finishDate",
)  # a single sprint, not a listing

# -- Queries ---------------------------------------------------------------
LIMIT = (
    200  # the server's cap on one WIQL result, one batch read, and one page of comments
)
# A WIQL condition names a field (`[System.State]`, `[Custom.Team]`); anything else is search text.
WIQL_FIELD = re.compile(r"\[[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+\]")

# -- Processes -------------------------------------------------------------
PROCESS_AGILE = "agile"
PROCESS_SCRUM = "scrum"
PROCESS_CMMI = "cmmi"

DEFAULT_PROCESS = PROCESS_AGILE

POINTS_FIELD_BY_PROCESS = {
    PROCESS_AGILE: STORY_POINTS,
    PROCESS_SCRUM: EFFORT,
    PROCESS_CMMI: SIZE,
}

ACTIVITY_FIELD_BY_PROCESS = {
    PROCESS_AGILE: ACTIVITY,
    PROCESS_SCRUM: ACTIVITY,
    PROCESS_CMMI: DISCIPLINE,
}


def _process(value: str | None) -> str:
    """The process a name refers to; Agile when the name is missing or unrecognised."""
    text = (value or "").strip().lower()
    return next(
        (
            known
            for known in (PROCESS_SCRUM, PROCESS_CMMI, PROCESS_AGILE)
            if known in text
        ),
        DEFAULT_PROCESS,
    )


def _points_field(process: str | None = None) -> str:
    return POINTS_FIELD_BY_PROCESS[_process(process)]


def _activity_field(process: str | None = None) -> str:
    return ACTIVITY_FIELD_BY_PROCESS[_process(process)]


def _supports_original_estimate(process: str | None = None) -> bool:
    """Scrum ships only Remaining Work; Agile and CMMI ship all three scheduling fields.

    Writing Original Estimate to a Scrum project fails or silently drops the value, so an
    unstated process counts as unsupported: Remaining Work, which every process has, is enough.
    """
    return bool((process or "").strip()) and _process(process) != PROCESS_SCRUM


def _field_ref(field_name: str) -> str:
    """JSON-Patch path for a field, as `wit_work_item_write[update]` expects it."""
    return f"/fields/{field_name}"


def adapter(context: AdapterContext) -> TrackerOps:
    call = _caller(context)
    read = _reader(context, call)
    process = context.values.get("process", "")
    return TrackerOps(
        get_work_item=read,
        search_work_items=lambda query, cursor: _search(context, call, query),
        create_work_item=lambda kind, title, description, parent: _create(
            context, call, read, kind, title, description, parent
        ),
        transition_work_item=lambda ref, state: _transition(
            context, call, read, ref, state
        ),
        list_children=lambda ref: bind(
            payloads.number(ref, "parent"),
            lambda parent: _query(
                context,
                call,
                f"SELECT [{ID}] FROM WorkItems WHERE [{PARENT}] = {parent}",
            ),
        ),
        list_artifacts=lambda ref: _comments(call, ref),
        add_artifact=lambda ref, draft: _comment(call, ref, draft),
        link_development_artifact=lambda ref, url, kind: bind(
            payloads.number(ref, "work item"),
            lambda number: fmap(
                call(
                    "link",
                    "link",
                    {
                        "updates": [
                            {
                                "id": number,
                                "type": "hyperlink",
                                "url": url,
                                "comment": kind,
                            }
                        ]
                    },
                ),
                payloads.mapping,
            ),
        ),
        read_iteration=lambda replies, ref: fmap(
            _usable(replies), lambda _: _reading(replies, ref)
        ),
        iteration_items=lambda replies, ref: _sprint_items(replies, process),
        hour_fields=_hour_fields(process),
    )


def _caller(context: AdapterContext):
    project = context.values.get("project", "")
    tools = context.manifest.tools

    def call(tool: str, action: str, arguments: Mapping[str, Any]) -> Result[Any]:
        present = {key: value for key, value in arguments.items() if value is not None}
        return context.call(
            tools[tool], {"action": action, "project": project, **present}
        )

    return call


def _reader(context: AdapterContext, call):
    def read(ref: str) -> Result[WorkItem]:
        return bind(
            payloads.number(ref, "work item"),
            lambda number: bind(
                call("read", "get", {"id": number, "expand": "Relations"}),
                lambda reply: _first(
                    context, reply, f"work item {ref} was not returned"
                ),
            ),
        )

    return read


def _first(context: AdapterContext, reply: Any, missing: str) -> Result[WorkItem]:
    match _records(reply):
        case (record, *_):
            return Ok(_item(context, record))
        case ():
            return err("not_found", missing)


def _records(reply: Any) -> tuple[Mapping[str, Any], ...]:
    """Work item records from one record, a wrapped list, or a batch whose items carry JSON text."""
    return tuple(
        record
        for record in map(_unwrapped, payloads.one_or_many(reply, "fields", "id"))
        if isinstance(record, dict)
    )


def _unwrapped(item: Any) -> Any:
    match item:
        case {"body": str(body)}:
            return value_or(
                attempt(lambda: json.loads(body), "bad_body", "batch item", ValueError),
                None,
            )
        case _:
            return item


def _item(context: AdapterContext, record: Mapping[str, Any]) -> WorkItem:
    fields = record.get("fields") if isinstance(record.get("fields"), dict) else {}
    link = ((record.get("_links") or {}).get("html") or {}).get("href")
    manifest = context.manifest
    return WorkItem(
        id=payloads.text(record, "id") or payloads.text(fields, ID),
        key=payloads.text(record, "id") or payloads.text(fields, ID),
        title=payloads.text(fields, TITLE),
        kind=payloads.reverse(
            manifest.kinds,
            payloads.text(fields, WORK_ITEM_TYPE),
            WorkItemKind.TASK,
        ),
        state=payloads.reverse(
            manifest.states, payloads.text(fields, STATE), LogicalState.BACKLOG
        ),
        url=str(link or record.get("url") or ""),
        description=payloads.text(fields, DESCRIPTION),
        parent_id=payloads.text(fields, PARENT),
        provider_data=record,
    )


def _wiql(query: str) -> str:
    """A WIQL statement from a statement, a condition naming a field, or plain search text."""
    text = query.strip()
    condition = (
        text
        if WIQL_FIELD.search(text)
        else f"[{TITLE}] CONTAINS '{{}}'".format(text.replace("'", "''"))
    )
    return (
        text
        if text.upper().startswith("SELECT")
        else f"SELECT [{ID}] FROM WorkItems WHERE [{TEAM_PROJECT}] = @project "
        f"AND ({condition}) ORDER BY [{CHANGED_DATE}] DESC"
    )


def _ids(call, statement: str) -> Result[tuple[int, ...]]:
    return fmap(
        call("query", "wiql", {"wiql": statement, "top": LIMIT}),
        lambda reply: tuple(
            int(item["id"])
            for item in payloads.records(reply)
            if str(item.get("id", "")).isdigit()
        ),
    )


def _batch(
    context: AdapterContext, call, ids: tuple[int, ...]
) -> Result[tuple[WorkItem, ...]]:
    chunks = tuple(ids[start : start + LIMIT] for start in range(0, len(ids), LIMIT))
    return fmap(
        sequence(
            call("read", "get_batch", {"ids": list(chunk), "fields": list(FIELDS)})
            for chunk in chunks
        ),
        lambda replies: tuple(
            _item(context, record) for reply in replies for record in _records(reply)
        ),
    )


def _query(
    context: AdapterContext, call, statement: str
) -> Result[tuple[WorkItem, ...]]:
    return bind(_ids(call, statement), lambda ids: _batch(context, call, ids))


def _search(context: AdapterContext, call, query: str) -> Result[Page]:
    # The server caps a WIQL result; say so rather than implying the result is complete.
    return bind(
        _ids(call, _wiql(query)),
        lambda ids: fmap(
            _batch(context, call, ids), lambda found: Page(found, "", len(ids) >= LIMIT)
        ),
    )


def _create(
    context: AdapterContext,
    call,
    read,
    kind: WorkItemKind,
    title: str,
    description: str,
    parent: str,
) -> Result[WorkItem]:
    work_type = context.manifest.kinds[kind]
    request = (
        bind(
            payloads.number(parent, "parent"),
            lambda number: call(
                "write",
                "add_child",
                {
                    "parentId": number,
                    "workItemType": work_type,
                    "items": [
                        {
                            "title": title,
                            "description": description,
                            "format": "Markdown",
                        }
                    ],
                },
            ),
        )
        if parent
        else call(
            "write",
            "create",
            {
                "workItemType": work_type,
                "fields": [
                    {"name": TITLE, "value": title},
                    {
                        "name": DESCRIPTION,
                        "value": description,
                        "format": "Markdown",
                    },
                ],
            },
        )
    )
    # Read it back so the caller gets the stored item, not the echo of the request.
    return bind(request, lambda reply: _read_created(read, reply))


def _read_created(read, reply: Any) -> Result[WorkItem]:
    match tuple(record for record in _records(reply) if record.get("id")):
        case (created, *_):
            return read(str(created["id"]))
        case ():
            return err(
                "provider_error", "Azure DevOps did not return the created work item"
            )


def _transition(
    context: AdapterContext, call, read, ref: str, state: LogicalState
) -> Result[WorkItem]:
    update = [
        {
            "op": "add",
            "path": _field_ref(STATE),
            "value": context.manifest.states[state],
        }
    ]
    return bind(
        payloads.number(ref, "work item"),
        lambda number: bind(
            call("write", "update", {"id": number, "updates": update}),
            lambda _: read(ref),
        ),
    )


def _comments(call, ref: str) -> Result[tuple[ArtifactRef, ...]]:
    return bind(
        payloads.number(ref, "work item"),
        lambda number: fmap(
            call("read", "list_comments", {"workItemId": number, "top": LIMIT}),
            lambda reply: artifacts.references(
                payloads.records(reply), "text", "content"
            ),
        ),
    )


def _comment(call, ref: str, draft: ArtifactDraft) -> Result[ArtifactRef]:
    return bind(
        payloads.number(ref, "work item"),
        lambda number: fmap(
            call(
                "comment",
                "add",
                {
                    "workItemId": number,
                    "text": artifacts.encode(draft),
                    "format": "Markdown",
                },
            ),
            lambda reply: artifacts.added(payloads.mapping(reply), draft),
        ),
    )


# --- planning: the sprint, its items, and the fields that record hours ----------------------


def _reading(replies: Mapping[str, Any], iteration_ref: str) -> IterationReading:
    """The sprint from the replies the manifest's `planning.replies` names; see `pick_sprint`."""
    sprint, missing = pick_sprint(
        replies.get("iteration"),
        iteration_ref,
        SPRINT_MARKERS,
        ("id", "name", "path"),
        _current_sprint,
    )
    return IterationReading(
        _iteration(
            iteration_ref,
            iteration=sprint,
            capacities=replies.get("capacities"),
            team_settings=replies.get("team_settings"),
        ),
        missing + _capacity_cross_check(replies.get("capacities")),
    )


# What each reply must be to be read: a sprint (or a listing of them), a capacity listing, the team
# settings object. A reply that was fetched but holds none of that (an error text, say) is refused,
# since reading it as "no team" or "no sprint" would let work past the capacity check.
REPLY_SHAPES = {
    "iteration": lambda reply: payloads.readable(reply, *SPRINT_MARKERS),
    "capacities": payloads.is_listing,
    "team_settings": lambda reply: isinstance(reply, dict),
}


def _usable(replies: Mapping[str, Any]) -> Result[None]:
    unusable = tuple(
        key
        for key, fits in REPLY_SHAPES.items()
        if key in replies and not fits(replies[key])
    )
    return require(
        not unusable,
        "unreadable_reply",
        f"these replies hold no usable data, fetch them again: {', '.join(unusable)}",
    )


def _sprint_items(
    replies: Mapping[str, Any], process: str | None
) -> Result[tuple[EstimableItem, ...]]:
    """The sprint's work items with their fields.

    A reply that lists only ids (what `wit_work_item[list_for_iteration]` returns) is refused
    rather than read as an empty sprint; an empty list of ids is an empty sprint.
    """
    reply = replies.get("work_items")
    relations = payloads.object_or_empty(reply).get("workItemRelations")
    return (
        err(
            "ids_only",
            "the work_items reply lists only work item ids; read them with "
            "wit_work_item[get_batch] (no fields list) and pass that reply as work_items, "
            "or [] when the sprint has none",
        )
        if payloads.listed(relations)
        or any(
            "target" in record and "fields" not in record
            for record in payloads.records(reply)
        )
        else Ok(())
        if isinstance(relations, list)
        else err(
            "unreadable_reply",
            "the work_items reply holds no usable data, fetch it again",
        )
        if "work_items" in replies and not payloads.readable(reply, "fields", "id")
        else Ok(_estimables(reply, process=process))
    )


def _hour_fields(process: str | None) -> HourFields:
    """Remaining Work always; Original Estimate once, where the process has it."""
    return hour_writer(
        _field_ref(REMAINING_WORK),
        _field_ref(ORIGINAL_ESTIMATE) if _supports_original_estimate(process) else "",
    )


def _weekday_index(value: Any) -> int | None:
    """One working-day entry as Python's weekday number (Monday = 0).

    Azure sends day names through the REST API but integers through the MCP server, and those
    count from Sunday = 0 the JavaScript way; a team working [1,2,3,4,5] works Monday to Friday.
    """
    match value:
        case bool():
            return None
        case int():
            return (value - 1) % 7 if 0 <= value <= 6 else None
        case _:
            text = str(value).strip().lower()
            return (
                _weekday_index(int(text)) if text.isdigit() else WEEKDAY_INDEX.get(text)
            )


def _days_off(payload: Any) -> tuple[DateRange, ...]:
    """A daysOff list, bare or under a `daysOff` key."""
    return date_ranges(payload.get("daysOff") if isinstance(payload, dict) else payload)


def _capacities(payload: Any) -> tuple[MemberCapacity, ...]:
    """The team capacity reply: one member per entry, with hours per day for each activity."""
    return tuple(_member(entry) for entry in payloads.records(payload))


def _member(entry: Mapping[str, Any]) -> MemberCapacity:
    person = payloads.object_or_empty(entry.get("teamMember"))
    return MemberCapacity(
        member_id=payloads.text(person, "id"),
        display_name=payloads.text(person, "displayName"),
        # An unreadable figure is left out rather than counted as zero; the cross-check against
        # Azure's own total reports the shortfall.
        activities=tuple(
            ActivityCapacity(payloads.text(activity, "name"), per_day)
            for activity in payloads.records(entry.get("activities"))
            if (per_day := as_float(activity.get("capacityPerDay"))) is not None
        ),
        days_off=_days_off(entry.get("daysOff")),
    )


def _current_sprint(
    entries: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any] | None:
    """The active sprint in an iteration listing, or None when none is marked active.

    A `timeframe: current` query returns only the active sprint, so a lone unmarked entry is it.
    An entry marked past or future is never taken as current.
    """
    unmarked = tuple(entry for entry in entries if _time_frame(entry) is None)
    return next(
        (entry for entry in entries if _time_frame(entry) == TIMEFRAME_CURRENT),
        unmarked[0] if len(entries) == 1 and unmarked else None,
    )


def _time_frame(entry: Mapping[str, Any]) -> Any:
    return payloads.object_or_empty(entry.get("attributes")).get("timeFrame")


def _reported_daily_total(payload: Any) -> float | None:
    """Azure's own `totalCapacityPerDay`, when the capacity reply carries it."""
    return (
        as_float(payload.get("totalCapacityPerDay"))
        if isinstance(payload, dict)
        else None
    )


def _weekend_days(team_settings: Any) -> tuple[int, ...] | None:
    """The days a team does not work, from the working days its settings state.

    None means "not stated" (no settings, or no readable day), so the default stays. An empty
    tuple is a real answer: a team that works all seven days has no weekend.
    """
    working = payloads.object_or_empty(team_settings).get("workingDays")
    worked = frozenset(
        index
        for index in map(_weekday_index, working if isinstance(working, list) else ())
        if index is not None
    )
    return tuple(sorted(frozenset(range(7)) - worked)) if worked else None


def _iteration(
    iteration_ref: str,
    *,
    iteration: Any = None,
    capacities: Any = None,
    team_settings: Any = None,
) -> IterationCapacity:
    """A sprint from the three Azure replies that describe it."""
    sprint = payloads.object_or_empty(iteration)
    attributes = payloads.object_or_empty(sprint.get("attributes"))
    weekend = _weekend_days(team_settings)
    return IterationCapacity(
        iteration_ref=iteration_ref,
        start_date=parse_date(attributes.get("startDate") or sprint.get("startDate")),
        finish_date=parse_date(
            attributes.get("finishDate") or sprint.get("finishDate")
        ),
        members=_capacities(capacities),
        team_days_off=_days_off(
            payloads.object_or_empty(team_settings).get("teamDaysOff")
        ),
        weekend_days=DEFAULT_WEEKEND_DAYS if weekend is None else weekend,
    )


def _estimable(payload: Any, *, process: str | None = None) -> EstimableItem | None:
    """One work item as the planner sees it; None when the record carries no id."""
    record = payloads.object_or_empty(payload)
    fields = payloads.object_or_empty(record.get("fields"))
    item_id = payloads.text(record, "id") or payloads.text(fields, ID)
    person = fields.get(ASSIGNED_TO)
    assigned = (
        payloads.text(person, "displayName", "uniqueName")
        if isinstance(person, dict)
        else str(person or "")
    )
    activity = payloads.text(fields, _activity_field(process), ACTIVITY)
    return (
        EstimableItem(
            item_id=item_id,
            title=payloads.text(fields, TITLE),
            item_type=payloads.text(fields, WORK_ITEM_TYPE),
            points=first_number(
                fields, _points_field(process), STORY_POINTS, EFFORT, SIZE
            ),
            estimated_hours=as_float(fields.get(ORIGINAL_ESTIMATE)),
            remaining_hours=as_float(fields.get(REMAINING_WORK)),
            completed_hours=as_float(fields.get(COMPLETED_WORK)),
            activity=activity or None,
            assigned_to=assigned or None,
            state=payloads.text(fields, STATE),
            iteration=payloads.text(fields, ITERATION_PATH) or None,
        )
        if item_id
        else None
    )


def _estimables(
    payload: Any, *, process: str | None = None
) -> tuple[EstimableItem, ...]:
    return tuple(
        item
        for item in (
            _estimable(record, process=process) for record in _records(payload)
        )
        if item is not None
    )


def _capacity_cross_check(capacities: Any) -> tuple[str, ...]:
    """The mapped per-member total against Azure's own; a gap means someone was misread."""
    reported = _reported_daily_total(capacities)
    mapped = round(sum(member.daily_hours for member in _capacities(capacities)), 2)
    return (
        ()
        if reported is None or abs(mapped - reported) < 0.01
        else (
            f"capacity mismatch: mapped {mapped:g}h/day but Azure reports {reported:g}h/day — "
            "some members or activities could not be read, so availability is understated",
        )
    )
