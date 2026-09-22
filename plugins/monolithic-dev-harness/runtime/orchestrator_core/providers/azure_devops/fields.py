"""Azure DevOps field reference names.

The single Python home for `Microsoft.VSTS.*` and `System.*` strings, which until now lived
only in scattered markdown. Import from here rather than retyping a reference name.
"""

from __future__ import annotations

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
"""NOT present on Scrum projects -- guard every write with `supports_original_estimate`."""

COMPLETED_WORK = "Microsoft.VSTS.Scheduling.CompletedWork"
"""NOT present on Scrum projects."""

ACTIVITY = "Microsoft.VSTS.Common.Activity"
"""Named `Discipline` in CMMI. Allowed values are configured per project."""

DISCIPLINE = "Microsoft.VSTS.Common.Discipline"  # CMMI equivalent of Activity

ACCEPTANCE_CRITERIA = "Microsoft.VSTS.Common.AcceptanceCriteria"

# -- System fields ---------------------------------------------------------
TITLE = "System.Title"
DESCRIPTION = "System.Description"
WORK_ITEM_TYPE = "System.WorkItemType"
STATE = "System.State"
PARENT = "System.Parent"
ASSIGNED_TO = "System.AssignedTo"
ITERATION_PATH = "System.IterationPath"
AREA_PATH = "System.AreaPath"

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


def normalize_process(value: str | None) -> str:
    """Resolve a process name, degrading to Agile when unrecognised."""
    if not value:
        return DEFAULT_PROCESS
    text = value.strip().lower()
    for known in (PROCESS_SCRUM, PROCESS_CMMI, PROCESS_AGILE):
        if known in text:
            return known
    return DEFAULT_PROCESS


def points_field(process: str | None = None) -> str:
    return POINTS_FIELD_BY_PROCESS[normalize_process(process)]


def activity_field(process: str | None = None) -> str:
    return ACTIVITY_FIELD_BY_PROCESS[normalize_process(process)]


def supports_original_estimate(process: str | None = None) -> bool:
    """Scrum ships only Remaining Work; Agile and CMMI ship all three scheduling fields.

    Writing Original Estimate to a Scrum project fails or silently drops the value, so an
    unstated process is treated as unsupported. Guessing wrong here is silent, and Remaining
    Work -- which every process has -- is enough on its own.
    """
    if not (process or "").strip():
        return False
    return normalize_process(process) != PROCESS_SCRUM


def supports_completed_work(process: str | None = None) -> bool:
    if not (process or "").strip():
        return False
    return normalize_process(process) != PROCESS_SCRUM


def field_ref(field_name: str) -> str:
    """JSON-Patch path for a field, as `wit_update_work_item` expects it."""
    return f"/fields/{field_name}"
