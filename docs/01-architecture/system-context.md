---
title: System Context
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# System Context

## Context

The harness runs inside a developer's agent host and acts on the team's Azure DevOps organization
with the developer's own identity. It has no server of its own.

```text
                +--------------------+
                |     Developer      |
                | prompts, approvals |
                +---------+----------+
                          |
                          v
+-------------------------------------------------------+
|  Agent host: Claude Code or Cursor                    |
|  + monolithic-dev-harness plugin                      |
|    skills, agents, hook runtime, 4 MCP servers        |
+----+-------------------+--------------------+---------+
     |                   |                    |
     v                   v                    v
+-----------+   +-----------------+   +------------------+
| Repository|   | Azure DevOps    |   | Browser          |
| git, code,|   | Boards + Repos  |   | interactive OAuth|
| .harness/ |   | (developer's    |   | for the MCP      |
|           |   |  identity)      |   | server           |
+-----------+   +-----------------+   +------------------+
```

## Authority Boundaries

| Actor | May | May not |
| --- | --- | --- |
| Developer | approve batches, record manual checks, edit the policy, publish and merge pull requests | — |
| Agent | read anything; edit the working tree; run checks; commit within the rules; write to Azure DevOps inside an approval window | open approval windows, write approval or manual-check records, edit the policy, touch protected items, publish or vote on pull requests |
| Hook runtime | allow or deny a tool call | perform the call itself |
| Orchestrators | validate and critique skill inputs and outputs | call a provider |

## Components

External systems: the agent host, the repository, Azure DevOps (Boards and Repos), and the
browser that completes OAuth for the `@azure-devops/mcp` server. Internal components are described
in [architecture.md](architecture.md).

## Runtime State Machine

Not applicable at the system level; see [architecture.md](architecture.md#runtime-state-machine).

## Durable State

Durable state lives in two places only: Azure DevOps (work items, links, pull requests,
artifacts) and the repository (`.harness/policy.json` committed; `.harness/state/` ignored by git).

## Contracts / Schemas

- The repository policy: `plugins/monolithic-dev-harness/config/policy.schema.json`.
- Host hook payloads: Claude `PreToolUse` / `UserPromptSubmit`; Cursor `preToolUse`,
  `beforeShellExecution`, `beforeMCPExecution`, `beforeSubmitPrompt`.
- Azure DevOps calls: the current `@azure-devops/mcp` tools (`skills/azure-devops/references/tool-map.md`).

## Host Differences

See [architecture.md](architecture.md#host-differences).

## Failure Modes

If Azure DevOps or OAuth is unavailable, reads fail and writes are never attempted; the agent
reports and stops. If the hook runtime cannot run, writes are denied and reads continue.

## Security Invariants

See [../05-security/security.md](../05-security/security.md).

## Validation Gates

See [architecture.md](architecture.md#validation-gates).
