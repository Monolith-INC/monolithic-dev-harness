---
name: thermos
description: "Launch both thermo-nuclear review subagents in parallel, then synthesize their findings. Use for thermos, double thermo review, or combined bug/security and code-quality branch audits."
---

# Thermos

Run the two thermo review passes as background subagents in parallel, then synthesize their results into one verdict.

## Workflow

1. Determine the review scope from the user request, PR, current branch, or the relevant changed files. State the scope you picked before launching.
2. Gather the diff with the Bash tool — typically `git diff <base>...HEAD`, defaulting the base to the repository's trunk. Write large diffs to a file in the scratchpad directory and hand the reviewers that path rather than pasting the whole thing.
3. Launch both reviewers in parallel and wait for both results. Claude Code uses the Agent tool with `run_in_background: true`; Cursor uses the Task tool. Their agent names are `thermo-nuclear-review-subagent` (bugs and security) and `thermo-nuclear-code-quality-review-subagent` (maintainability and architecture). Codex uses the installed custom agents `mdh_thermo_review` and `mdh_thermo_quality`, respectively.
4. Give both the same scoped context: the diff (or its path), the changed-file list, the branch and commit subjects, and any repository conventions worth honoring. Tell each to return prioritized findings with `file:line` references and evidence, and to read whatever surrounding code it needs rather than guessing.
5. Pass along any project-specific risks worth weighting — production code paths touched by work that was meant to stay contained, committed data artifacts, secrets, paid API calls — and any house rules from `AGENTS.md`/`CLAUDE.md`, the repository's review guides (e.g. `docs/review.md` and the subproject's own `docs/review.md`), or memory that would otherwise produce bogus findings.
6. When both finish, synthesize: findings first, deduplicated across reviewers. Weight overlapping findings more heavily, resolve disagreements with your own judgment, and keep summaries brief.

## Reporting

If the individual background summaries are already visible to the user, do not restate them wholesale — surface the unified verdict, the highest-signal findings, and any remaining uncertainty.

If a reviewer is interrupted or returns nothing, say so plainly and report what is missing. Never present a partial run as a completed review, and never invent or predict a pending agent's findings.
