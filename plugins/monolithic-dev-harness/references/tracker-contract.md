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
| `planning` | the replies sprint planning reads (`replies[].key`), and how to fetch each (`description`) |
| `text_format` | markdown, html, or plain, for descriptions and comments |

Use the harness kinds and states with the gateway (`tracker_create_work_item`,
`tracker_transition_work_item`); the adapter maps them. Show people the provider's own names
from `kinds` and `states`. Azure-specific instructions apply only when the active tracker is
`azure-devops`; otherwise use the gateway operations.

When `mentions_link` is true, never write a protected item's id in a form listed in `mention`:
name it in plain words instead, for example "Idea 4007".
