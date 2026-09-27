# Project Configuration

Where the backlog stage finds its settings, and how a skill fills in a value that is missing.

## One settings file, two locations to keep apart

Every setting lives in the repository's `.harness/settings.json`, the harness's only settings
file (schema: `config/settings.schema.json`). People edit it; the harness only reads it.

```text
<project>/.harness/settings.json    the settings (human-owned)
<project>/.harness/backlog/         plugin-owned. Created by the plugin.
|-- estimation.json                  optional: the team's points-to-hours bands
|-- mistakes.json                    retry-loop memory
`-- reports/                         validation reports

<artifacts_path>                     user-owned. NEVER created by the plugin:
                                     wherever the user says their drafts go
```

**The plugin never creates a directory structure in a project.** It does not look for one and
has no default location for a user's work products. If `artifacts_path` is unset, local output is
unavailable and the correct behaviour is to **ask**, never to invent a path.

## What the backlog stage reads

```json
{
  "tracker": {
    "name": "azure-devops",
    "values": {"organization": "contoso", "project": "my-product", "team": "Developers", "process": "agile"}
  },
  "artifacts_path": "docs/backlog"
}
```

- `artifacts_path`: relative to the project root or absolute; `~` expands. No default.
- `tracker.values`: the values the selected tracker's `tracker.json` declares. For Azure DevOps,
  `organization` and `project` are needed for most work, `team` for sprint capacity (it is
  team-scoped), and `process` decides which fields exist (on Scrum, Original Estimate is absent
  and writing it fails silently). For Linear, `team`.

No secrets live here: authentication comes from the provider's MCP server and its sign-in.
Commit the file so the team shares one configuration.

## Reading it

```bash
bin/agile-backlog-toolkit config --show
```

Prints every value, the file it came from, and whether the artifacts directory exists yet. Exits
non-zero when a required Azure value is missing, so it works as a precondition check.

## Filling in a missing value

The harness never writes the settings file, and neither may the agent. When a value is missing:

**For `artifacts_path`: ask the user** where their work should go, and ask them to add it to
`.harness/settings.json`.

**For Azure values: discover, then propose.** These are lookups, so nobody should type a slug:

| Missing | Discover with |
|---|---|
| project | `core_list_projects` |
| team | `core_list_project_teams` |
| process | `wit_backlog[list]`: the Stories backlog column names it (`StoryPoints` agile, `Effort` scrum, `Size` cmmi) |

Present the options, let the user pick, and give them the exact `tracker.values` entry to add.

## Setting it up

`harness bootstrap --settings-from <file>` checks a settings file and copies it into the
repository once. It does not create the artifacts directory; it only records where it should be.

## References

- `runtime/orchestrator_core/project_config.py`: the backlog view of the settings
- `scripts/harness/settings.py`: the loader, and the defaults for omitted sections
- `azure-mechanics.md`: which field each process actually has
