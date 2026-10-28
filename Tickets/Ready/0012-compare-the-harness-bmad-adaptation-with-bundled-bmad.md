---
title: "Compare the harness BMAD adaptation with bundled BMAD"
type: ticket
work_item_type: User Story
provider: local
provider_id: "STORY-0012"
date: 2026-10-28
---

Document how the harness's BMAD integration differs from the bundled BMAD sources it is built on.

The rendered discovery route (`harness workflow render`, docs/03-engineering/discovery-rendering.md) already turns the vendored BMAD templates into self-contained step packages with provenance. What the 2026-10-05 rework plan also asked for is still missing: a traced comparison of our adaptation against the pinned BMAD sources.

## Acceptance criteria

- [ ] Trace installed entry -> selected route -> step instructions -> tools -> artifact -> review for each harness stage that uses BMAD.
- [ ] For each bundled BMAD skill the harness uses, list retained behavior, intentional changes with their reason, and gaps.
- [ ] Every gap is either fixed, recorded as its own work item, or accepted with a reason.
- [ ] The comparison is a document under this item's folder in docs/work-items/.
