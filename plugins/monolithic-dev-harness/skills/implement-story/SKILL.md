---
name: implement-story
description: Spec-driven implementation of one User Story after its spec is approved — branch, then for each Task in order architect → failing test → implement → check → deslop → atomic commit → Task transition — ending with the Story ready for the review stage. Use after write-spec is accepted (gate G2), from the harness flow or feature-implementation.
---

# Implement Story

The execution half of the harness. Inputs come from earlier stages and are never re-invented here:

| Input | Produced by |
| --- | --- |
| Story, acceptance criteria, points | `decompose-backlog` (backlog stage, gate G1) |
| Tasks in order, plus Staging / Review / Breakdown | `generate-breakdown-work-items` |
| Technical specification (*how*) | `write-spec`, approved at gate G2 |
| Repository rules and commands | `AGENTS.md` routing, `.harness/policy.json` |

If the spec is missing or unapproved, stop and run `write-spec` first. The workflow policy hook
also blocks governed writes without the spec.

## 0. Start

1. `start-ticket` on the Story: it confirms the tracker item, moves it to in progress (a tracker write:
   ask for the approval batch), and returns the spec plan.
2. `branch-and-pr` → *Branch* section: create the Story branch from the fresh base.
3. Read the repository routing (`AGENTS.md` → subproject router) once, and list the rules that apply
   to this Story (state management, layer boundaries, localization, PII masking, generated code,
   test layout). Carry the list through every Task.

## 1. Per Task, in the breakdown order

Apply `sequence-verifiable-units`: every Task ends in a verified, committed state before the next
one starts.

1. **Architect** (`architect`) when the Task adds or reshapes an interface; skip it for mechanical
   Tasks and say why.
2. **Failing test first** (`tdd`) for the Task's acceptance criterion.
3. **Implement** the smallest change that passes it, following the carried rules.
4. **Check** (`check --staged` for guarded paths; otherwise run the applicable checks). Fix until
   green; never silence a check.
5. **Deslop** (`deslop`) the Task's diff.
6. **Commit** atomically (`commit-prep`): one Task, one commit, with a message that names the Task
   id. The hooks block commits that lack tests (`tests-with-code`), edit generated files (`generated-files`), or touch a guarded
   path without evidence (`guarded-paths`). Fix the cause; never work around the hook.
7. **Transition the Task** to done in the tracker (an approval batch; group several Tasks into one
   batch when they finish together).

## 2. Story done

1. `check` on HEAD with a clean tree: evidence for the exact tree that will be reviewed.
2. `prove-it-works`: exercise the real behavior (run the widget or flow, the emulator scenario, the
   endpoint) and record what you observed, not what you expect.
3. Hand off to the `review` skill. Do not open the pull request here; the review stage does that
   after its verdict.

## Report

Per Task: the commit, the test that failed first and then passed, the checks run, and any deviation
from the spec with its reason. For the Story: the evidence path and the observed behavior.
