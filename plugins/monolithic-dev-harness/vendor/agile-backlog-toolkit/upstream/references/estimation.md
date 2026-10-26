# Estimation and Capacity

How this plugin turns story points into hours, and how it decides whether a sprint fits.

## The two tiers

Backlog systems keep two separate estimation systems that never talk to each other.

**Points** sit on a Story. They measure how big something feels next to other work, not how long it
takes. Points drive velocity — the amount of size a team finishes per sprint — which is what makes
forecasting possible.

**Hours** sit on a Task. They drive sprint capacity and the burndown chart, the line showing how
much work is left as the sprint runs down.

A Task with no hours is invisible to both. It shows on the board and in the hierarchy, but the
sprint tooling reads it as nothing.

## There is no formula

Points are deliberately unitless and team-relative. No published algorithm converts them to hours,
and any constant claiming to is guessing. The only defensible method is measuring your own team:
divide the hours a set of finished work actually took by the points it carried.

So this plugin does not hardcode a curve. It resolves an estimate in three steps, and always says
which one it used:

```
1. calibrated   -- from your team's own completed work
        |  (not enough history?)
        v
2. config       -- bands your team wrote down
        |  (no config?)
        v
3. seed-default -- shipped starting point, explicitly not a measurement
```

Every suggestion carries that label. A `seed-default` figure announces itself as uncalibrated
wherever it appears, so nobody mistakes a shipped default for a fact about their team.

## Configuration

Create `.agile-backlog-toolkit/estimation.json` to replace the shipped defaults:

```json
{
  "scale": "fibonacci",
  "ceiling": 5,
  "bands": {
    "1": {"low": 1, "high": 2},
    "2": {"low": 2, "high": 4},
    "3": {"low": 4, "high": 6},
    "5": {"low": 8, "high": 16},
    "8": {"low": 24, "high": 40},
    "13": {"low": 40, "high": 80}
  },
  "calibration": {"enabled": true, "min_sample": 8, "window_iterations": 6}
}
```

`min_sample` is how many finished items must exist before a calibrated figure is trusted; below it
the number still appears but is marked low confidence. `window_iterations` limits calibration to
recent sprints, so a team that has got faster is not held to how it worked a year ago.

A malformed or missing file falls back to the defaults rather than failing.

## Estimates are applied, and always reported

Hours derive from the Story's points, so there is nothing for a person to approve item by item.
They are written without asking — and **every figure that is set or changed is named in the run
summary**, old value and new. Nothing asked permission, so nothing moves silently.

This matters most on recompute. A Task list that changed but kept its old hours is worse than one
with no hours at all: the burndown keeps charting a plan nobody is following, and the team finds
out at the end of the sprint. So any change to the work a Story needs triggers a recompute and an
update, followed by a report of what moved.

The judgement that *does* need a person is whether the work fits — see the capacity ceiling below.

The validator still treats an unestimated item as `SKIP`, never a failure: an item nobody has
sized yet is an honest state.

## Capacity is a ceiling

A Story's Tasks are checked against **the assigned person's** hours in the **active sprint** —
their daily capacity times the days they are actually present, with weekends, team holidays and
their own leave removed, less whatever is already on their plate.

When the derived hours exceed what they have left, the run **stops before writing** and asks for a
decision: split the Story, move it to a later sprint, reassign it, or reduce the scope. The hours
are never scaled down to fit — that would misrepresent how long the work takes.

When the assignee cannot be matched to a team member, or the Story is unassigned, capacity is
unknown. That is reported plainly and the run continues; absence of data is not a failure.

`capacity --iteration <id>` reports the whole team rather than one person, for sprint-level review.
It also states how many items carry no estimate: a plan built on partial coverage is a floor, not a
total, and saying so is the difference between a useful report and a misleading one.

Capacity is read, never written. Changing capacity settings rewrites other people's sprint
configuration, which is not this plugin's business.

## Commands

```bash
bin/agile-backlog-toolkit estimate --file <path>          # suggest hours for a draft
bin/agile-backlog-toolkit estimate --points 5             # suggest hours for a point value
bin/agile-backlog-toolkit capacity --provider filesystem  # plan from local drafts
bin/agile-backlog-toolkit capacity --provider azure-devops --iteration <id> --payloads <json>
```

`capacity` exits non-zero when the sprint is overcommitted, so it works as a gate.

## Adding another backlog system

The estimation and capacity logic knows nothing about any particular tracker. A new adapter means
one module under `orchestrator_core/providers/` implementing two reads and one write-planner, plus
a line in the registry. Nothing in the estimation or capacity code changes.

## References

- `orchestrator_core/estimation/` — scales, bands, calibration
- `orchestrator_core/capacity/` — the sprint model and planner
- `orchestrator_core/providers/azure_devops/fields.py` — field reference names
- `azure-mechanics.md` — which field each process actually has
- Halstead, *Elements of Software Science* (1977) — the `T = E / 18` time formula used only as a
  retrospective cross-check against code that already exists
