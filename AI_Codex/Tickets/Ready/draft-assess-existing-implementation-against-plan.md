---
date: 2026-09-23
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-adopt-implementation-already-in-progress"
story_points: 3
language: en
tags: [ticket, user-story, delivery-workflow]
---

# Assess an existing implementation against its plan

## 🎯 What

As a delivery team, we need the harness to assess an existing Story branch against its approved
plan before it proposes additional work.

## 💡 Why

The team needs a reliable view of what is complete and what remains before an agent continues work
that another session or developer started.

## 📋 Expected Behavior

```text
Story and branch
  -> read planned Tasks, specification, commits, diff, and evidence
  -> compare planned and observed work
  -> report each Task as completed, incomplete, changed, or unverified
```

## ✅ Acceptance Criteria

- [ ] Read the Story, ordered Tasks, approved specification, branch, commits, current diff, and
  evidence records.
- [ ] Classify every planned Task as completed, incomplete, changed, or unverified.
- [ ] Identify stale or mismatched evidence as unverified for the current Git tree.
- [ ] Report scope differences without changing the Story, Task list, or specification.

## 🔧 Technical Notes

Read existing Git and evidence state only. Reuse the current evidence records keyed to a tree or
commit; do not create approval or manual-check records.

## 📊 Complexity

**3 points** — Largest driver: Scope=3, Uncertainty=3, Integrations=2, Data=1, QA=3, Rollout=2 → 3 points

## 📄 Original Description

"Suppose the implementation is already ongoing, does the harness have a workflow prepared for it?"
