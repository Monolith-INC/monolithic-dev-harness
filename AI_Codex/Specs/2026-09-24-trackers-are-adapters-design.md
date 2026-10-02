---
type: design-doc
work_item_type: Feature
feature: "pending:draft-make-trackers-pluggable-adapters"
area: trackers
stack: [python, markdown, json]
tags: [spec, design-doc, trackers, adapters]
created: 2026-09-24
status: draft
source: [conversation-2026-09-24, codex-workflows-plugin, repository-survey]
---

# Trackers are adapters — design

## Problem

The harness owns a delivery workflow (backlog, plan, build, verify) but is welded to one tracker, Azure DevOps.
A survey of the plugin on 2026-09-24 found Azure in eight kinds of places:

| Where | What is Azure-specific |
| --- | --- |
| `scripts/harness/bootstrap.py:95-176` | refuses to run without an Azure organization; always writes Azure Boards + Azure Repos; forces the backlog into Azure mode |
| `.harness/integrations.json`, `.harness/backlog/config.json`, `.harness/review/sources.json`, `policy.json` `azure` block | four records of the tracker choice that nothing keeps in agreement |
| `scripts/integrations/azure.py` and `runtime/orchestrator_core/providers/azure_devops/` | two separate Azure adapters, one for delivery, one for the backlog |
| `scripts/integrations/discovery.py` | Azure (and Linear) presets and tool-name candidates in shared code |
| 11 backlog skills + `references/azure-mechanics.md` | written against Azure's `wit_*` tools and Azure artifact names |
| `common/artifact-schema.json`, `contracts.WorkItemKind` | a fixed Epic / Feature / User Story / Task list and a fixed provider list |
| `scripts/harness/rules.py:66,180-196,415-455` | approval gating recognizes Azure writes and gateway writes only; protected items assume numeric Azure ids and `AB#` mentions |
| plugin `.mcp.json`, `harness doctor --azure` | the Azure MCP server starts for everyone; only Azure has a health check |

The most important consequence is a security one: a skill that wrote to another tracker's MCP server directly would
not be asked for approval, because the approval rule only knows Azure's tool names.

## Goals

- A tracker is a self-contained adapter in its own folder. The harness names no tracker outside that folder.
- The harness asks the active tracker for its shape (artifacts, hierarchy, states, ids, writes, templates) and
  executes through its adapter.
- Ship three trackers: Azure DevOps, Linear, local.
- One tracker choice at bootstrap configures delivery, backlog, and review.
- Onboard a new tracker from its documentation; ask the user only what the documentation does not answer.
- Hooks gate and protect every tracker without a rules change per tracker.

## Non-goals

