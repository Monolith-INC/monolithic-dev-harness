# Project Configuration

Where the backlog stage finds its settings, and how a skill fills in a value that is missing.

## One settings file, two locations to keep apart

Every setting lives in the repository's `.harness/settings.json`, the harness's only settings
file (schema: `config/settings.schema.json`). People edit it; the harness changes
only its `tracker` section, when the user chooses a tracker.

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
- `tracker.values`: the values the selected tracker's `tracker.json` declares under `settings`,
  each with what it is for and whether it is required. `harness bootstrap --inspect` lists them.

No secrets live here: authentication comes from the provider's MCP server and its sign-in.
Commit the file so the team shares one configuration.

## Reading it

`harness bootstrap --inspect` prints the settings, the artifacts path, the selected tracker, and
what is missing; `harness doctor` says whether the tracker can be used.

## Filling in a missing value

The agent never writes the settings file. When a value is missing, run the bootstrap skill: it
asks only for what is missing, discovers the tracker's values through its onboarding where it can,
and applies the settings the user reviewed.

## Setting it up

`harness bootstrap --settings-from <file>` checks a settings file and copies it into the
repository once. It does not create the artifacts directory; it only records where it should be.

## References

- `runtime/orchestrator_core/project_config.py`: the backlog view of the settings
- `scripts/harness/settings.py`: the loader, and the defaults for omitted sections
