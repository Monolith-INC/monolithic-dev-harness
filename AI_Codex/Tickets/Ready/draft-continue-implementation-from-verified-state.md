---
date: 2026-09-23
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-adopt-implementation-already-in-progress"
story_points: 5
language: en
tags: [ticket, user-story, delivery-workflow]
---

# Continue implementation from a verified state

## 🎯 What

As a delivery team, we need the harness to continue an adopted implementation only after a person
approves its continuation plan.

## 💡 Why

The team needs the normal delivery controls to remain effective when work starts before the harness
is asked to manage it.

## 📋 Expected Behavior

```text
Assessment report
  -> proposed continuation plan
  -> human approval
  -> normal per-Task implementation workflow
```

## ✅ Acceptance Criteria

- [ ] Present a continuation plan that identifies the next Task and all unverified work.
- [ ] Wait for explicit human approval before changing tracker records, source code, or source-control state.
- [ ] Continue through the existing per-Task implementation workflow after approval.
- [ ] Preserve the original checkout as a recovery source and materialize inherited work in a
  separate correctly based worktree.
- [ ] Use one explicit adoption commit when truthful Task-sized boundaries do not already exist;
  do not manufacture TDD or commit history with index plumbing or temporary partial files.
- [ ] Transition Tasks only after their mapped acceptance and current-tree checks are satisfied.
- [ ] Preserve branch naming, approved-spec, test, check, review-verdict, and approval enforcement.

## 🔧 Technical Notes

The workflow must not mark a Task complete from code or commit history alone. It must preserve
uncommitted work and existing commit history. The `adopt-existing-implementation` skill is the
execution contract for the approved continuation plan.

## 📊 Complexity

**5 points** — Largest driver: Scope=5, Uncertainty=3, Integrations=3, Data=2, QA=5, Rollout=3 → 5 points

## 📄 Original Description

"Suppose the implementation is already ongoing, does the harness have a workflow prepared for it?"