- Pluggable SCM. GitHub and Azure Repos stay as they are; the same pattern can follow later.
- Moving existing work items between trackers.
- An OS-level sandbox for shell writes (deferred, issue #7). The shell reader stays best-effort.

## The model

The same split the harness already uses for hosts. A host adapter turns a host's hook payload into the harness's
`CanonicalToolEvent` and turns a decision back. A tracker adapter turns the harness's work-item operations into the
tracker's calls and turns the tracker's records back into harness records.

```text
                  harness (owns the workflow; names no tracker)
 ┌──────────────────────────────────────────────────────────────────────┐
 │ skills: generate · enrich · decompose · split · breakdown · amend ·   │
 │         validate · start-ticket · write-spec · resolve · review       │
 │ hooks:  approval-required · protected-items · spec gate · branch key  │
 └───────────────┬──────────────────────────────────┬───────────────────┘
                 │ gateway tools (tracker_*)        │ manifest (read-only)
                 ▼                                  ▼
          ┌─────────────┐   loads     ┌────────────────────────────────┐
          │  registry   │────────────▶│ active tracker                 │
          └─────────────┘             │  tracker.json  adapter.py      │
                                      │  mcp.json      templates/      │
                                      │  references/   doctor.py       │
                                      └───────────────┬────────────────┘
                                                      │ its own MCP server / CLI / API
                                                      ▼
                                   Azure DevOps · Linear · local records · onboarded
```

What each side owns:

| The harness owns | Each tracker owns |
| --- | --- |
| the workflow, gates G1–G4, and the hooks | its artifact types, hierarchy, and required fields |
| the team format: sections, language, complexity drivers | its states and allowed transitions |
| the gateway operations (what can be asked) | how each operation is done (its adapter) |
| harness roles (see below) | which artifact plays which role |
| approval records and evidence | its MCP connection, auth, and health check |
| | its enrichment templates and its instructions for skills |

### Harness roles

The workflow needs to know which artifact gets a branch, a spec, a review, and a pull request. Trackers do not say
that; it is the harness's concept. A manifest maps its artifacts onto three roles:

- `containers` — ordered, top first. Azure: Epic, Feature. Linear: Epic, Feature (issues with a managed label).
- `delivery_unit` — one branch, one spec, one review, one pull request, and the points. Azure: User Story.
  Linear: Story. Local: story.
- `step` — below the delivery unit. Azure: Task. Linear: Task (sub-issue).

A tracker may add artifacts outside the roles (Azure's Bug, for example); the harness carries them but never
branches on them.

## Folder layout

```text
<plugin>/trackers/                  shipped with the plugin
  azure-devops/
    tracker.json                    the manifest
    adapter.py                      TrackerAdapter subclass: harness operations ⇄ native calls
    mcp.json                        how the gateway starts its MCP server (command, args, env)
    templates/<artifact>.md         enrichment template per artifact
    enrichers/<artifact>.prompt.md  enricher prompt per artifact (optional; falls back to the harness's)
    references/                     instructions skills read (today's azure-mechanics.md, tool map)
    doctor.py                       health check used by `harness doctor`
  linear/ …
  local/ …

<repo>/.harness/trackers/<name>/    onboarded in this repository (same layout)
```

`scripts/trackers/registry.py` finds both, validates each manifest against `config/tracker.schema.json`, and
returns the active one (named in `.harness/integrations.json` → `tracker.name`). A repository tracker with the
same name as a shipped one is used only when the user chose it at onboarding.

## The manifest

Every question the onboarding interview asks is a manifest field, so a shipped tracker and an onboarded one have
the same shape. Each answer carries its source: a documentation URL, or `user`.

```json
{
  "schemaVersion": 1,
  "name": "azure-devops",
  "label": "Azure DevOps Boards",
  "docs": "https://learn.microsoft.com/azure/devops/boards/",
  "access": { "kind": "mcp", "server": "mcp.json", "auth": "oauth-interactive" },
  "settings": [
    { "key": "organization", "required": true, "env": "AZURE_DEVOPS_ORG" },
    { "key": "project", "required": true },
    { "key": "team", "required": false }
  ],
  "artifacts": [
    { "name": "Epic",       "children": ["Feature"] },
    { "name": "Feature",    "children": ["User Story", "Bug"] },
    { "name": "User Story", "children": ["Task"], "estimate": "Microsoft.VSTS.Scheduling.StoryPoints" },
    { "name": "Task",       "children": [] },
    { "name": "Bug",        "children": ["Task"] }
  ],
  "roles": { "containers": ["Epic", "Feature"], "delivery_unit": "User Story", "step": "Task" },
  "states": {
    "backlog": "New", "ready": "Approved", "in_progress": "Active", "done": "Closed", "canceled": "Removed"
  },
  "ids": { "pattern": "[0-9]+", "branch_key": "[0-9]+", "mention": ["#{id}", "AB#{id}", "_workitems/edit/{id}"] },
  "mentions_link": true,
  "attachments": { "spec": "comment", "report": "comment", "pull_request": "artifact-link" },
  "text_format": "markdown",
  "writes": ["wit_work_item_write", "wit_work_item_link_write", "wit_work_item_comment_write", "repo_create_branch"],
  "sources": { "states": "https://learn.microsoft.com/azure/devops/boards/work-items/workflow-and-state-categories" }
}
```

## Operations

Skills and hooks reach a tracker only through the gateway (`workflow-integrations`). The gateway already exposes
eight tracker operations; the backlog skills need three more, so the contract grows to eleven:

| Operation | Exists | Used by |
| --- | --- | --- |
| get, search, create (with parent), list children, transition | yes | all stages |
| publish artifact, list artifacts, link development artifact | yes | spec, resolve, review, spec gate |
| update fields (title, description, custom fields) | new | enrich, amend, auto-fix |
| set estimate | new | decompose, split |
| describe (the manifest, with settings resolved) | new | every backlog skill, bootstrap, doctor |

The tracker's own MCP server is started by the gateway from `mcp.json` (the delivery layer already works this
way), not by the plugin's `.mcp.json`. So the host never sees a tracker's raw tools, and the only tracker writes an
agent can call are the gateway's.

## Hooks

- `approval-required` gates every gateway write (as today) plus every tool in the active manifest's `writes` list,
  in case a host still exposes that tracker's server. `is_azure_write` and `AZURE_EXTRA_WRITES` go away.
- `protected-items` reads `ids.pattern` and `ids.mention`. When `mentions_link` is true, a protected id mentioned
  in text is blocked, as Azure's `#4007` is today.
- The branch key comes from `ids.branch_key` instead of the fixed pattern in `TrackerAdapter.resolve_branch_key`.
- A manifest that cannot be loaded makes every tracker write fail closed.

## Templates and the team format

The harness keeps the section model: What, Why, Expected Behavior, Acceptance Criteria, Technical Notes,
Complexity, Original Description, and the language setting. A tracker's template decides how those sections land in
its fields: Azure puts them in Description (markdown) and the points field; Linear puts them in the issue body and
its estimate. Today's `common/templates/canonical-*.md` become the Azure and local templates; Linear gets its own.

## Configuration

One choice, written once:

```text
.harness/integrations.json   tracker: { name, settings }   ← the only record of the choice
.harness/backlog/config.json provider_mode                ← derived from it at bootstrap
.harness/review/sources.json tracker                      ← derived from it at review-setup
.harness/policy.json         azure block                  ← migrated into tracker.settings
```

Bootstrap migrates a 0.1.x repository in place: `adapter: azure_devops` becomes `name: azure-devops`,
`local_tracker` becomes `local`, `linear` stays, and the policy's `azure` values move into `tracker.settings`.
Local tracker records stay in `.harness/tracker/`. Nothing is asked again.

## Onboarding a tracker

```text
"I'd like to onboard a new tracker"
  1 ask: which tracker, and where is its documentation?
  2 identify it → a shipped tracker? use it, stop
  3 read the documentation; answer each manifest question with its source
  4 ask the user only what stayed open (one question at a time)
  5 propose the role mapping; the user confirms
  6 pick access: official MCP server → CLI → REST API (generated adapter)
  7 write .harness/trackers/<name>/; validate against the schema
  8 read-only probe: read one item, list its states
  9 the user approves → the tracker appears in bootstrap's list
```

Nothing is guessed. An unanswered question stays open until the user answers it, and the tracker is not selectable
until the schema check and the probe pass.

**Declarative first.** An onboarded tracker reached through an MCP server needs no code: the generic
`TrackerAdapter` already runs from `bindings` (operation → tool name) and `mappings`, and discovery can propose the
bindings from the server's tool list. Generated `adapter.py` code is only for a tracker with no MCP server, and the
user reviews it before approving.

**An approved tracker is pinned.** The agent writes the onboarded folder, and the manifest decides what the hooks
treat as a write and which ids are protected. So an agent must not be able to change it afterwards. When the user
approves the tracker, the approval hook records a digest of the whole folder (the same mechanism that pins approved
spec notes); the registry loads an onboarded tracker only when its current digest is pinned, and any later edit
needs a new approval.

## Decisions taken while the user was away (confirm at G2)

1. **Harness roles** (`containers`, `delivery_unit`, `step`) are the harness's vocabulary; each manifest maps onto
   them. Without this the branch, spec, and pull-request flow cannot be tracker-neutral.
2. **Onboarded trackers live in `.harness/trackers/<name>/`** in the repository, following ADR-0008 (one harness
   folder per repository). Contributing one back to the plugin is a normal pull request.
3. **Templates live with the tracker; the section model stays with the harness.**
4. **The plugin stops starting the Azure MCP server for everyone.** The gateway starts the active tracker's server.
5. **This Feature's backlog stays local** (no Azure items), per the user.

## Critic pass

Findings from reviewing this design against the code, and how the design answers them:

| Finding | Resolution |
| --- | --- |
| An onboarded manifest decides what the hooks gate, and the agent writes it: an edit could drop a write tool or a protected-id pattern. | Onboarded folders are pinned by the user's approval; the registry refuses an unpinned one (Onboarding). |
| Generated adapter code would run inside the gateway. | Declarative first: MCP-reachable trackers need bindings only; generated code only without an MCP server, reviewed by the user. |
| A host may still expose a tracker's raw MCP tools (a user-level Linear server, for example). | `approval-required` also gates the manifest's `writes` list, not only gateway tools. |
| Hooks now read a manifest on every call. | Manifests are small JSON; the registry caches by file mtime within the process. A load failure fails closed. |
| Adapter names change (`local_tracker` → `local`). | Bootstrap migration maps old names; the registry accepts old names for one minor version with a warning. |
| Story 4's tests run per shipped tracker, but Stories 2–3 create them. | Story 4 starts on fixture manifests from Story 1 and adds the shipped trackers to its table as they land. |

## Alternatives considered

- **Configuration only, as in the example plugin** (`codex-workflows-plugin`): trackers are classes in one package,
  chosen at bootstrap, with bindings and mappings in `integrations.json`. It keeps a fixed five-kind artifact list and
  has no per-tracker templates or folder, so a new tracker still needs code in shared modules. We keep its bootstrap
  choice, gateway, and provider-neutral skills, and go further.
- **A copy of each backlog skill per tracker.** Rejected: it duplicates the workflow, which is the harness's to own.

## Risks

- **Breadth of the skill rewrite** (Story: backlog skills read the tracker's shape). Mitigation: move one skill at a
  time behind the `describe` operation, with Azure first so behavior can be compared before and after.
- **Azure OAuth under the gateway.** The delivery layer already starts Azure's server this way; the backlog path is
  new to it. Mitigation: health check in the Azure tracker's `doctor.py` before the switch.
- **Onboarding quality depends on the documentation.** Mitigation: every answer cites its source, the probe runs
  against the real tracker, and the user approves before use.

## Delivery order

```text
1 manifest + registry ─┬─▶ 2 Azure folder ──┬─▶ 5 backlog skills ──▶ 6 bootstrap ──▶ 7 onboarding
                       ├─▶ 3 Linear + local ─┘
                       └─▶ 4 hooks
```

Stories 3 and 4 can run in parallel after 1. See the implementation plan for Tasks.
