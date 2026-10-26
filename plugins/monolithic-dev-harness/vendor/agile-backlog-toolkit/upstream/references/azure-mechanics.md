# Azure DevOps Mechanics

The exact MCP calls and the traps that bite if you skip them. These are invariant — not seams.

## Before the first Azure call: know the project

Org, project, team, and process live in `.agile-backlog-toolkit/config.json`. Read them with:

```bash
bin/agile-backlog-toolkit config --show      # exits non-zero when something required is missing
```

If a value is missing, **discover it rather than asking the user to type a slug** — then persist it
so it is never asked again:

| Missing | Discover with | Then |
|---|---|---|
| project | `core_list_projects` | `config --set azure.project=<name>` |
| team | `core_list_project_teams` | `config --set azure.team=<name>` |
| process | `wit_list_backlogs` — the Stories backlog column names it: `StoryPoints` → agile, `Effort` → scrum, `Size` → cmmi | `config --set azure.process=<name>` |

Present the options and let the user pick when there is more than one. Full rules in
`project-config.md`.

## Read a work item (ingest)

Use `wit_get_work_item(id=<id>, expand=relations)` to load fields and relations in one call.

**URL → id:** Azure work-item URLs end with `/_workitems/edit/{id}` or `/_workitems/view/{id}`.
Extract the numeric `{id}` segment.

**Attachments:** With `expand=relations`, each `AttachedFile` relation includes `attributes.name`
and a `url` ending in the attachment GUID. Download via `wit_get_work_item_attachment` when the MCP
server supports it; otherwise REST:

```
GET https://dev.azure.com/{org}/{project}/_apis/wit/attachments/{attachmentId}?fileName={fileName}&download=true&api-version=7.1
```

Auth: MCP credentials, or `AZURE_DEVOPS_EXT_PAT` / `ADO_PAT` (Basic, empty username), or `az login`.

**Description references:** Parse `System.Description` for markdown links, bare URLs, filenames that
match attachment names, and local and repo paths. Fetch those sources into supplementary context before
enrichment — see `enrich-work-item/references/azure-ingest.md` for the full bundle rules.

## Create a Story

Use `wit_create_work_item` (project = host's Azure project; repo context as needed):
- `workItemType: "User Story"` (or Bug/Tech Debt/Spike).
- **Description in Markdown format** — Markdown descriptions render fenced ASCII diagrams. Plain-text
  format mangles them.
- Set Story Points and tags at creation when supported.

## Link to parent — TWO GOTCHAS

### Gotcha 1 — always pass an explicit `type`
`wit_work_items_link` **defaults to `type: "related"`.** Omitting `type` silently creates a wrong
**Related** link instead of a parent link. ALWAYS pass `type: "parent"` explicitly.

### Gotcha 2 — a Story's parent is its FEATURE, not the Epic
Link the Story to the **Feature id**, never the Epic id. Skipping the Feature level breaks the
Epic→Feature→Story chain. If you have been handling the Epic id all session, do not reflexively reuse
it here — the parent is the Feature.

Fix sequence if a wrong link was made:
```
wit_work_item_unlink   id=<story> type=related      # remove the stray Related link
wit_work_item_unlink   id=<story> type=parent       # remove a wrong parent (e.g. → Epic)
wit_work_items_link    id=<story> linkToId=<feature> type=parent
```

## Scheduling fields (estimation and capacity)

Azure keeps two independent estimation tiers. Points on the Story feed velocity and forecasting;
hours on the Task feed capacity bars and the burndown. Neither reads the other.

| Field | Reference name | Notes |
|---|---|---|
| Story Points | `Microsoft.VSTS.Scheduling.StoryPoints` | Agile process only |
| Effort | `Microsoft.VSTS.Scheduling.Effort` | Scrum equivalent |
| Size | `Microsoft.VSTS.Scheduling.Size` | CMMI equivalent |
| Remaining Work | `Microsoft.VSTS.Scheduling.RemainingWork` | **Drives capacity and burndown.** Every process has it |
| Original Estimate | `Microsoft.VSTS.Scheduling.OriginalEstimate` | **Absent on Scrum** — guard before writing |
| Completed Work | `Microsoft.VSTS.Scheduling.CompletedWork` | Absent on Scrum |
| Activity | `Microsoft.VSTS.Common.Activity` | `Discipline` in CMMI; allowed values are per-project |

**A Task with no `RemainingWork` is invisible to the sprint.** It appears on the board and in the
hierarchy, but contributes nothing to the capacity bar or the burndown line — the sprint reads as
empty while looking healthy.

**Hours are derived, applied, and reported.** They come from the Story's points, split across its
Tasks — so they are written without asking, and every figure set or changed is named in the run
summary. The one thing that stops a write is the capacity ceiling: if the total exceeds the
assignee's remaining hours in the active sprint, STOP and ask. See
`orchestrator_core/estimation/breakdown.py`, and take field names from
`orchestrator_core/providers/azure_devops/fields.py` rather than retyping them.

Capacity itself lives under a different API area from `wit_*` and is read-only for these skills:

```
GET https://dev.azure.com/{org}/{project}/{team}/_apis/work/teamsettings/iterations/{iterationId}/capacities?api-version=7.1
```

Never PUT capacity — that rewrites other people's sprint configuration.

## Rendering rules

- Work-item **description** bodies: **ASCII diagrams only.** Mermaid does NOT render in work-item
  descriptions (it renders only in the Wiki). Inline SVG is unsupported.
- Keep parentheses inside ASCII diagram boxes; outside diagrams, prefer one sentence per line.

## Verify (read-back, every time)
After creating + linking, read the item back and assert `System.Parent == <feature id>` and that the
sole hierarchy relation is Parent → the Feature. A failed assertion STOPS the run.
