---
date: 2026-09-24
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-make-trackers-pluggable-adapters"
story_points: 5
language: en
tags: [ticket, user-story, trackers, bootstrap]
---

# Bootstrap asks which tracker to use

## 🎯 What

As a user opting a repository in, I need bootstrap to list the available trackers and configure every stage
from my one choice, so that I never edit three configuration files that must agree.

## 💡 Why

Bootstrap always writes Azure Boards and Azure Repos and stops without an Azure organization. The tracker is
recorded in three places (delivery, backlog, and review) that nothing keeps in agreement.

## 📋 Expected Behavior

```text
harness bootstrap
  -> Which tracker? Azure DevOps / Linear / Local / Onboard a new tracker
  -> asks only the chosen tracker's settings
  -> writes one tracker choice that delivery, backlog, and review all read
```

## ✅ Acceptance Criteria

- [ ] List shipped and onboarded trackers, plus an option to onboard a new one.
- [ ] Ask only the settings the chosen tracker's manifest declares.
- [ ] Record the tracker choice once and derive the delivery, backlog, and review configuration from it.
- [ ] Move the policy's Azure block into tracker settings, migrating existing policies without data loss.
- [ ] Check the chosen tracker with its own health check in `harness doctor`.

## 🔧 Technical Notes

- `scripts/harness/bootstrap.py`, `integrations_setup.py`, `skills/bootstrap/SKILL.md`, `config/policy.schema.json`.
- SCM stays a separate choice (GitHub or Azure Repos) and is out of scope here.

## 📊 Complexity

**5 points** — Largest driver: Scope=5, Uncertainty=2, Integrations=3, Data=3, QA=3, Rollout=5 → 5 points

## 📄 Original Description

"The harness will ask the user: do you have a tracker that you want to use? Or list the options and let the user pick."
