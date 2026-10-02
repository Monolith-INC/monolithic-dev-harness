---
date: 2026-09-24
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-make-trackers-pluggable-adapters"
story_points: 5
language: en
tags: [ticket, user-story, trackers, hooks, security]
---

# Gate writes and protect items through the active tracker

## 🎯 What

As a team lead, I need the approval and protected-items rules to cover whatever tracker is active, so that
switching trackers never opens a way to write without approval.

## 💡 Why

The approval rule recognizes Azure writes and the harness gateway's tools only. A skill writing to Linear
directly would not be asked for approval, and protected items assume Azure's numeric ids and mention links.

## 📋 Expected Behavior

```text
tool call
  -> is it a write of the active tracker's manifest, or a gateway write?  -> approval window required
  -> does it name a protected item in the tracker's id format?            -> blocked
  -> does the tracker turn a mention into a link, and does the text mention one? -> blocked
```

## ✅ Acceptance Criteria

- [ ] Treat every write operation declared in the active tracker's manifest as needing an approval window.
- [ ] Match protected items using the active tracker's id format, including text mentions when the tracker links them.
- [ ] Resolve the branch's work-item key with the active tracker's id format.
- [ ] Fail closed when the active tracker's manifest cannot be loaded.
- [ ] Remove Azure names from the hook rules.

## 🔧 Technical Notes

- Today: `is_azure_write`, `AZURE_EXTRA_WRITES`, and the `AB#` mention logic in `scripts/harness/rules.py`.
- Tests: one table-driven suite runs the same cases for each shipped tracker.

## 📊 Complexity

**5 points** — Largest driver: Scope=3, Uncertainty=3, Integrations=3, Data=2, QA=5, Rollout=3 → 5 points

## 📄 Original Description

"Enforce required behavior with hooks, and cover every bypass path."
