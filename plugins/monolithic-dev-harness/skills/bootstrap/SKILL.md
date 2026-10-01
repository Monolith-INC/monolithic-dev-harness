---
name: bootstrap
description: Use when the user asks to set up, opt in, reconfigure, or check the harness for a repository: writing its `.harness/settings.json`, the one settings file every stage reads.
---

# Bootstrap

The harness is **opt-in per repository**. Installing the plugin loads skills, agents, hooks, and MCP
servers everywhere, but its rules only govern a repository that has `.harness/settings.json`.
Bootstrap writes that file once and adds the Codex project default needed for option-based
questions. It does not copy hooks or MCP servers into the repository.

## 1. Choose the settings

Start from `<plugin root>/examples/settings.example.json` or build one with the user. Schema:
`<plugin root>/config/settings.schema.json`. Omitted sections take the defaults in
`scripts/harness/settings.py`.

| Field | Drives |
| --- | --- |
| `tracker` | `name` (a folder under `<plugin root>/trackers/`, or an onboarded one with `source: onboarded`) and `values`, the settings that tracker's `tracker.json` declares (Azure DevOps: `organization`, `project`, optional `team`, `process`; Linear: `team`) |
| `scm` | `github` (`owner`, `repo`) or `azure-repos` (`organization`, `project`, `repository`) |
| `branch_template` | ticket branch names; must contain `{key}` (for example `{category}/{key}-{slug}`) |
| `protected_work_items` | ids never written, linked, parented, or mentioned in linking text (`protected-items`) |
| `artifacts_path` | where backlog drafts, plans, and reports are written |
| `git.base_branch` | branch base, branch diffs, deslop scope |
| `approvals.window_minutes` | how long an approval keeps tracker and SCM writes open (`approval-required`) |
| `checks` | the commands `check` runs, selected by `when` globs (`guarded-paths`, `draft-reviewed-prs`) |
| `tests_required` | source and test globs for the commit gate (`tests-with-code`) |
| `generated` | files never edited by hand (`generated-files`) |
| `guarded_paths` | paths whose commits need `check:<name>` or `manual:<name>` evidence (`guarded-paths`) |
| `pull_requests` | draft-only creation and the review-verdict requirement (`draft-reviewed-prs`) |

The file is human-owned: hook `human-owned` blocks the agent from editing it after bootstrap. Show
the user the file and get a clear yes before running step 2.

## 2. Run

From the repository root:

```bash
harness bootstrap --settings-from <settings file>     # omit it to use the bundled example
```

If the `harness` command is not on `PATH`, run
`python3 "<plugin root>/scripts/harness/bootstrap.py" --repo <repo root> --settings-from <file>`.
Bootstrap checks the file and the selected tracker's values before writing anything, and never
replaces an existing settings file. Check the result with `harness doctor`.

## 3. Finish

1. Run `review-setup` once to record where requirements and pull requests live
   (`.harness/review/sources.json`).
2. For Azure DevOps, health-check with `harness doctor --azure`.
3. Restart the agent session so hooks and MCP servers reload.
4. If using Codex, trust the repository so `.codex/config.toml` is loaded. If it explicitly disables
   the picker, bootstrap reports the conflict and typed approvals remain available.
5. If the repository still has other copies of these workflows wired in (project-level hooks,
   `.claude/skills` copies of the same skill names, a project `.mcp.json` `azure-devops` entry),
   list them for the user. Two enforcers or two Azure servers on one repository cause double
   prompts and duplicate OAuth. Removing them is the user's decision.
