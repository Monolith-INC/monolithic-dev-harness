---
name: bootstrap
description: Use when the user asks to set up, opt in, reconfigure, or check the harness for a repository — writing its `.harness/policy.json` and the tracker/SCM, backlog, and review configuration the stages read.
---

# Bootstrap

The harness is **opt-in per repository**. Installing the plugin loads skills, agents, hooks, and MCP
servers everywhere, but its rules only govern a repository that has `.harness/policy.json`.
Bootstrap writes that file and the per-component configuration. It never wires hooks or MCP
servers into the repository's own host settings; the plugin provides those.

## 1. Choose the policy

Start from `<plugin root>/examples/policy.example.json` or build one with the user. Fields (schema: `<plugin root>/config/policy.schema.json`):

| Field | Drives |
| --- | --- |
| `azure` | organization (empty → taken from `AZURE_DEVOPS_ORG` at bootstrap), project, team, repository, `protected_work_items` (`protected-items`) |
| `backlog.artifacts_path` | where backlog drafts, plans, and reports are written |
| `git.base_branch` | branch base, branch diffs, deslop scope |
| `approvals.window_minutes` | how long an approval (a click on `Approve`, or an `approve HB-…` reply) keeps writes open (`approval-required`) |
| `checks` | the commands `check` runs, selected by `when` globs (`guarded-paths`, `draft-reviewed-prs`) |
| `tests_required` | source ↔ test globs for the commit gate (`tests-with-code`) |
| `generated` | files never edited by hand (`generated-files`) |
| `guarded_paths` | paths whose commits need `check:<name>` or `manual:<name>` evidence (`guarded-paths`) |
| `pull_requests` | draft-only creation and the review-verdict requirement (`draft-reviewed-prs`) |

The policy is human-owned: hook `human-owned` blocks the agent from editing it after bootstrap. Show the user
the policy and get a clear yes before running step 2.

## 2. Run

From the repository root:

```bash
harness bootstrap --policy-from <policy file>     # omit --policy-from to use the bundled example
```

If the `harness` command is not on `PATH` (installed without the installer), run
`python3 "<plugin root>/scripts/harness/bootstrap.py" --repo <repo root> --policy-from <policy file>`.
`AZURE_DEVOPS_ORG` must be set when the policy leaves `azure.organization` empty. Check the result
with `harness doctor`.

Optional: `--branch-template` (must contain `{key}`; default `{category}/{key}-{slug}`), `--discover`
(queries Azure DevOps for work-item types and states, which starts OAuth), `--force` (rewrite
`.harness/integrations.json` from scratch). An existing policy is never replaced; re-running
bootstrap on an opted-in repository repairs its integrations file in place instead.

## 3. Finish

1. Run `review-setup` once to record where requirements and pull requests live
   (`.harness/review/sources.json`).
2. Health-check Azure DevOps (`azure-devops` skill).
3. Restart the agent session so hooks and MCP servers reload.
4. If the repository still has older copies of these workflows wired in (project-level
   codex-workflows hooks, `.claude/skills` copies of the same skill names, a project `.mcp.json`
   `azure-devops` entry), list them for the user. Two enforcers or two Azure servers on one
   repository cause double prompts and duplicate OAuth. Removing them is the user's decision.
