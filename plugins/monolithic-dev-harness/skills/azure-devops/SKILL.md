---
name: azure-devops
description: Use when a harness workflow needs Azure DevOps work items, pull requests, branches, or review threads. All agent operations go through the provider-neutral workflow-integrations tools; the native Azure MCP is an internal gateway dependency and must not be called directly.
---

# Azure DevOps through the harness

The harness exposes one agent-facing integration: `workflow-integrations`. Use its provider-neutral
`tracker_*` and `scm_*` tools for every tracker and Azure Repos operation. The gateway routes these
calls to the configured adapter, which owns the native Azure DevOps MCP connection and interactive
OAuth session.

Never call `@azure-devops/mcp` tools directly, search for their host-specific names, start a second
Azure MCP server, or substitute Azure CLI, `az login`, or a PAT. This keeps authentication and
provider details behind the gateway.

The repository's `.harness/settings.json` is the source of organization, project, team, and
repository selection (`tracker.values` and `scm.values`). Ask the user to configure missing values
through the harness bootstrap or tracker onboarding flow. Do not infer an organization from the
machine environment.

## Gateway operations

| Need | Agent-facing tool |
| --- | --- |
| Describe tracker fields, states, and hierarchy | `tracker_describe` |
| Read or search work items | `tracker_get_work_item`, `tracker_search_work_items` |
| Read child work items | `tracker_list_children` |
| Create or transition a work item | `tracker_create_work_item`, `tracker_transition_work_item` |
| Read or publish harness artifacts | `tracker_list_artifacts`, `tracker_publish_artifact` |
| Link a work item to a branch or pull request | `tracker_link_development_artifact` |
| Read or create a pull request | `scm_get_pull_request`, `scm_create_pull_request` |
| Read or reply to review threads | `scm_list_review_threads`, `scm_reply_to_thread` |
| Link a work item to a pull request | `scm_link_work_item` |

Use the tool schemas as the source of argument names. Work item references are provider-neutral
strings; do not construct Azure-specific request payloads. Pull request creation is constrained by
the harness workflow and its approval gates.

## Authentication and recovery

The gateway reuses its persistent Azure MCP transport across calls. Make one targeted read-only
gateway call to verify access, such as `tracker_describe` followed by `tracker_get_work_item` for a
known reference, or `scm_get_pull_request` for a known PR. Do not run the standalone Azure health
check as part of a workflow; it starts another provider process and can trigger another OAuth
round trip.

If a gateway call times out or its transport closes, stop retrying and report the failure. Do not
spawn another Azure process. A stale gateway/provider process should be handled by reloading the
host or using the harness's documented recovery procedure; never terminate a process based only on
its name or count. Never log or store tokens, cookies, or credentials.

See [the gateway tool map](references/tool-map.md) for supported capabilities and
[the transport notes](references/oauth.md) for maintainers.
