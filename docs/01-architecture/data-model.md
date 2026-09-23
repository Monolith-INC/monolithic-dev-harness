---
title: Data Model
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Data Model

## Context

The harness keeps no database. Its data is the Azure DevOps hierarchy it creates and a handful of
JSON files in the repository.

## Authority Boundaries

`.harness/policy.json`, `.harness/state/approvals/`, and `.harness/state/manual/` are human-owned:
the `human-owned` rule blocks the agent from writing them. Check evidence and review verdicts are
written by scripts the agent runs.

## Components

### Azure DevOps hierarchy

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
|-- policy.json                      committed; schema: config/policy.schema.json
`-- state/                           git-ignored
    |-- approvals/<HB-id>.json       {id, opened, expires, writes[{tool, at}], revoked?}
    |-- manual/<name>-<tree>.json    {name, tree, note, recorded}
    |-- checks/<tree>.json           {tree, recorded, results[{name, run, exit_code, seconds}]}
    `-- review/<commit>.json         {head, verdict: ready|blocked, summary, recorded}
.codex-workflows/integrations.json   tracker + SCM adapters, branch template
.agile-backlog-toolkit/config.json   org, project, team, process, artifacts path, provider mode
.monolithic-code-review/sources.json requirement sources, PR host, knowledge store
```

## Runtime State Machine

Evidence is valid only for the git id it names. Any change to the code produces a new tree or
commit id, so old evidence stops matching instead of being wrong.

## Durable State

See the tables in [architecture.md](architecture.md#durable-state).

## Contracts / Schemas

- `config/policy.schema.json` (policy), `common/artifact-schema.json` (backlog drafts).
- Backlog drafts: frontmatter `type: ticket`, `work_item_type`, `provider`, `parent_id`,
  `story_points` (required for Stories), `language`; no `status` key. Stories under a Feature that
  does not exist yet use `parent_id: "pending:<feature draft stem>"` until creation.

## Host Differences

None: both hosts read and write the same files.

## Failure Modes

A corrupt state file is ignored (treated as absent), which can only make a rule deny, never allow.

## Security Invariants

Approval and manual-check records are created only by the prompt hook.

## Validation Gates

`tests/harness/test_hook_rules.py` covers every record type; `tests/backlog/` covers draft
validation against the artifact schema.
