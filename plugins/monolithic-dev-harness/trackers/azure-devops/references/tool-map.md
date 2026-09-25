# Azure DevOps MCP tool map

The current `@azure-devops/mcp` server groups operations into a few tools, each selected with an
`action` argument. Harness skills write a call as **`tool[action]`**: `wit_work_item[get]` means
"call `wit_work_item` with `action: "get"`". Add the host prefix from `SKILL.md` → *Finding the
tools*.

## Work items

| Call | Arguments that matter | Notes |
| --- | --- | --- |
| `wit_work_item[get]` | `id`, `project`, `expand: "Relations"` (or `fields: [...]`) | `expand` and `fields` are mutually exclusive |
| `wit_work_item[get_batch]` | `ids`, `project`, `fields` | parent-chain and fan-out reads |
| `wit_work_item[list_for_iteration]` | `project`, `team`, `iterationId` | existing sprint commitments |
| `wit_work_item[list_revisions]` | `workItemId`, `project` | audit and "unchanged" checks |
| `wit_work_item[get_type]` | `workItemType`, `project` | field and state metadata |
| `wit_work_item_write[create]` | `workItemType`, `project`, `fields: [{name, value, format}]` | set `format: "Markdown"` on `System.Description` |
| `wit_work_item_write[add_child]` | `parentId`, `workItemType`, `project`, `items: [{title, description, format, areaPath, iterationPath}]` | cannot set other fields; follow with `[update]` |
| `wit_work_item_write[update]` | `id`, `project`, `updates: [{op, path, value}]` | prepend `{op: "test", path: "/rev", value: <rev>}` for a safe read-modify-write |
| `wit_work_item_write[update_batch]` | `project`, `batchUpdates: [{id, op, path, value}]` | |
| `wit_work_item_link_write[link]` | `project`, `updates: [{id, linkToId, type}]` | **`type` defaults to `related`**. Always pass `type: "parent"` or `"child"` explicitly |
| `wit_work_item_link_write[unlink]` | `id`, `project`, `type` (`related`, `parent`, …) | |
| `wit_work_item_link_write[link_to_pull_request]` | `workItemId`, `projectId`, `repositoryId`, `pullRequestId` | |
| `wit_work_item_link_write[add_artifact_link]` | `workItemId`, `linkType: "Branch"`, `projectId`, `repositoryId`, `branchName` | branch and commit links |
| `wit_work_item_attachment` | `attachmentId`, `fileName`, `project`, `savePath` (relative) | single-purpose tool, no `action` |
| `wit_work_item_comment_write` | see the tool schema | |

## Backlog, iterations, capacity

| Call | Arguments that matter |
| --- | --- |
| `wit_backlog[list]` | `project`, `team`. The Stories level names the points field: `StoryPoints` (Agile), `Effort` (Scrum), `Size` (CMMI) |
| `wit_backlog[list_work_items]` | `project`, `team`, `backlogId` |
| `work[list_team_iterations]` | `project`, `team`, `timeframe: "current"` |
| `work[get_team_settings]` | `project`, `team` |
| `work[get_team_capacity]` | `project`, `team`, `iterationId` |

## Repos and pull requests

| Call | Arguments that matter |
| --- | --- |
| `repo_pull_request_write[create]` | `repositoryId`, `project`, `sourceRefName`, `targetRefName`, `title`, `description` (≤ 4000 chars), `isDraft`, `workItems` (space-separated ids) |
| `repo_pull_request_write[update]` | `repositoryId`, `pullRequestId`, fields to change |
| `repo_pull_request_thread_write` | see the tool schema; posting is guarded by the poster hook |

## Legacy names

Older skill text and older server builds used one tool per operation. If you meet one of these
names, use the replacement:

| Legacy | Current |
| --- | --- |
| `wit_get_work_item` | `wit_work_item[get]` |
| `wit_get_work_items_batch_by_ids` | `wit_work_item[get_batch]` |
| `wit_get_work_items_for_iteration` | `wit_work_item[list_for_iteration]` |
| `wit_create_work_item` | `wit_work_item_write[create]` |
| `wit_update_work_item` | `wit_work_item_write[update]` |
| `wit_add_child_work_items` | `wit_work_item_write[add_child]` |
| `wit_work_items_link` | `wit_work_item_link_write[link]` |
| `wit_work_item_unlink` | `wit_work_item_link_write[unlink]` |
| `wit_get_work_item_attachment` | `wit_work_item_attachment` |
| `wit_list_backlogs` | `wit_backlog[list]` |
| `work_list_team_iterations` | `work[list_team_iterations]` |
| `work_get_team_settings` | `work[get_team_settings]` |
| `work_get_team_capacity` | `work[get_team_capacity]` |
