# Agent-facing integration tool map

Agents interact with Azure DevOps only through `workflow-integrations`. The gateway translates
these provider-neutral operations into native Azure MCP calls internally.

| Harness operation | Gateway tool | Notes |
| --- | --- | --- |
| Describe tracker capabilities | `tracker_describe` | Returns configured types, states, identifiers, and hierarchy. |
| Read a work item | `tracker_get_work_item` | Supply the item reference as `ref`. |
| Search work items | `tracker_search_work_items` | Supply `query`; use `cursor` for pagination when returned. |
| Read child items | `tracker_list_children` | Supply the parent `ref`. |
| Create a work item | `tracker_create_work_item` | Use harness kinds and optional `parentRef`. |
| Update a work item | `tracker_update_work_item` | Supply `ref` and only the fields to change: `title`, `description` (the whole refined body), `storyPoints`, `hours` and `firstEstimate` (a Task's effort), `assignee`, `iteration`. The item is read back. |
| Transition a work item | `tracker_transition_work_item` | Use a harness logical state. |
| List or publish workflow artifacts | `tracker_list_artifacts`, `tracker_publish_artifact` | Publishing is revision-aware and idempotent. |
| Link branch or PR | `tracker_link_development_artifact` | Supply work item `ref`, artifact `url`, and optional `type`. |
| Read a pull request | `scm_get_pull_request` | Supply a provider-neutral PR `ref`. |
| Create a pull request | `scm_create_pull_request` | Harness policy requires a draft and workflow approval. |
| Read or reply to review threads | `scm_list_review_threads`, `scm_reply_to_thread` | Replies are subject to harness posting policy. |
| Open a thread on a file and line range, edit its first comment, or set its status | `scm_create_review_thread`, `scm_update_thread_comment`, `scm_set_thread_status` | Subject to the same posting policy as replies. |
| Link a PR to a work item | `scm_link_work_item` | Supply both provider-neutral references. |

Use the tool schemas returned by the gateway for exact input shapes. Native Azure MCP tool names,
action arguments, and payloads are implementation details and are not part of the agent interface.
