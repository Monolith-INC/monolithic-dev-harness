---
title: User Guide
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# User Guide

## Goal

Take a piece of work from an idea to a reviewed draft pull request with the harness.

## Audience

Developers, Feature Owners, and Tech Leads on a team using Claude Code or Cursor with Azure DevOps,
Linear, the repository-local tracker, or an onboarded one. The examples below use Azure DevOps.

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
Points, then asks one question:

```text
Create these in Azure: 1 Epic, 2 Features, 4 Stories (5, 3, 3, 3 points)?
  Approve    I create them now.
  Not now    Nothing is written.
```

Click **Approve**. Nothing reaches Azure DevOps before that. In Cursor, which has no question
picker, the agent gives the batch an id and you reply `approve HB-4F9A`.

### 3. Plan (gate G2)

For the Story you build next, the agent checks out its branch, moves it to in progress, binds it to
your checkout with `harness session start <story>`, and writes a technical spec from its acceptance
criteria and Tasks. The Tech Lead reviews it; approve the batch that publishes it.

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
| `approve HB-XXXX` | opens a 20-minute window for the batch's writes (Cursor; in Claude, click **Approve**) |
| `harness revoke` | closes open windows |
| `harness manual-check <name> ok` | records that you validated a guarded change by hand |
| `approve HT-XXXXXX` | trusts an onboarded tracker as it was shown to you (Cursor; in Claude, click **Trust**) |
| `use HT-XXXXXX` | makes that trusted tracker the project's tracker (Cursor; in Claude, click **Use it**) |
| `stop trusting the <name> tracker` | withdraws that trust (Cursor; in Claude, click **Stop trusting**) |

To add a tracker the harness does not ship, ask the agent. It prepares the tracker, explains what
it does and what it writes, then asks you two questions: whether to trust it, and whether to use it
now. Your clicks do the rest; the harness updates the settings file for you.

### Useful commands

| Command | Effect |
| --- | --- |
| `harness session status` | which work item this checkout is bound to, and its phase |
| `harness session pause` / `resume` / `close` | stop, restart, or finish the session |
| `harness doctor` | settings, tracker, and session at a glance |

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
