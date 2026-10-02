---
date: 2026-09-24
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-make-trackers-pluggable-adapters"
story_points: 8
language: en
tags: [ticket, user-story, trackers, onboarding, skills]
---

# Onboard a new tracker from its documentation

## 🎯 What

As a user whose tracker is not shipped, I need to point the harness at my tracker's documentation and answer
only what the documentation does not say, so that I get a working tracker folder without writing an adapter.

## 💡 Why

Well-known trackers document their rules; teams with their own tracker know them. Either way, the harness can
fill most of the manifest itself and ask the user only for the gaps, instead of guessing.

## 📋 Expected Behavior

```text
user asks to onboard a tracker
  -> asks for the tracker and its documentation link
  -> identifies the tracker (a shipped one is used as is)
  -> answers the manifest questions from the documentation, citing each source
  -> asks the user only the unanswered questions, then proposes the harness role mapping
  -> writes .harness/trackers/<name>/, validates it, probes the tracker read-only
  -> the user approves before it becomes selectable
```

## ✅ Acceptance Criteria

- [ ] Ask for the tracker and a documentation link, one question at a time.
- [ ] Use a shipped tracker unchanged when the documentation identifies one.
- [ ] Answer each manifest question from the documentation, recording the source, and never guess an unanswered one.
- [ ] Ask the user only the questions the documentation left open, and have the user confirm the role mapping.
- [ ] Write the tracker folder under the repository's harness folder and validate it against the manifest schema.
- [ ] Run a read-only probe against the tracker (read one item, list its states) before offering it in bootstrap.

## 🔧 Technical Notes

- New skill `onboard-tracker`; bootstrap's "Onboard a new tracker" option starts it.
- Access order: the tracker's official MCP server, then its CLI, then its REST API through a generated adapter.

## 📊 Complexity

**8 points** — Largest driver: Scope=5, Uncertainty=8, Integrations=5, Data=3, QA=5, Rollout=3 → 8 points

## 📄 Original Description

"Point us to the documentation for that tracker. If we don't get answers to these questions, we go back to the user."
