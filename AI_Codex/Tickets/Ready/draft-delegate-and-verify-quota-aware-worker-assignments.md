---
date: 2026-09-23
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-enable-role-defined-worker-agent-orchestration"
story_points: 5
language: en
tags: [ticket, user-story, worker-agents]
---

# Delegate and verify quota-aware worker assignments

## 🎯 What

As a delivery team, we need the harness to delegate bounded assignments through approved worker
profiles, respect each assignment's quota budget, and verify the produced artifact before use.

## 💡 Why

The team needs a disciplined delegation process that can control quota use while preserving the
quality and traceability of delivery work.

## 📋 Expected Behavior

```text
Bounded assignment and selected profile
  -> dispatch with quota budget and allowed tools
  -> receive output artifact and execution record
  -> root agent verifies the artifact
  -> accept, retry, or reject the assignment
```

## ✅ Acceptance Criteria

- [ ] Dispatch only an assignment that has a selected approved worker profile.
- [ ] Enforce the profile's quota budget and report when the assignment cannot continue within it.
- [ ] Record the profile, input, output, execution result, and quota use for each assignment.
- [ ] Require the root agent to inspect the produced artifact before accepting the result.
- [ ] Keep approval-sensitive tracker, source-control, and policy writes under root-agent control.

## 🔧 Technical Notes

The workflow must use artifact-based verification and must not treat a worker's self-reported
completion as evidence. A quota budget is a control limit, not a guarantee of lower usage.

## 📊 Complexity

**5 points** — Largest driver: Scope=5, Uncertainty=3, Integrations=3, Data=3, QA=5, Rollout=3 → 5 points

## 📄 Original Description

"Such protocol would reduce quota usage and provide a more structured work discipline."
