---
name: implement-story
description: Spec-driven implementation of one User Story after its spec is approved — branch, then for each Task in order architect → failing test → implement → check → deslop → atomic commit → Task transition — ending with the Story ready for the review stage. Use after the six-stage implementation bundle is accepted, or after legacy write-spec approval, from the harness flow or feature-implementation.
---

# Implement Story

The execution half of the harness. Inputs come from earlier stages and are never re-invented here:

| Input | Produced by |
| --- | --- |
| Story, acceptance criteria, points | `decompose-backlog` (backlog stage, gate G1) |
| Tasks in order, plus Staging / Review / Breakdown | `generate-breakdown-work-items` |
| Implementation plan | `generate-breakdown-work-items`, approved with `implementation-confirm` |
| Technical specification (*how*) | `write-spec`, for the kinds the Story still lacks |
| Repository rules and commands | `AGENTS.md` routing, `.harness/settings.json` |

## Approved-plan handoff

Read the Story's approved implementation plan and the reading manifest, then only the documents this
Story needs. The plan was approved on its own with `implementation-confirm`; the harness refuses
code changes if it changed since. Every tracker write (moving the Story or a Task) is asked with its
own `move-item` approval. If a required contract is missing or circumstances changed materially,
explain the gap and consult the user about that specific change. Never invent or widen
authorization.

## 0. Start

0. Detect version control automatically at execution. If present, inspect the branch, index, working tree, untracked files, and commits since the intended base. This is context for preservation only; never require a branch or make a Git write to begin local implementation. If absent, execute and verify locally without Git-specific branch, commit or PR steps. If
   implementation already exists, stop this fresh-build routine and use
   `adopt-existing-implementation`; do not manufacture TDD history or reconstruct commits by swapping
   partial file versions through the working tree.
1. `start-ticket` on the Story: it confirms the tracker item, moves it to in progress (a tracker write:
   ask the `move-item` gate), and returns the spec plan.
2. Use `branch-and-pr` → *Branch* section only when the user selected branch-based delivery. Otherwise continue in the existing working copy; the approved project work-session is the work context.
3. Before the first code change, run `harness workflow requirements --repo <project>`. Continue only
   when it reports `ready`; otherwise do the step it names for the first missing requirement. The
   hook refuses code changes with the same report.
4. Read the repository routing (`AGENTS.md` → subproject router) once, and list the rules that apply
   to this Story (state management, layer boundaries, localization, PII masking, generated code,
   test layout). Carry the list through every Task.

## 1. Per Task, in the breakdown order

Apply `sequence-verifiable-units` to verify each Task before advancing. Its advice about rebasing,
branches, commits and PRs applies only when the user selected versioned delivery; no VCS action is a
prerequisite for local implementation.

1. **Architect** (`architect`) when the Task adds or reshapes an interface; skip it for mechanical
   Tasks and say why.
2. **Failing test first** (`tdd`) for the Task's acceptance criterion.
3. **Implement** the smallest change that passes it, following the carried rules.
4. **Check** (`check`): run the applicable checks on the code as it is. Fix until green; never
   silence a check.
5. **Deslop** (`deslop`) the Task's diff.
6. **Commit** atomically (`commit-prep`) when versioned delivery was selected: one Task, one commit, with a message that names the Task
   id. Hand edits of generated files are refused (`generated-files`). Tests with code, checks,
   and guarded-path evidence are completion requirements: the Story cannot be marked done without
   them (`harness workflow requirements --gate completion`). Fix the cause; never work around a
   hook.
7. **Transition the Task** to done in the tracker, with its `move-item` approval. If the hook
   reports the plan or spec changed, show what changed and ask again.

## 2. Story done

1. `check` on HEAD with a clean tree: evidence for the exact tree that will be reviewed.
2. **End-to-end tests** (`bmad-qa-generate-e2e-tests`): generate API and end-to-end tests for the
   Story's user-facing flows and endpoints with the project's existing test framework, run them, and
   commit them as their own atomic commit. Skip it only for a Story with no user-facing or API
   behavior, and say why.
3. `prove-it-works`: exercise the real behavior (run the widget or flow, the emulator scenario, the
   endpoint) and record what you observed, not what you expect.
4. Hand off to the `review` skill. Do not open the pull request here; the review stage does that
   after its verdict.

## Report

Per Task: the commit, the test that failed first and then passed, the checks run, and any deviation
from the spec with its reason. For the Story: the evidence path and the observed behavior.
