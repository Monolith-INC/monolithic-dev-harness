---
date: 2026-09-23
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-enable-role-defined-worker-agent-orchestration"
story_points: 3
language: en
tags: [ticket, user-story, worker-agents]
---

# Define worker roles and execution profiles

## 🎯 What

As a delivery team, we need predefined worker profiles so that a delegated assignment has a role,
appropriate model tier, reasoning effort, quota budget, permitted tools, and clear result contract.

## 💡 Why

The team needs delegation to use a consistent level of capability for the work instead of choosing
an agent profile ad hoc in each session.

## 📋 Expected Behavior

```text
Bounded assignment
  -> select an approved worker profile
  -> provide permitted input and expected output
  -> record the selected profile for verification
```

## ✅ Acceptance Criteria

- [ ] Define a versioned profile format with role, model tier, reasoning effort, quota budget,
  permitted tools, input contract, output contract, and verification method.
- [ ] Define approved profiles for at least reviewer, researcher, planner, and implementation roles.
- [ ] Select a profile from the assignment type without allowing an unapproved profile.
- [ ] Record the selected profile with the delegated assignment.

## 🔧 Technical Notes

Profiles describe delegation policy and do not grant authority for tracker, source-control, policy,
or approval-record writes.

## 📊 Complexity

**3 points** — Largest driver: Scope=3, Uncertainty=3, Integrations=2, Data=2, QA=3, Rollout=2 → 3 points

## 📄 Original Description

"The lack of a worker-agent workflow with pre-defined agents having model tier and reasoning
strength set to match their work is a gap."
