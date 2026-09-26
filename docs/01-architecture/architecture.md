---
title: Architecture
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Architecture

## Context

A delivery process built from prompts alone cannot guarantee its own rules. The harness separates
what the model decides (skills) from what a deterministic runtime enforces (hooks, orchestrator
contracts, evidence), and routes every provider call through a place the runtime can see.

## Authority Boundaries

- **Skills** decide *how* to do a stage. They cannot grant themselves permissions.
- **Orchestrators** decide whether a skill's input and output satisfy its contract and when to stop
  retrying. They never call a tracker.
- **Tracker folders** decide what a tracker is and how to talk to it. They cannot relax a rule:
  the rules read their declarations, and an onboarded folder counts only while the user trusts it.
- **People** own `.harness/settings.json`; the harness only reads it.
- **The hook runtime** decides whether a tool call may run. It never performs the call.
- **The developer's prompt** is the only source of approval windows, manual-check records, and
  tracker trust.

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
|    rules.py  tracker_policy.py  settings.py  sessions.py       |
|    state.py  gitstate.py  globs.py  checks.py  bootstrap.py    |
|    review_verdict.py  cli.py                                   |
|                                                                |
|  scripts/core/  result.py (Ok/Err)  schema.py (stdlib checker) |
|                                                                |
|  scripts/integrations/   contracts  registry  trust  gateway   |
|    transport  scm  artifacts  branches  onboarding             |
|  trackers/<name>/        tracker.json + adapter.py             |
|    azure-devops  linear  local                                 |
|                                                                |
|  scripts/  (workflow runtime)       runtime/orchestrator_core/ |
|    policy/  host_adapters/            backlog orchestrator:    |
|    orchestrator/  hook_runtime.py     validation, estimation,  |
|                                       capacity, MCP + CLI      |
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
| `scripts/harness/rules.py` | The nine named rules. |
| `scripts/harness/settings.py` | Reads `.harness/settings.json` once per process into a value nothing can change; holds the defaults for omitted sections. |
| `scripts/harness/tracker_policy.py` | What the rules know about trackers, built once per call from every usable tracker folder. |
| `scripts/harness/sessions.py` | Binds a work item to one checkout; the workflow policy reads the active session. |
| `scripts/core/` | `Ok`/`Err` values for every step that can fail, and the standard-library JSON Schema checker. |
| `scripts/harness/state.py` | Evidence store under `.harness/state/`. |
| `scripts/harness/questions.py` | Questions to the user: the plain-language check before they are shown, and approval by click. |
| `scripts/hook_runtime.py`, `scripts/policy/` | Workflow policy: an active session, the branch convention, the session item's state, spec prerequisites, completion evidence, protected branches, stack merges. |
| `workflow-orchestrator` (`scripts/orchestrator/`) | Delivery skills as MCP tools: manifest contracts, event-sourced task queue, Actor-Critic retries, failure taxonomy. |
| `backlog-orchestrator` (`runtime/orchestrator_core/`) | Backlog skills as MCP tools plus a CLI: draft validation, quality gates, estimation, capacity. |
| `workflow-integrations` (`scripts/integrations/`) | The gateway: provider-neutral tools dispatched to the selected tracker's adapter and the SCM adapter (GitHub, Azure Repos). |
| `scripts/integrations/registry.py` | Finds tracker folders, checks each against the contract on its own, resolves the selected one (not configured, active, or invalid), and loads its adapter. |
| `trackers/<name>/` | One tracker each: `tracker.json` (what it is) and `adapter.py` (translation only). Shipped: Azure DevOps, Linear, local. |
| `azure-devops` | The `@azure-devops/mcp` server registered with the host, started with the organization from `AZURE_DEVOPS_ORG` (the installer sets it). The gateway starts its own copy with the settings' organization. |

## Runtime State Machine

Per tool call:

```text
received --> governed? --no--> allowed
                |
               yes
                v
         settings readable? --no--> write-class denied, reads allowed
                |
               yes: build the tracker policy once
                v
         harness rules (in order)
         human-owned -> tracker-invalid -> protected-items
         -> draft-reviewed-prs -> history-preserved
         -> approval-required -> generated-files -> commit rules
                |                                   |
              pass                                 deny --> denied (rule + fix)
                v
         workflow policy (Claude, Cursor preToolUse):
         active session -> branch convention -> item in progress
         -> spec accepted -> completion evidence
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
| Settings | `.harness/settings.json` (committed) | a person (bootstrap copies it once) | until edited |
| Onboarded trackers | `.harness/trackers/<name>/` (committed) | `harness tracker stage` | until edited, which drops trust |
| Tracker trust | `.harness/state/trackers/` | prompt hook | until the folder changes or is untrusted |
| Sessions | `.harness/state/sessions/` | `harness session` | until closed |
| Tracking mode | `.harness/state/tracking.json` | gateway skip/resume (approved) | until changed |
| Approval windows | `.harness/state/approvals/` | prompt and answer hooks | expires (default 20 min) |
| Manual checks | `.harness/state/manual/` | prompt hook | valid for one index tree |
| Check evidence | `.harness/state/checks/` | `checks.py` | valid for one tree |
| Review verdicts | `.harness/state/review/` | `review_verdict.py` | valid for one commit |
| Review config | `.harness/review/sources.json` | `review-setup` | until reconfigured |

Details: [data-model.md](data-model.md).

## Contracts / Schemas

- `config/settings.schema.json`: the repository settings.
- `config/tracker.schema.json` and `scripts/integrations/contracts.py`: the tracker contract.
- `skills/*/manifest.json` — orchestrated skills' input and output schemas.
- `common/artifact-schema.json` — backlog draft frontmatter.
- Command contracts: [../02-design/api.md](../02-design/api.md).

## Host Differences

| Aspect | Claude Code | Cursor |
| --- | --- | --- |
| Hook events | `PreToolUse` (matcher `Bash\|Write\|Edit\|MultiEdit\|NotebookEdit\|mcp__.*`), `UserPromptSubmit` | `preToolUse`, `beforeShellExecution`, `beforeMCPExecution`, `beforeSubmitPrompt` |
| Deny output | `hookSpecificOutput.permissionDecision: deny` | `{"permission": "deny", "agent_message", "user_message"}` |
| MCP tool names | `mcp__plugin_monolithic-dev-harness_<server>__<tool>` | bare tool names under the server |
| Host Azure server's organization | `${AZURE_DEVOPS_ORG}` from the environment (the installer writes it to Claude settings) | the installer pins it into `cursor.mcp.json` |
| Status | verified in a sandboxed profile | load not yet observed in a live Cursor session |

## Failure Modes

| Failure | Behavior |
| --- | --- |
| Settings file invalid | write-class calls denied (`harness-error`), reads allowed |
| Rules crash or run out of time | edits, shell commands, and every MCP call denied; plain reads allowed |
| Workflow runtime import or run fails | write-class calls denied, reads allowed |
| Selected tracker missing, invalid, untrusted, or lacking values | tracker and SCM writes denied (`tracker-invalid`) |
| A broken onboarded tracker folder | reported by `harness doctor`; other trackers unaffected |
| No active session for the checkout | governed code changes denied until `harness session start` |
| git unavailable | commit and PR rules deny |
| Approval window expired | tracker/SCM writes denied until a new approval |
| Azure DevOps unreachable | the call fails; nothing is retried in a loop (see the runbook) |

## Security Invariants

- No approval window or tracker trust exists unless the user's own prompt or click created it.
- No onboarded tracker counts unless its folder matches the digest the user trusted.
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
