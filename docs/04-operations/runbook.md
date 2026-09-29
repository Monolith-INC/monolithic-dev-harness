---
title: Runbook
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Runbook

## Runtime / Host

Claude Code or Cursor with the plugin installed; a governed repository.

## Installation

See [deployment.md](deployment.md).

## Configuration

See [environments.md](environments.md).

## Health Checks

```bash
harness doctor
harness doctor --tools
harness doctor --azure
```

## State Inspection

See [observability.md](observability.md).

## Runbook

| Situation | Action |
| --- | --- |
| Every write is blocked with `harness-error` | the settings are invalid or the runtime failed: read the message; a person fixes `.harness/settings.json`, or reinstall |
| `tracker-invalid` blocks a tracker write | the selected tracker is missing, invalid, untrusted, or lacks values: `harness doctor` names which; fix the settings or the folder, or trust it again |
| The workflow refuses code changes: "need an active session" | `harness session status`; on the work item's branch run `harness session start <item>`, or `resume` a paused one |
| `approval-required` blocks a write you approved | the window expired or the id differed: approve the new batch id |
| `protected-items` blocks a write | intended; the item is listed in `protected_work_items`. A person changes the settings only if the item should no longer be protected |
| `tests-with-code` blocks a commit | add the test, or put the test commit first on the branch |
| `guarded-paths` blocks a commit | stage, run `scripts/harness/checks.py --staged` (the working files must match the index exactly), commit; or validate by hand and click **Approve change** (Cursor: reply `harness manual-check <name> ok`) |
| `feature-branch` blocks a PR | the Story belongs to a Feature: target the Feature branch its session pinned (`harness session status`) |
| `harness adoption materialize` refuses | the source checkout, base, or plan changed since approval, or the patch does not apply: assess, plan, and approve again; a failed run removes the worktree and branch it created |
| `draft-reviewed-prs` blocks a PR | re-run the review stage on HEAD; any new commit needs a new verdict and new check evidence |
| `history-preserved` blocks a git command | intended; bring changes in with `git merge` (the `reconcile-feature-stack` skill) and land Stories with merge commits |
| Azure DevOps tools missing | search for the bare tool name (deferred tools load on search); run `harness doctor --azure` |
| Azure DevOps calls hang | stop retrying; reload the host. Look for stale `mcp-server-azuredevops` processes by walking the parent chain, and end only a stale one (see `skills/azure-devops/references/oauth.md`) |
| The MCP server does not start from the desktop app | the app lacks the shell's `PATH` (Node via `nvm`): start the host from a shell or make `npx` available system-wide |
| Hooks fire twice or two prompts appear | an older workflow plugin or a project-level hook is also installed; remove the duplicate |

## Recovery

Reinstall with the installer; clear `.harness/state/` if state is suspected corrupt.

## Rollback

Install the previous version with `--version`; see [deployment.md](deployment.md#rollback).

## Evidence to Preserve

The deny message, `harness doctor` output, and the relevant `.harness/state/` files.
