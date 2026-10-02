---
name: review
description: Verification stage for a finished User Story — requirements coverage first (review-story-preflight), then a deep correctness and quality audit (thermos), fixes, and a recorded verdict. If a hosted code service is configured, the workflow can continue by opening a draft pull request. Use after implement-story, or when asked to review a Story branch.
---

# Review

Requirements first, code quality second, a human last. The stage produces one recorded verdict per
HEAD commit using the local branch diff. It does not need a remote code host. A pull request is an
optional publishing step available only when a hosted service is configured.

## 1. Requirements coverage

Run `review-story-preflight` on the Story branch. It checks the whole branch against the Story's
description, acceptance criteria, and Definition of Done, and ends with a ready/blocked verdict.
It needs `.harness/review/sources.json`; run `review-setup` once per repository if it is
missing. Add `--lenses typescript` for TypeScript subprojects and `--lenses maintainability` when
the Story reshapes structure.

## 2. Deep audit

Run `thermos` on the same branch diff (base: `git.base_branch` from `.harness/settings.json`). Pass
the repository's review guides as house rules: the root `docs/review.md` and the touched
subproject's `docs/review.md` when they exist, plus the rules list `implement-story` carried. Items
no linter catches go here explicitly, for example masking personal data in the UI when the repository requires it.

## 3. Fix and re-run

Fix every `VERIFIED` finding at `high` or above, and any `error` or `gap` from the requirements
pass, as new atomic commits (the commit hooks still apply). Re-run the checks on HEAD, then re-run
the pass that produced each fixed finding. Any new commit invalidates an earlier verdict.

## 4. Verdict

With a clean tree, record the verdict for HEAD:

```bash
python3 "<plugin root>/scripts/harness/review_verdict.py" --verdict ready --summary "<one line>"
```

Use `--verdict blocked` when something must go back to the backlog or the spec: an acceptance
criterion that cannot be met as written, or a finding that needs a product decision. Report the
blocker and do not open a pull request.

## 5. Pull request

When GitHub or Azure Repos is configured, `branch-and-pr` can push and open the **draft** pull
request linked to the Story (one approval batch for both). Include the requirements coverage and
the thermos verdict in the description. If no hosted service is configured, finish after recording
the verdict; the local review is complete and must not be marked blocked for lack of a pull request.

## Human gates

- **G3, staging:** the Feature Owner (or the Story's developer) validates the behavior in the
  staging environment, per the team's Definition of Done.
- **G4, pull request:** a human publishes the draft and approves it. The hooks block both actions
  for the agent. Reviewer comments come back through `triage-pr-comments` and
  `respond-pr-comments`; posting replies is a write that needs the user's approval batch.
