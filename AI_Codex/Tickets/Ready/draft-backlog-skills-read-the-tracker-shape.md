---
date: 2026-09-24
type: ticket
work_item_type: User Story
provider: local
parent_id: "pending:draft-make-trackers-pluggable-adapters"
story_points: 8
language: en
tags: [ticket, user-story, trackers, backlog, skills]
---

# Backlog skills read the tracker's shape

## 🎯 What

As a product owner, I need generate, enrich, decompose, split, breakdown, amend, and validate to use my
tracker's artifacts and templates, so that my backlog comes out in the shape my tracker understands.

## 💡 Why

Eleven skills are written against Azure's tools and Azure's artifact names. The artifact schema only allows
Epic, Feature, User Story, and Task, and the provider field only allows local, azure-devops, or linear.

## 📋 Expected Behavior

```text
skill needs to draft a child
  -> asks the active tracker: which artifact sits below this one, with which template?
  -> drafts with the tracker's template in the team format
  -> creates it through the gateway (approval required)
```

## ✅ Acceptance Criteria

- [ ] Take artifact names, hierarchy, and templates from the active tracker's manifest in every backlog skill.
- [ ] Validate draft frontmatter against the active tracker's artifacts instead of a fixed list.
- [ ] Create, update, link, and read back items only through the gateway, adding the operations the backlog needs (update fields, add child, set estimate).
- [ ] Point skills to the active tracker's instructions instead of Azure's.
- [ ] Keep the team format (sections, language, complexity drivers) owned by the harness.

## 🔧 Technical Notes

- Enrichment templates move from `common/templates/` into each tracker; the harness keeps the section model.
- Gateway contract grows from 8 tracker operations; the local tracker implements all of them.

## 📊 Complexity

**8 points** — Largest driver: Scope=8, Uncertainty=5, Integrations=3, Data=3, QA=5, Rollout=3 → 8 points

## 📄 Original Description

"Our backlog tools do not belong to any particular tracker. They belong to the harness."
