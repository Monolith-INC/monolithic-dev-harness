---
date: 2026-09-24
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-make-trackers-pluggable-adapters"
story_points: 5
language: en
tags: [ticket, user-story, trackers, linear, local-tracker]
---

# Package Linear and the local tracker as trackers

## 🎯 What

As a team without Azure DevOps, I need Linear and a repository-local tracker shipped in the same shape as
Azure DevOps, so that I can adopt the harness with the tracker I already use or with none.

## 💡 Why

Linear exists only as a partial adapter and a paragraph of prose. The local tracker works for delivery but the
backlog skills do not know it. Shipping three trackers proves the manifest is not shaped around one of them.

## 📋 Expected Behavior

```text
trackers/linear/   (issues, sub-issues, managed type labels, comments)
trackers/local/    (records under .harness/tracker/)
  -> each passes the same contract tests as Azure DevOps
```

## ✅ Acceptance Criteria

- [ ] Create the Linear tracker folder, with Epic, Feature, Story, and Task expressed as issues with one managed type label each.
- [ ] Create the local tracker folder around the existing local tracker, storing records under the repository's harness folder.
- [ ] Run the shared tracker contract tests against all three trackers.
- [ ] Document in each manifest where specs, reports, and pull-request links attach.

## 🔧 Technical Notes

- Linear: Projects are not Epics (from `common/providers.md`); parent through `parentId`.
- Local: reuse `scripts/integrations/local_tracker.py` and its MCP runner.

## 📊 Complexity

**5 points** — Largest driver: Scope=5, Uncertainty=3, Integrations=5, Data=3, QA=3, Rollout=2 → 5 points

## 📄 Original Description

"We could ship Azure for sure, a local tracker, and perhaps a third option."
