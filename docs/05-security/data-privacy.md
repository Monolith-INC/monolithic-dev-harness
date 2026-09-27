---
title: Data Privacy
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Data Privacy

## Scope

What data the harness reads, stores, and sends.

## Assets / Authority

| Data | Read from | Stored by the harness | Sent to |
| --- | --- | --- | --- |
| Work item content | Azure DevOps | local drafts under `backlog.artifacts_path` | the model provider (as part of the agent's context) |
| Source code | the repository | nothing new | the model provider (as part of the agent's context) |
| Approval prompts | the developer | first 500 characters of a manual-check prompt, in `.harness/state/manual/` | nowhere |
| Tool calls | the host | tool name and time for writes inside an approval window | nowhere |
| Credentials | — | none (OAuth tokens stay in the provider MCP server's process memory or its own sign-in cache) | the tracker and SCM providers only |

## Trust Boundaries

Everything the agent reads may be sent to the model provider configured in the host. The harness
adds no other destination.

## Role Permissions

Not applicable.

## Threats

Personal data inside work items or code reaches the model provider through the host, as with any
coding agent.

## Controls

- No telemetry or external calls from the harness itself.
- `.harness/state/` is git-ignored, so approval and evidence records are not committed.
- Skills and the Azure DevOps skill forbid logging tokens, cookies, or tenant ids.

## Host Enforcement Differences

None.

## Fail-closed Behavior

Not applicable.

## Supply-chain Validation

See [security.md](security.md#supply-chain-validation).

## Residual Risks

Draft files under the artifacts path may contain work item text; they live in the repository and
follow its access rules.
