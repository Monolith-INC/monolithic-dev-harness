---
date: 2026-09-24
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-make-trackers-pluggable-adapters"
story_points: 5
language: en
tags: [ticket, user-story, trackers, manifest]
---

# Define the tracker manifest and registry

## 🎯 What

As the harness, I need one manifest format that every tracker fills in, and one registry that finds the
installed trackers, so that the workflow can ask the active tracker for its shape instead of assuming Azure.

## 💡 Why

Every later Story depends on a fixed description of what a tracker is. Without it, each stage keeps its own
guess about artifact names, states, and ids, which is how Azure got hardwired in the first place.

## 📋 Expected Behavior

```text
trackers/<name>/tracker.json   (shipped with the plugin)
.harness/trackers/<name>/tracker.json   (onboarded in the repository)
  -> registry validates each manifest against the schema
  -> the active tracker is the one named in .harness/integrations.json
```

## ✅ Acceptance Criteria

- [ ] Define a versioned manifest schema covering identity, access, artifacts, parent rules, harness roles, states, id format, mention-link behavior, attachments, estimation, text format, and write operations.
- [ ] Record the documentation source for each manifest answer, and mark answers the user supplied.
- [ ] Load shipped trackers from the plugin and onboarded trackers from the repository, with the repository winning on a name clash only when the user chose it.
- [ ] Refuse an invalid manifest with a message naming the field and the problem.
- [ ] Expose the active tracker's manifest to the hooks, the gateway, and the backlog runtime through one function.

## 🔧 Technical Notes

- Schema lives in `config/tracker.schema.json`; loader in `scripts/trackers/registry.py`.
- Harness roles: `container` levels (ordered, top first), `delivery_unit` (gets a branch, spec, review, and pull
  request, and carries points), and `step` (below the delivery unit).
- Mirrors `scripts/host_adapters/`: one registry, one module per tracker, no tracker named outside its folder.

## 📊 Complexity

**5 points** — Largest driver: Scope=3, Uncertainty=5, Integrations=3, Data=3, QA=3, Rollout=2 → 5 points

## 📄 Original Description

"The tracker will inform the harness how it does things, its shape."
