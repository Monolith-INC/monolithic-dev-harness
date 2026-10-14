# Tracker drafts

Refinement in six-stage Preparation ends in one machine-checked file, `tracker-drafts.json`, saved
in the work's planning folder beside the plan. It is the batch the final approval binds and the
only input to publication. The refinement skills keep writing their readable drafts as before;
this file records the hierarchy they settled on.

## Who writes it

Run the refinement skills in their six-stage draft mode, in this order, after Hardening:

1. `generate-work-item` drafts the top item (Epic, Feature, Story or Bug), or name an existing
   tracker item as the parent instead.
2. `decompose-backlog` splits an Epic into Features and Stories, or a Feature into Stories.
3. `generate-breakdown-work-items` drafts the Tasks of every Story or Bug in the batch.

Each skill adds its items to `tracker-drafts.json`; none of them creates tracker items.

## Format

```json
{
  "items": [
    {"ref": "E1", "kind": "epic", "title": "Task persistence clarity", "description": "…"},
    {"ref": "F1", "kind": "feature", "title": "Reset notice", "parent": "E1"},
    {"ref": "S1", "kind": "user_story", "title": "Explain reset on screen", "parent": "F1",
     "acceptance_criteria": ["Given …, when …, then …"], "estimate": 2},
    {"ref": "T1", "kind": "task", "title": "Add the notice widget", "parent": "S1"}
  ]
}
```

- `ref`: a local name, unique in the batch. `parent`: an earlier `ref`, an existing tracker key
  (such as `FEATURE-0007`), or empty for a top item.
- `kind`: `epic`, `feature`, `user_story`, `bug` or `task`.
- `description`: the enriched body in the team format. Acceptance criteria and the estimate are
  appended to it when the item is created.
- List parents before their children.

## What the harness checks

`harness workflow show` and the `implementation-confirm` gate refuse a batch unless:

- every Epic and Feature has children, and each child is a kind its parent may hold;
- every Story and Bug has acceptance criteria and at least one Task, and a Story has an estimate
  when the tracker records one;
- every Task has a parent Story or Bug;
- the batch has at least one Story or Bug.

## Publication

After `implementation-confirm` approves the bundle, run
`harness tracker publish --drafts <path> --session-id <id> --repo <project>`. It creates the items
in order through the selected tracker, once each. A receipt per item means a rerun never creates
a duplicate. Use the printed keys for `start-ticket`.
