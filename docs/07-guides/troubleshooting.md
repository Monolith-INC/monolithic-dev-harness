---
title: Troubleshooting
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Troubleshooting

## Goal

Resolve the problems users hit most often.

## Audience

Anyone using or installing the harness.

## Prerequisites

`harness doctor` output for the repository in question.

## Procedure

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Installer: `could not find the latest release` | private repository, no credentials | `gh auth login`, or set `GH_TOKEN`, or pass `--version` |
| Installer: `checksum mismatch` | corrupted or altered download | retry; if it persists, report it and do not install |
| Installer: `Claude Code … not on PATH` | Claude Code not installed or not on `PATH` | install it, or use `--host cursor` |
| `harness: command not found` | `~/.local/bin` not on `PATH` | add it to your shell profile |
| Plugin missing after install | host not restarted | restart Claude Code / reload Cursor |
| Every write blocked with `harness-error` | invalid `.harness/settings.json` | fix the JSON; check `guarded_paths` names existing checks; `harness doctor` shows the first problem |
| `tracker-invalid` on a tracker write | the selected tracker cannot be used | `harness doctor`: add the missing `tracker.values`, fix the folder, or trust the onboarded tracker again |
| Code changes refused: no active session | no session, a paused one, a detached HEAD, or another branch | `harness session status`, then `start <item>` on the item's branch or `resume` |
| `harness session start` refuses | the branch carries a different id, or the checkout already has an open session | check out the item's branch; close the old session first |
| `approval-required` after approving | window expired or a different batch id | approve the batch id the agent shows now |
| `protected-items` | the item is protected in the settings | intended; work on a copy |
| `tests-with-code` on a commit | source changed without tests on the branch | add the test |
| `guarded-paths` on a commit | no evidence for the staged change | run the check with `--staged`, or record a manual check |
| `draft-reviewed-prs` on the PR | no `ready` verdict or checks for HEAD | run the review stage again after the last commit |
| `history-preserved` on a git command | a rebase, squash merge, or force-push | merge instead; a person can rewrite history outside the agent if it is really needed |
| Azure DevOps tools not found | deferred tools not loaded, or the server did not start | ask the agent to search for the tool by name; run `harness doctor --azure` |
| Azure DevOps calls hang | an OAuth redirect nobody completed | complete the browser sign-in; otherwise reload the host (see the runbook) |

## Expected Result

The blocked action succeeds after the cause is fixed.

## Verification

Re-run the action; `harness doctor` reports healthy.

## Troubleshooting

If a rule blocks something it should allow, capture the deny message and the relevant
`.harness/state/` files and report them to the maintainers.

## Related Documentation

- [../04-operations/runbook.md](../04-operations/runbook.md)
- [../04-operations/observability.md](../04-operations/observability.md)
