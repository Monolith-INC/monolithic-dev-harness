---
name: tdd
description: "Make each Task's intended behavior executable before writing production code: a focused failing test, then the smallest change that passes it. Used by implement-story for every Task with a practical test path, and for bug fixes with a cheap local reproduction."
---

# Test first

For every Task in `implement-story`, turn one acceptance criterion into a focused test that fails
before the change and passes after it. For a bug, the test reproduces the defect.

Adapted from pstack's `tdd` (MIT, Lauren Tan), widened from bug fixes to every Task. The harness
enforces the outcome deterministically: a commit that changes source files without test changes in
the commit or on the branch is blocked (rule `tests-with-code`), and a pull request needs passing check evidence
for its exact tree (rule `draft-reviewed-prs`).

## Workflow

1. **Pick the criterion.** Name the acceptance criterion this Task satisfies and its smallest
   observable behavior.
2. **Choose the narrowest executable check.** Use the test style the repository already uses for
   that code path (the subproject router names it: widget tests, unit tests with the project's mock
   library, rules tests against emulators, …). Mirror the source path under the test directory.
3. **Write the failing test first.** Encode the intended behavior, not the implementation.
4. **Run it and see it fail for the intended reason.** If it passes, or fails for another reason,
   fix the test before touching production code.
5. **Implement the smallest change** that satisfies the behavior while keeping nearby contracts.
6. **Rerun the test**, then the nearby suite for the touched area.

## When a failing test is impractical

Say so explicitly before implementing, and choose the closest executable check (a targeted script,
an emulator scenario, a manual reproduction the user runs). Prefer no new test over a bad one: tests
that mostly test mocks, encode implementation details, depend on timing, or need heavy
infrastructure for a small change. A guarded path without an automated suite goes through the
manual-check flow instead (rule `guarded-paths`).

## Guardrails

- Never change a test to match a wrong implementation, and never weaken an assertion without a
  stated behavior change.
- Keep the test focused on the criterion; no fixture churn.
- Flaky signal: make it deterministic or document what is locked down.

## Report

Name the failing-before run and its failure, the passing-after run, and the nearby validation. If
failing-before evidence could not be produced, say why and name the substitute check.
