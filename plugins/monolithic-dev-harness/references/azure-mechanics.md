# Azure DevOps through the harness gateway

Harness workflows access Azure DevOps only through the `workflow-integrations` MCP server. The
gateway selects the configured tracker and SCM adapters and keeps provider-specific authentication
and payloads internal.

## Supported agent operations

- Work-item reads and searches: `tracker_get_work_item`, `tracker_search_work_items`,
  `tracker_list_children`.
- Work-item creation and state transitions: `tracker_create_work_item`,
  `tracker_transition_work_item`.
- Artifact and development links: `tracker_list_artifacts`, `tracker_publish_artifact`,
  `tracker_link_development_artifact`.
- Pull requests and review threads: `scm_get_pull_request`, `scm_create_pull_request`,
  `scm_list_review_threads`, `scm_reply_to_thread`, `scm_link_work_item`.

Use the gateway tool schema for exact argument and result shapes. Work-item references are strings;
the adapter translates them into provider identifiers. A work item's parent should be supplied as
`parentRef` at creation when applicable.

## Capability limits

The gateway does not currently expose Azure attachment downloads, arbitrary field updates, backlog
metadata, pull-request diff retrieval, or raw provider queries. If a workflow requires one of those
operations, stop and report the missing gateway capability. Do not call native Azure MCP tools,
Azure CLI, direct REST APIs, or another MCP server as a fallback.

Azure-specific scheduling field names and Markdown serialization remain adapter implementation
details. User-facing workflows must rely on the provider-neutral gateway contract.
