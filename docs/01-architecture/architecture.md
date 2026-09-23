---
title: Architecture
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Architecture

## Context

A delivery process built from prompts alone cannot guarantee its own rules. The harness separates
what the model decides (skills) from what a deterministic runtime enforces (hooks, orchestrator
contracts, evidence), and routes every provider call through a place the runtime can see.

## Authority Boundaries

- **Skills** decide *how* to do a stage. They cannot grant themselves permissions.
- **Orchestrators** decide whether a skill's input and output satisfy its contract and when to stop
  retrying. They never call Azure DevOps.
- **The hook runtime** decides whether a tool call may run. It never performs the call.
- **The developer's prompt** is the only source of approval windows and manual-check records.

## Components

```text
+--------------------------- plugin -----------------------------+
|                                                                |
|  skills/ (45)          agents/            hooks/               |
|  backlog, delivery,    thermo-*           hooks.json (Claude)  |
|  execution, review,    reviewer           cursor.hooks.json    |
|  conductors            subagents          (Cursor)             |
|                                               |                |
|                                               v                |
|  scripts/harness/  <-- hook.py: rules, then workflow policy    |
|    rules.py  state.py  gitstate.py  config.py  globs.py        |
|    checks.py  review_verdict.py  bootstrap.py  cli.py          |
|                                                                |
|  scripts/  (workflow runtime)       runtime/orchestrator_core/ |
|    policy/  host_adapters/            backlog orchestrator:    |
|    orchestrator/  integrations/       validation, estimation,  |
|    hook_runtime.py                    capacity, MCP + CLI      |
|                                                                |
|  .mcp.json / cursor.mcp.json:                                  |
|    backlog-orchestrator  workflow-orchestrator                 |
|    workflow-integrations  azure-devops                         |
+----------------------------------------------------------------+
```

| Component | Responsibility |
| --- | --- |
| Skills | Stage procedures. Conductors (`harness`, `implement-story`, `review`) sequence the others. |
| Reviewer agents | `thermo-nuclear-review-subagent`, `thermo-nuclear-code-quality-review-subagent`; no file-edit tools, pinned to `opus`. |
| `scripts/harness/hook.py` | Single hook entry point for both hosts; runs the harness rules, then delegates to the workflow policy runtime. |
| `scripts/harness/rules.py` | The eight named rules. |
| `scripts/harness/state.py` | Evidence store under `.harness/state/`. |
| `scripts/harness/questions.py` | Questions to the user: the plain-language check before they are shown, and approval by click. |
| `scripts/hook_runtime.py`, `scripts/policy/` | Workflow policy: branch key, state, spec prerequisites, completion evidence, protected branches, stack merges. |
| `workflow-orchestrator` (`scripts/orchestrator/`) | Delivery skills as MCP tools: manifest contracts, event-sourced task queue, Actor-Critic retries, failure taxonomy. |
| `backlog-orchestrator` (`runtime/orchestrator_core/`) | Backlog skills as MCP tools plus a CLI: draft validation, quality gates, estimation, capacity. |
| `workflow-integrations` (`scripts/integrations/`) | Tracker and SCM adapters behind one contract (Azure Boards, Azure Repos; others retained but unused). |
| `azure-devops` | The `@azure-devops/mcp` server, started with the organization from `AZURE_DEVOPS_ORG`. |

## Runtime State Machine

Per tool call:

```text
received --> governed? --no--> allowed
                |
               yes
                v
         harness rules (in order)
         human-owned -> protected-items -> draft-reviewed-prs
         -> approval-required -> generated-files -> commit rules
                |                                   |
              pass                                 deny --> denied (rule + fix)
                v
         workflow policy (Claude, Cursor preToolUse)
                |
          pass / deny
                v
         allowed  --> if it used an approval window, the write is logged to it
```

Per orchestrated skill call (workflow orchestrator):

```text
spawned -> inputs validated -> running --success--> completed
                                  |
                          critiques / transient failure
                                  v
                               ready (retry < max) --> running
                                  |
                   same output + same critiques twice, or
                   deterministic / fatal failure, or max reached
                                  v
                               stopped (state reported)
```

## Durable State

| State | Location | Written by | Lifetime |
| --- | --- | --- | --- |
| Policy | `.harness/policy.json` (committed) | bootstrap or a person | until edited |
| Approval windows | `.harness/state/approvals/` | prompt hook | expires (default 20 min) |
| Manual checks | `.harness/state/manual/` | prompt hook | valid for one index tree |
| Check evidence | `.harness/state/checks/` | `checks.py` | valid for one tree |
| Review verdicts | `.harness/state/review/` | `review_verdict.py` | valid for one commit |
| Tracker binding | `.harness/integrations.json` | bootstrap | until reconfigured |
| Backlog config | `.harness/backlog/config.json` | bootstrap | until reconfigured |
| Review config | `.harness/review/sources.json` | `review-setup` | until reconfigured |

Details: [data-model.md](data-model.md).

## Contracts / Schemas

- `config/policy.schema.json` — the repository policy.
- `skills/*/manifest.json` — orchestrated skills' input and output schemas.
- `common/artifact-schema.json` — backlog draft frontmatter.
- Command contracts: [../02-design/api.md](../02-design/api.md).

## Host Differences

| Aspect | Claude Code | Cursor |
| --- | --- | --- |
| Hook events | `PreToolUse` (matcher `Bash\|Write\|Edit\|MultiEdit\|NotebookEdit\|mcp__.*`), `UserPromptSubmit` | `preToolUse`, `beforeShellExecution`, `beforeMCPExecution`, `beforeSubmitPrompt` |
| Deny output | `hookSpecificOutput.permissionDecision: deny` | `{"permission": "deny", "agent_message", "user_message"}` |
| MCP tool names | `mcp__plugin_monolithic-dev-harness_<server>__<tool>` | bare tool names under the server |
| Organization | `${AZURE_DEVOPS_ORG}` from the environment (the installer writes it to Claude settings) | the installer pins it into `cursor.mcp.json` |
| Status | verified in a sandboxed profile | load not yet observed in a live Cursor session |

## Failure Modes

| Failure | Behavior |
| --- | --- |
| Policy file invalid | write-class calls denied (`harness-error`), reads allowed |
| Workflow runtime import or run fails | write-class calls denied, reads allowed |
| Tracker configuration missing | workflow policy denies governed writes until bootstrap runs |
| git unavailable | commit and PR rules deny |
| Approval window expired | tracker/SCM writes denied until a new approval |
| Azure DevOps unreachable | the call fails; nothing is retried in a loop (see the runbook) |

## Security Invariants

- No approval window exists unless the user's own prompt created it.
- No write, link, or child ever touches a protected work item.
- No pull request is created non-draft or without a `ready` verdict for its HEAD.
- Rules that cannot run never allow a write.

See [../05-security/security.md](../05-security/security.md).

## Validation Gates

- `ruff check` and `ruff format --check` clean.
- Backlog, delivery, and harness suites green on Python 3.10 and 3.12.
- `scripts/check_versions.py` agrees across every version source.
- The built release installs into a sandboxed Claude Code profile in CI and reports the plugin as
  enabled.
