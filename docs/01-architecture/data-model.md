---
title: Data Model
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-28
---

# Data Model

## Context

The harness keeps no database. Its data is the work item hierarchy it creates in the selected
tracker, one settings file, the tracker folders, and a handful of JSON records in the repository.

## Authority Boundaries

Human-owned, so the `human-owned` rule blocks the agent from writing them directly:

- `.harness/settings.json`: only people change it. They edit it, or they choose an onboarded
  tracker (click **Use it**, or reply `use HT-XXXXXX`); the harness then replaces the `tracker`
  section, and only if the result is still valid settings. Bootstrap copies the file in once.
- `.harness/state/approvals/`, `manual/`, `asked/`, `trackers/`: written only by the prompt and
  answer hooks, from what the user typed or clicked.
- `.harness/state/sessions/`: written only through `harness session`, which checks every step.
- `.harness/state/tracking.json`: written only by the gateway's skip and resume tools, each behind
  an approval.

Check evidence and review verdicts are written by scripts the agent runs; they are keyed to git
ids, so they cannot vouch for code they did not see.

## Components

### Work item hierarchy

The harness speaks five kinds (epic, feature, user_story, task, bug) and five states (backlog,
ready, in_progress, done, canceled). Each tracker maps them to its own types and states in its
`tracker.json` (`kinds`, `states`) and declares which type may contain which (`artifacts`). Every
tracker must let an epic hold features, a feature hold user stories and bugs, and a user story hold
tasks. On Azure DevOps:

```text
Epic
 `-- Feature                 (parent link: Epic, optional)
      `-- User Story         (parent link: Feature, optional; Story Points required)
           |-- Task ...      (one per acceptance-criterion step)
           |-- Staging
           |-- Review
           `-- Breakdown     (done when the breakdown is created)
```

A Feature and a Story may each stand alone, with no parent. A Task always has a Story parent.
A Story never attaches to an Epic. Points go into the process's points field
(`Microsoft.VSTS.Scheduling.StoryPoints` on Agile, `Effort` on Scrum, `Size` on CMMI).

### Repository files

```text
.harness/
|-- settings.json                    committed; schema: config/settings.schema.json
|-- trackers/<name>/                 committed; onboarded trackers (tracker.json, adapter.py)
|-- tracker/                         this clone only (ignored); local tracker records, when selected
|   |-- <state>/<KEY>.json           {key, id, title, kind, state, description, parentId, links[]}
|   `-- artifacts/<KEY>/*.md         artifacts in the shared envelope format
|-- review/sources.json              requirement sources, PR host, knowledge store
|-- knowledge/<store>/               agent-owned, append-only knowledge revisions
|-- backlog/                         backlog stage reports, estimation bands, retry memory
`-- state/                           git-ignored
    |-- approvals/<HB-id>.json       {id, opened, expires, question?, notes?, writes[{tool, at}], revoked?}
    |-- manual/<name>-<tree>.json    {name, tree, note, recorded}
    |-- asked/<id>.json              a question the check let through, used up by its answer
    |-- checks/<tree>.json           {tree, recorded, results[{name, run, exit_code, seconds}]}
    |-- review/<commit>.json         {head, verdict: ready|blocked, summary, recorded}
    |-- sessions/<HS-id>/            session.json {id, work_item, workflow, worktree, git_dir,
    |                                branch, base_commit, started} and events/NNNN-<event>.json
    |-- trackers/<name>.json         {name, digest, trusted}: tracker trust
    `-- tracking.json                {mode: enforced|skipped, changed}
```

### Plugin files

```text
config/settings.schema.json          the settings contract
config/tracker.schema.json           the tracker manifest contract
trackers/<name>/tracker.json         shipped manifests: azure-devops, linear, local
trackers/<name>/adapter.py           shipped adapters
```

## Runtime State Machine

Evidence is valid only for the git id it names. Any change to the code produces a new tree or
commit id, so old evidence stops matching instead of being wrong.

A session's phase is the last event it recorded:

```text
          start            pause
 (none) --------> active ---------> paused
                    |  ^              |
                    |  +---resume-----+
             close  |                 | close
                    v                 v
                  closed <------------+
```

A closed session frees the checkout; the same work item can start a new session.

## Durable State

See the tables in [architecture.md](architecture.md#durable-state).

## Contracts / Schemas

- `config/settings.schema.json` (settings), `config/tracker.schema.json` (tracker manifests),
  `common/artifact-schema.json` (backlog drafts). The harness checks the first two with its own
  standard-library checker (`scripts/core/schema.py`).
- `scripts/integrations/contracts.py`: `TrackerOps` and `ScmOps`, the operations every adapter
  provides, and the values they exchange.
- Workflow artifacts on a tracker start with an envelope line
  `harness-artifact:v1 {"kind", "title", "revision"}`; one title and revision is published once.
- Backlog drafts: frontmatter `type: ticket`, `work_item_type`, `provider`, `parent_id`,
  `story_points` (required for Stories), `language`; no `status` key. Stories under a Feature that
  does not exist yet use `parent_id: "pending:<feature draft stem>"` until creation.

## Host Differences

None: both hosts read and write the same files.

## Failure Modes

- An unreadable settings file blocks every write-class call until a person fixes it.
- A missing, invalid, or untrusted selected tracker refuses tracker and SCM writes
  (`tracker-invalid`); a broken onboarded folder is reported on its own and hides nothing else.
- An unreadable session record makes the checkout's session state broken, which blocks governed
  code changes.
- A corrupt approval or evidence file is ignored (treated as absent), which can only make a rule
  deny, never allow.

## Security Invariants

Approval, manual-check, and tracker-trust records are created only by the prompt and answer hooks.
Sessions change only through `harness session`. The settings change only by a person.

## Validation Gates

`tests/harness/test_hook_rules.py` covers every rule through the hook; `tests/harness/test_sessions.py`
and `tests/delivery/contract/test_hook_runtime.py` cover sessions; `tests/integrations/` covers the
registry, adapters, gateway, trust, and onboarding; `tests/backlog/` covers draft validation.
