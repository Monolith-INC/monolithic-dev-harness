---
name: check
description: Run the repository's configured compile, lint, type-check, and test commands, fix what fails, and record check evidence keyed to the exact git tree. Use after each Task, before committing a guarded path, and before the review stage.
---

# Check

Adapted from cursor-team-kit's `check-compiler-errors` (MIT). The commands are not guessed: they
come from `.harness/settings.json` → `checks`, where each entry has a `name`, the `run` command, and
`when` globs that decide which checks apply to the files the branch changes.

## Run

From the repository root:

```bash
sh "<plugin root>/bin/harness-python" "<plugin root>/scripts/harness/checks.py"            # committed HEAD (clean tree required)
sh "<plugin root>/bin/harness-python" "<plugin root>/scripts/harness/checks.py" --staged   # index, only when working files match it exactly
sh "<plugin root>/bin/harness-python" "<plugin root>/scripts/harness/checks.py" --only <name> ...
```

The script runs every applicable check, prints each exit code, and writes evidence to
`.harness/state/checks/<tree>.json`. Evidence is keyed to the git tree, so any later change makes
it stale. The hooks read it:

- **`guarded-paths`:** committing a guarded path whose evidence is `check:<name>` needs that check to pass for the
staged tree. Stage, run with `--staged`, then commit.
- **`draft-reviewed-prs`:** creating the pull request needs every applicable check to pass for HEAD's tree.

`--staged` fails before running anything when unstaged or untracked content makes the working-file
tree differ from the index. Use a clean worktree whose files exactly match what will be committed;
never treat results from one version as proof for another.

## When something fails

1. Summarize failures by file and category (compile, analyzer/lint, test, format).
2. Fix the highest-confidence issues first; formatting and analyzer findings are usually mechanical.
3. Never silence a check (skipping tests, lowering analyzer levels, `// ignore:` without a reason
   the user accepts) to get green.
4. Re-run until clean, or stop and report what blocks you.

## Output

- Status per check with its exit code and the tree it covered.
- Grouped error summary, the fixes applied, and any remaining blocker.
