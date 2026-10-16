---
name: check
description: Run the repository's configured compile, lint, type-check, and test commands, fix what fails, and record check evidence for the code exactly as it is on disk. Use after each Task, after changing a guarded path, and before the review stage.
---

# Check

Adapted from cursor-team-kit's `check-compiler-errors` (MIT). The commands are not guessed: they
come from `.harness/settings.json` → `checks`, where each entry has a `name`, the `run` command, and
`when` globs that decide which checks apply to the files changed since the work session linked its
work item.

## Run

From the repository root:

```bash
sh "<plugin root>/bin/harness-python" "<plugin root>/scripts/harness/checks.py"
sh "<plugin root>/bin/harness-python" "<plugin root>/scripts/harness/checks.py" --only <name> ...
```

The script runs every applicable check, prints each exit code, and writes evidence to
`.harness/state/checks/<code digest>.json`. Evidence is keyed to a digest of the code files on
disk, staged or not, and version control plays no part; any later change to a code file makes it
stale. A check that changes code files itself (a formatter with `--fix`) records nothing: run it
again on the result. The harness reads the evidence:

- **Completion:** a work item is done only when every applicable check passed on the code as it is
  now, and each changed guarded path with `check:<name>` evidence has that check passing
  (`harness workflow requirements --gate completion`).
- **`draft-reviewed-prs`:** with Git-based delivery, creating the pull request needs the same
  evidence.

Never treat results from one version of the code as proof for another.

## When something fails

1. Summarize failures by file and category (compile, analyzer/lint, test, format).
2. Fix the highest-confidence issues first; formatting and analyzer findings are usually mechanical.
3. Never silence a check (skipping tests, lowering analyzer levels, `// ignore:` without a reason
   the user accepts) to get green.
4. Re-run until clean, or stop and report what blocks you.

## Output

- Status per check with its exit code and the tree it covered.
- Grouped error summary, the fixes applied, and any remaining blocker.
