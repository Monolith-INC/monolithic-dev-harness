---
title: Architecture
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-24
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
- **People** own `.harness/settings.json` (see [data-model.md](data-model.md#authority-boundaries)
  for the one change the harness makes on their behalf).
- **The hook runtime** decides whether a tool call may run. It never performs the call.
- **The developer's prompt and clicks** are the only source of approval windows, manual-check
  records, tracker trust, and tracker selection.

## Components

```text
+--------------------------- plugin -----------------------------+
|                                                                |
|  skills/               agents/            hooks/               |
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
|    workflow-integrations (routes to native provider internally) |
+----------------------------------------------------------------+
```

| Component | Responsibility |
| --- | --- |
| Skills | Stage procedures. Conductors (`harness`, `implement-story`, `review`) sequence the others. |
| Reviewer agents | `thermo-nuclear-review-subagent`, `thermo-nuclear-code-quality-review-subagent`; no file-edit tools, pinned to `opus`. |
| `scripts/host_adapters/` | Translates each host's payload keys, tool names, patch syntax, workspace hints, and response JSON into and out of the generic hook contract. Each adapter also implements the subagent contract (`subagents.py`), held to its `hosts/<host>.json` declaration. |
| `scripts/harness/hook.py` | Host-neutral hook orchestration: evaluates the normalized call, then delegates to the workflow policy runtime. |
| `scripts/harness/rules.py` | The nine named rules; consumes normalized tool kind, command, paths, and arguments. |
| `scripts/harness/settings.py` | Reads `.harness/settings.json` once per process into a value nothing can change; holds the defaults for omitted sections. |
| `scripts/harness/tracker_policy.py` | What the rules know about trackers, built once per call from the tracker folders. |
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
| Azure DevOps adapter | Internal gateway implementation using `@azure-devops/mcp`; it is not separately registered with the host. The gateway starts one persistent provider transport using repository settings. |

## Adapter Messaging Contract

**Owner decision, 2026-10-24. Shared process messaging implemented in the development source.**
The governing rule is [Constitution Article 13](../../CONSTITUTION.md#article-13--adapters-exchange-centrally-defined-messages-through-one-interface).

All agent-host adapters use one shared standard protocol and messaging interface. A central
message contract defines the available messages for each case. An adapter selects a predefined
message through the shared types or constructors, supplies the required data and submits it to
the bus. Neither an adapter nor a consumer defines a private variation of that message.

```text
Codex  <-> Codex adapter  <-> |
Claude <-> Claude adapter <-> | shared message bus <-> harness
Cursor <-> Cursor adapter <-> |
                             one interface and central message contract
```

| Component | Owns |
| --- | --- |
| Central protocol and message catalog | Message types, required fields, meanings, validation, versioning and shared constructors. |
| Adapter | Vendor-specific tool calls, notifications, identifiers and response translation. |
| Message bus | Delivery through the shared interface and explicit delivery outcomes. |
| Harness consumer | Generic context checks, policy, valid state transitions and persistent records. |

For a process status update, the contract must identify the process or subagent, the relevant
work session, the reported status, the report's source and the information needed to correlate,
order and deduplicate events. The exact schema belongs to the central catalog. Vendor-specific
event names and payloads stay inside the adapter.

Cancellation illustrates the distinction between intent and observation: the main agent sends a
standard cancellation request through its adapter; the harness can withdraw the subagent's
permission to make changes under its work session. Confirmation that the runtime stopped the
subagent is a separate status update. Reporting a status never grants additional permission or
creates a human approval.

The bus is a shared communication abstraction. Implementation should reuse existing standard
transport facilities where suitable; this decision does not select an external broker or require
a separate service.

### Shared protocol and first consumer

The process catalog is `scripts/harness/process_messages.py`. It provides the constructors and
validation for version 1 messages using [JSON-RPC 2.0](https://www.jsonrpc.org/specification),
whose standard permits communication within one process. The `MessageBus` interface and generic
consumer live in `scripts/harness/process_bus.py`; `process_store.py` isolates locked, atomic
persistence under `.harness/state/host_sessions/processes/`. A typed receipt supplies the centrally
constructed JSON-RPC response with the same request identifier.

| Catalog message | Meaning |
| --- | --- |
| `process.get` / `process.list` | Read a process or list processes within the adapter-derived owner/work-session scope. |
| `process.register` | Register an observed process in an existing active work session. It cannot replace a record or restore withdrawn permission. |
| `process.status_update` | Record a status for an identified execution. Host observations and main-agent reports remain separate. |
| `process.cancel` | Withdraw permission immediately. It does not claim that the host or an operating-system process stopped. |

All messages carry a protocol version, event identity and adapter-derived conversation/work-session
context. Process-specific messages also carry the process identity. Updates and cancellation requests include the expected record
revision. A duplicate message has no additional effect; reused event identities with changed
content, outdated revisions, old executions and contradictory ownership are refused. Cancellation
is permanent for that process record. A later report, registration or running notification cannot
restore its permissions.

The command vocabulary is shared in `scripts/harness/process_commands.py`. The agent selects an
operation with `harness process list|status|cancel|report`. The adapter derives the sender from the
actual host invocation and submits the corresponding catalog message through the bus. Command
bodies read results; they cannot directly publish a lifecycle update or edit the protected record.
A cancellation or report run without its adapter observation is refused unless that requested
state has already been applied. Reports expose only the main-agent origin; they cannot select a
host-confirmed origin or grant an approval.

`host_adapters/process_channel.py` is the shared adapter entry point. Codex's implementation is
`host_adapters/codex_process.py`; native lifecycle dispatch has moved out of the shared harness
hook. The existing Codex binding holds private identity and turn observations; the generic bus
record controls permission withdrawal. Both must allow a subsequent subagent write. Adapter
observations cannot bypass the shared consumer's ownership, revision or revocation checks.

The same bus and catalog accept all adapter identifiers without vendor branches. Codex is the
first connected native adapter. Claude and other adapters still lack a verified native process
channel; this change does not advertise that they implement one. The older Python subprocess
subagent contract in `host_adapters/subagents.py` remains separate and unsupported.

### Verification and remaining scope

A real isolated CLI trial on 2026-10-24 observed a successful subagent file write, a standard
cancellation request, a main-agent interruption report, and a denied subsequent write by the
same subagent. The generic record retained `revoked: true`, distinguished the main-agent report
from its last host observation, and the file remained unchanged after cancellation. See the
[native evidence](../06-delivery/acceptance/codex-adapter/process-bus-native-trial.json).

This controls subsequent guarded effects. It does not retroactively stop an already-running OS
command. Desktop controls, native observation delivery beyond the verified channel, other adapter
integrations and the remaining release acceptance requirements retain their own qualification.

## Runtime State Machine

Per tool call:

```text
host payload -> host_adapters -> ToolCall(name, kind, command, paths, arguments)
                                  -> harness rules and workflow policy
generic decision -> host_adapters -> host-native hook response
```

Host-specific names and JSON fields belong only in `host_adapters`; policy modules must not parse
them or construct a host response envelope.

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
         -> feature-branch* -> draft-reviewed-prs -> history-preserved*
         -> approval-required -> generated-files      (* Git delivery only)
                |                                   |
              pass                                 deny --> denied (rule + fix)
                v
         workflow policy (normalized host event):
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
| Settings | `.harness/settings.json` (committed) | a person (bootstrap copies it once); the answer hook (click) or prompt hook (typed `use HT-…`) replaces `tracker` when the user chooses a tracker | until edited |
| Onboarded trackers | `.harness/trackers/<name>/` (committed) | `harness tracker stage` | until edited, which drops trust |
| Local tracker items | `Tickets/` (project content; ticket files) | the local tracker adapter | until edited |
| Adoptions | `.harness/state/adoptions/<HA-id>/` | `harness adoption`; approval only by the answer hook | assessment and approval immutable |
| Tracker trust | `.harness/state/trackers/` | answer hook (click) or prompt hook (typed reply) | until the folder changes or is untrusted |
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
- `config/host.schema.json` and `scripts/host_adapters/subagents.py`: the subagent contract.
- [Adapter messaging](#adapter-messaging-contract): the shared process bus interface and central
  message catalog (`process_messages.py`, `process_bus.py`, `process_store.py`).
- `skills/*/manifest.json` — orchestrated skills' input and output schemas.
- `common/artifact-schema.json` — backlog draft frontmatter.
- Command contracts: [../02-design/api.md](../02-design/api.md).

## Host Differences

| Aspect | Claude Code | Cursor | Codex |
| --- | --- | --- | --- |
| Hook events | `PreToolUse`, `UserPromptSubmit`, `Stop`, question hooks | `preToolUse`, `beforeShellExecution`, `beforeMCPExecution`, `beforeSubmitPrompt` (no stop guard: its stop hook gets no final message) | `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`, question-tool hooks |
| Deny output | `hookSpecificOutput.permissionDecision: deny` | `{"permission": "deny", "agent_message", "user_message"}` | `hookSpecificOutput.permissionDecision: deny` |
| MCP tool names | `mcp__plugin_monolithic-dev-harness_<server>__<tool>` | bare tool names under the server | `mcp__<server>__<tool>` |
| Azure organization | `.harness/settings.json` → tracker/scm values | `.harness/settings.json` → tracker/scm values | `.harness/settings.json` → tracker/scm values |
| Status | verified in a sandboxed profile | live load pending | payload and policy tests pass; live load pending |

## Failure Modes

| Failure | Behavior |
| --- | --- |
| Settings file invalid | write-class calls denied (`harness-error`), reads allowed |
| Rules crash or run out of time | edits, shell commands, and every MCP call denied; plain reads allowed |
| Workflow runtime import or run fails | write-class calls denied, reads allowed |
| Selected tracker missing, invalid, untrusted, or lacking values (or a shipped tracker broken) | tracker and SCM writes denied, and every call to an MCP server other than the harness's own (`tracker-invalid`) |
| A broken onboarded tracker folder | reported by `harness doctor`; other trackers unaffected |
| Execution requirements not met (`harness workflow requirements`) | governed code changes denied; the refusal names the next workflow step |
| git unavailable, with Git delivery | commit, push, and PR rules deny |
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
- Backlog, delivery, and harness suites green on Python 3.12 and 3.13.
- `scripts/check_versions.py` agrees across every version source.
- The built release installs into a sandboxed Claude Code profile in CI and reports the plugin as
  enabled.
