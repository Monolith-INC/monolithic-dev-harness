# The active tracker

The repository selects one tracker in `.harness/settings.json` (`tracker.name`). Its folder,
`trackers/<name>/` in the plugin or `.harness/trackers/<name>/` for an onboarded one, is the only
definition of that tracker: `tracker.json` says what it is, `adapter.py` how to talk to it.

Before choosing a hierarchy, a destination, a provider call, or an id format, call
`tracker_describe`. Its answer is that `tracker.json`, and it is authoritative for:

| Field | What it decides |
|-------|-----------------|
| `kinds` | the provider type for each harness kind: epic, feature, user_story, task, bug |
| `artifacts` | the provider types and which may contain which (the hierarchy to draft) |
| `states` | the provider state for each harness state: backlog, ready, in_progress, done, canceled |
| `ids` | how an id looks (`pattern`), how a branch carries it (`branch_key`), which text links it (`mention`, `mentions_link`) |
| `writes` | the host tools that change the tracker; each needs an approval window |
| `optional` | operations beyond the base surface this tracker offers (`remove_artifact`); its tools appear only then |
| `text_format` | markdown, html, or plain, for descriptions and comments |

Use the harness kinds and states with the gateway (`tracker_create_work_item`,
`tracker_update_work_item`, `tracker_transition_work_item`); the adapter maps them.
`tracker_update_work_item` changes only the fields it names (title, description, story points, a
Task's hours, assignee, sprint, `parentRef` to move it under another parent, `tags` as the whole
tag list, `priority` from 1 urgent to 4 low) and reads the item back; a tracker that keeps no hours
refuses a change of hours. Ask the harness for sprints, never the tracker's own tools:
`tracker_current_sprint` gives the running sprint and the `path` an item's `iteration` takes to
join it, `tracker_sprint_items` its items, `tracker_sprint_capacity` its team and capacity.
`tracker_revise_artifact` rewrites a published artifact in place; `tracker_remove_artifact` is
offered only by trackers that can remove one. Show people the provider's own names
from `kinds` and `states`. Nothing about a particular tracker is part of the workflow: what one
tracker needs beyond this contract lives in its adapter.

When `mentions_link` is true, never write a protected item's id in a form listed in `mention`:
name it in plain words instead, for example "Idea 4007".
