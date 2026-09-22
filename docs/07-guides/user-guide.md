---
title: User Guide
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# User Guide

## Goal

Take a piece of work from an idea to a reviewed draft pull request with the harness.

## Audience

Developers, Feature Owners, and Tech Leads on a team using Azure DevOps with Claude Code or Cursor.

## Prerequisites

- The harness installed (see [../04-operations/deployment.md](../04-operations/deployment.md)).
- The repository opted in with `harness bootstrap`, `review-setup` run once, and `harness doctor`
  healthy.

## Procedure

### 1. Start

Ask the agent to run the harness on your idea or on an existing work item:

```text
Take "students can add a profile photo" through the harness. Start with the backlog. pt-BR.
```

### 2. Backlog (gate G1)

The agent drafts the top item, enriches it, and proposes Features and Stories as one outline. Edit
the outline in plain language until it is right. The agent then shows every body with Story
Points as one batch with an id:

```text
Batch HB-4F9A: 1 Epic, 2 Features, 4 Stories (5, 3, 3, 3 points), 7 parent links. Approve?
```

Reply `approve HB-4F9A`. Nothing reaches Azure DevOps before that.

### 3. Plan (gate G2)

For the Story you build next, the agent moves it to in progress and writes a technical spec from
its acceptance criteria and Tasks. The Tech Lead reviews it; approve the batch that publishes it.

### 4. Build

The agent works Task by Task: a failing test, the change, the checks, a cleanup, one commit. If a
rule blocks it, it reads the reason and fixes the cause. You approve the batches that move Tasks.

### 5. Verify (gates G3, G4)

The agent checks the Story's acceptance criteria against the branch, runs the deep review, fixes
what it finds, records a verdict, and asks you to approve the push and the draft pull request.
Validate in staging (G3); a person publishes and approves the pull request (G4).

### Useful replies

| Reply | Effect |
| --- | --- |
| `approve HB-XXXX` | opens a 20-minute window for the batch's writes |
| `harness revoke` | closes open windows |
| `harness manual-check <name> ok` | records that you validated a guarded change by hand |

## Expected Result

Work items in Azure DevOps with correct parents and points, one commit per Task with tests, a
`ready` verdict, and a draft pull request linked to the Story.

## Verification

Check the work items' parents and Story Points in Azure DevOps, `git log` on the Story branch, and
the draft pull request.

## Troubleshooting

See [troubleshooting.md](troubleshooting.md).

## Related Documentation

- [../02-design/workflows.md](../02-design/workflows.md)
- [../04-operations/runbook.md](../04-operations/runbook.md)
