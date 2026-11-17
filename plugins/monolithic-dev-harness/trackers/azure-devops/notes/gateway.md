# Azure DevOps through the gateway (maintainer notes)

The agent never reads this: it works through the gateway contract (`tracker_describe` and the
`tracker_*` tools). These notes are for maintainers of the Azure DevOps adapter.



The harness exposes one agent-facing integration: `workflow-integrations`. Use its provider-neutral
`tracker_*` and `scm_*` tools for every tracker and Azure Repos operation. The gateway routes these
calls to the configured adapter, which owns the native Azure DevOps MCP connection and interactive
OAuth session.

Never call `@azure-devops/mcp` tools directly, search for their host-specific names, start a second
Azure MCP server, or substitute Azure CLI, `az login`, or a PAT. This keeps authentication and
provider details behind the gateway.

Each `workflow-integrations` process owns an independent Azure MCP transport and private Unix
socket. This also separates multiple windows or host products that use the same MCP config. Local
CLI and hook readers reuse the sole live owner, or can select with `MDH_GATEWAY_HOST=claude|codex|cursor|kimi`.
If several instances are live, select both `MDH_GATEWAY_HOST` and the `MDH_GATEWAY_INSTANCE` value
from that instance's owner record under `.harness/state/gateway-owners/`; the record's `instance`
field supplies the value. For example, set both variables on a CLI or hook command:
`MDH_GATEWAY_HOST=codex MDH_GATEWAY_INSTANCE=<instance-id> harness ...`. With multiple windows of
one host product, harness CLI and hook reads cannot infer which window's MCP process to use; they
fail closed until an instance is selected. The host's own MCP tool calls remain bound to its
individual stdio gateway automatically. Stale crash records are ignored after bounded local peer
checks, and do not trigger a provider launch. Busy listeners remain candidates after a probe
timeout, so selection cannot silently move to another instance. Sockets accept only centrally
allowlisted reads, check same-user peer credentials and an owner record, and use mode 0600 inside a
mode 0700 user directory. Restart or reload the affected host to recover a dead owner.

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
| Create, update or transition a work item | `tracker_create_work_item`, `tracker_update_work_item`, `tracker_transition_work_item` |
| Read or publish harness artifacts | `tracker_list_artifacts`, `tracker_publish_artifact` |
| Link a work item to a branch or pull request | `tracker_link_development_artifact` |
| Read or create a pull request | `scm_get_pull_request`, `scm_create_pull_request` |
| Read or reply to review threads | `scm_list_review_threads`, `scm_reply_to_thread` |
| Open a thread on a file and line range, edit its first comment, or set its status | `scm_create_review_thread`, `scm_update_thread_comment`, `scm_set_thread_status` |
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

See [the gateway tool map](tool-map.md) for supported capabilities and
[the transport notes](oauth.md) for maintainers.
