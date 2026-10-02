---
date: 2026-09-23
type: ticket
work_item_type: Feature
provider: local
parent_id: "pending:draft-improve-delivery-workflow-continuity-and-discovery"
language: en
tags: [ticket, feature, delivery-workflow]
---

# Enable safe adoption of implementation already in progress

## Objective

Allow the harness to assess existing implementation before it continues delivery work.

## Scope

### Included

- Compare a Story, its planned Tasks, its approved specification, and its branch state.
- Report completed, incomplete, changed, and unverified work before continuation.
- Materialize approved inherited work on the correct base without rewriting history, manipulating
  the index directly, or swapping partial file versions through the working tree.
- Preserve an unchanged recovery source and record inherited tests and commits honestly.

### Excluded

- Automatically marking work complete from code or commit history alone.
- Rewriting existing history or overwriting uncommitted work.

## Success Criteria

- [ ] The Feature provides a verified continuation plan before new implementation begins.
- [ ] The Feature provides a safe adoption path when implementation is on the wrong base or is not
  already divided along Task boundaries.
- [ ] The Feature preserves existing approval, evidence, branch, and review rules.

## Areas / modules involved

- `plugins/monolithic-dev-harness/skills/`
- `plugins/monolithic-dev-harness/scripts/harness/`
- `plugins/monolithic-dev-harness/scripts/policy/`

## Original Description

"Suppose the implementation is already ongoing, does the harness have a workflow prepared for it?"
