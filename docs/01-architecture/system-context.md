---
title: System Context
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# System Context

## Context

The harness runs inside a developer's agent host and acts on the team's tracker and repository host
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
| Repository|   | Tracker + SCM   |   | Browser          |
| git, code,|   | Azure DevOps,   |   | interactive OAuth|
| .harness/ |   | Linear, GitHub  |   | for the MCP      |
|           |   | (developer's id)|   | servers          |
+-----------+   +-----------------+   +------------------+
```

## Authority Boundaries

| Actor | May | May not |
| --- | --- | --- |
| Developer | approve batches, record manual checks, trust onboarded trackers, edit the settings, publish and merge pull requests | — |
| Agent | read anything; edit the working tree; run checks; start and change sessions through `harness session`; stage trackers for review; commit within the rules; write to the tracker inside an approval window | open approval windows, write approval, manual-check, session, adoption, or trust records directly, trust a tracker, edit the settings, touch protected items, publish or vote on pull requests |
| Hook runtime | allow or deny a tool call | perform the call itself |
| Orchestrators | validate and critique skill inputs and outputs | call a provider |

## Components

External systems: the agent host, the repository, the selected tracker (Azure DevOps Boards,
Linear, an onboarded provider, or none for the local tracker), the SCM (Azure Repos or GitHub), and
the browser that completes OAuth for the providers' MCP servers. Internal components are described
in [architecture.md](architecture.md).

## Runtime State Machine

Not applicable at the system level; see [architecture.md](architecture.md#runtime-state-machine).

## Durable State

Durable state lives in two places only: the tracker and SCM (work items, links, pull requests,
artifacts) and the repository (`.harness/settings.json`, tracker folders, and local tracker records
committed; `.harness/state/` ignored by git).

## Contracts / Schemas

- The repository settings: `plugins/monolithic-dev-harness/config/settings.schema.json`.
- The tracker contract: `plugins/monolithic-dev-harness/config/tracker.schema.json` and
  `plugins/monolithic-dev-harness/scripts/integrations/contracts.py`.
- The subagent contract: `plugins/monolithic-dev-harness/config/host.schema.json`,
  `plugins/monolithic-dev-harness/hosts/*.json`, and
  `plugins/monolithic-dev-harness/scripts/host_adapters/subagents.py`.
- Host hook payloads: Claude `PreToolUse` / `UserPromptSubmit`; Cursor `preToolUse`,
  `beforeShellExecution`, `beforeMCPExecution`, `beforeSubmitPrompt`.
- Azure DevOps calls: provider-neutral `tracker_*` and `scm_*` tools from `workflow-integrations` (`skills/azure-devops/references/tool-map.md`).

## Host Differences

See [architecture.md](architecture.md#host-differences).

## Failure Modes

If the tracker or OAuth is unavailable, reads fail and writes are never attempted; the agent
reports and stops. If the hook runtime cannot run, writes are denied and reads continue.

## Security Invariants

See [../05-security/security.md](../05-security/security.md).

## Validation Gates

See [architecture.md](architecture.md#validation-gates).
