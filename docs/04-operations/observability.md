---
title: Observability
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Observability

## Runtime / Host

Everything the harness decides is visible either in the conversation (deny reasons, approval
notes) or in files under the repository's `.harness/state/`.

## Installation

Nothing to install; the state directory is created on first use.

## Configuration

`approvals.window_minutes` controls how long approval records stay active.

## Health Checks

`harness doctor` (see [deployment.md](deployment.md#health-checks)).

## State Inspection

```bash
ls .harness/state/approvals/                 # one file per approval id
python3 -m json.tool .harness/state/approvals/HB-7Q2K.json   # opened, expires, every write
ls .harness/state/checks/                    # check evidence per git tree
ls .harness/state/review/                    # verdict per commit
git rev-parse HEAD HEAD^{tree}               # which evidence applies right now
```

| Question | Where to look |
| --- | --- |
| Why was a call blocked? | the deny reason in the conversation: `[harness <rule>] …` |
| What did the agent write to Azure DevOps? | `writes` in the approval records, plus the work items' history |
| Did the checks pass for what is committed? | `.harness/state/checks/<tree of HEAD>.json` |
| Is the pull request allowed? | a `ready` file under `review/` for HEAD and a passing check file for HEAD's tree |
| Workflow policy debugging | `/tmp/codex_hook_debug.log` (written by the workflow runtime) |

## Runbook

See [runbook.md](runbook.md).

## Recovery

State files are plain JSON; deleting one only makes the matching rule deny again.

## Rollback

Not applicable.

## Evidence to Preserve

For an audit of a run: `.harness/state/approvals/`, `review/`, `checks/`, and the work items'
history in Azure DevOps.
