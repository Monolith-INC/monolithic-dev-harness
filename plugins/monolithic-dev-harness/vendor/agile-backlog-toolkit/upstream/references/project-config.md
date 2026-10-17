# Project Configuration

Where the plugin keeps per-project settings, and how a skill fills in a value that is missing.

## The plugin owns nothing but `.agile-backlog-toolkit/`

Two locations, and they must not be confused:

```
<project>/.agile-backlog-toolkit/          plugin-owned. Created by the plugin.
├── config.json                       settings
├── estimation.json                   optional: team's points→hours bands
├── mistakes.json                     retry-loop memory
└── reports/                          validation reports

<artifacts_path>                    user-owned. NEVER created by the plugin.
                                       wherever the user says their drafts go
```

**The plugin never creates a directory structure in a project.** It does not look for one, does not
glob for one, and has no default location for a user's work products. If `artifacts_path` is unset,
local output is unavailable and the correct behaviour is to **ask** — never to invent a path.

What lives at `artifacts_path` is not the plugin's concern. A knowledge base, a docs folder, a
shared drive: it reads markdown frontmatter from it and nothing more.

## The file

`.agile-backlog-toolkit/config.json`:

```json
{
  "artifacts_path": "docs/backlog",
  "azure": {
    "org": "contoso",
    "project": "my-product",
    "team": "Developers",
    "process": "agile"
  }
}
```

`artifacts_path` may be relative to the project root or absolute. It has no default.

`org` and `project` are needed for most Azure work. `team` is required for sprint capacity, which is
team-scoped. `process` decides which fields exist — on Scrum, Original Estimate is absent and
writing it fails silently.

No secrets live here. Authentication comes from the Azure DevOps MCP server, which uses the
signed-in browser session. Commit the file so the team shares one configuration.

## Where values come from

Earlier sources win. Projects configured by earlier versions still resolve:

```
1. environment variables
     AGILE_WORKFLOW_ARTIFACTS_PATH
     AGILE_WORKFLOW_AZURE_ORG / AZURE_DEVOPS_ORG / ADO_ORG
     ...PROJECT, ...TEAM, ...PROCESS
2. .agile-backlog-toolkit/config.json          <- canonical
3. .agile-backlog-toolkit.install.json         <- install receipt
4. .mcp.json / .cursor/mcp.json         <- org, from the MCP command arguments
```

## Reading it

```bash
bin/agile-backlog-toolkit config --show
```

Prints every resolved value, where it came from, and whether the artifacts directory exists yet.
Exits non-zero when a required Azure value is missing, so it works as a precondition check.

## Filling in a missing value

Anything not captured at install time is filled the first time a skill needs it.

**For `artifacts_path`: ask the user.** There is nothing to discover — only they know where their
work should go. Ask once, then persist:

```bash
bin/agile-backlog-toolkit config --set artifacts_path=<path>
```

**For Azure values: discover, then confirm.** These are lookups, so nobody should type a slug:

| Missing | Discover with | Then |
|---|---|---|
| project | `core_list_projects` | `config --set azure.project=<name>` |
| team | `core_list_project_teams` | `config --set azure.team=<name>` |
| process | `wit_list_backlogs` — the Stories backlog column names it: `StoryPoints` → agile, `Effort` → scrum, `Size` → cmmi | `config --set azure.process=<name>` |

Present the options and let the user pick when there is more than one. Saving merges: filling in a
team does not disturb the org, and unknown keys already in the file are preserved.

## Setting it up at install time

```bash
./install.sh --azure-org <org> [--azure-project <p>] [--azure-team <t>] [--artifacts-path <path>]
```

Only `--azure-org` is required. `--artifacts-path` is optional and the installer **does not create
the directory** — it only records where the user said it should be.

## How the MCP server is launched

The installer prefers a pinned invocation — `node` against an entrypoint installed once under
`~/.local/share/azure-devops-mcp` — and falls back to `npx` when unavailable.

Pinning is better for two reasons: `npx` re-resolves the package on every start, and it is the piece
that fails when a host leaks a truncated `PATH` into stdio subprocesses. Cursor is known to do this,
so the installer also writes a wrapper that sanitises the environment first.

## References

- `orchestrator_core/project_config.py` — the resolver
- `scripts/install.py` — `write_project_config`, `azure_mcp_launch`, `scaffold_project`
- `azure-mechanics.md` — which field each process actually has
