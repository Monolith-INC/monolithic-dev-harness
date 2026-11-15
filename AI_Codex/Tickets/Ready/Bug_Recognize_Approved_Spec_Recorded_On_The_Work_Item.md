---
date: 2026-09-23
type: ticket
work_item_type: Bug
provider: local
story_points: 3
language: en
tags: [ticket, bug, spec-gate, azure-devops]
---

# The spec gate rejects a Story whose spec was approved and recorded

## 🎯 What

A Story whose technical spec passed gate G2 is still blocked by "has no accepted specification
artifact", because the approval was recorded on the work item as an ordinary comment and the
Azure adapter lists it with kind `artifact`.

## 💡 Why

The gate is supposed to stop code without an approved spec. Here the spec was approved and the
decisions were on the work item, yet implementation was blocked. The only way out is to publish
the spec a second time, which the agent cannot do without a new approval and which nobody expects
after G2. The failure message does not say what kind was found or how to fix it.

## 📋 Expected Behavior

```text
G2 approved -> spec published through the tracker adapter with kind tech_spec
            -> list_artifacts returns kind tech_spec
            -> spec gate allows governed changes
```

And when the gate still denies, the message says which artifacts were found, with their kinds,
and how to publish the spec correctly.

## Observed

- `tracker_list_artifacts` on the Story returned one item: the G2 decision comment, `kind:
  "artifact"`, `title: ""`, `revision: ""`.
- `hook_runtime._evaluate_work_context` accepts only `spec`, `tech_spec`, `design_doc`,
  `implementation_plan`, `bugfix_spec` (and hyphen variants), so it denied.

## 🔧 Technical Notes

- `integrations/azure.py` → `list_artifacts` reads work-item comments; a comment without the
  harness envelope gets the generic kind.
- Close the path that produced it: `write-spec` must publish the accepted spec through
  `tracker_publish_artifact` (envelope, kind, revision) as part of the G2 approval batch, and must
  not leave G2 recorded only as prose.
- Add a repair path: a command or skill step that republishes an existing approved spec with the
  right kind, inside an approval window.
- Improve the denial text: list the kinds found and point to the repair step.

## ✅ Acceptance Criteria

- [ ] After G2, the Story's artifacts include a spec kind the gate accepts, with no extra step.
- [ ] A Story whose approval exists only as a plain comment can be repaired in one approved step.
- [ ] The denial message lists the artifact kinds found and the repair step.
- [ ] Tests cover a Story whose artifacts contain only a plain comment.

## 📊 Complexity

**3 points** — Largest driver: Scope=2, Uncertainty=2, Integrations=3, Data=2, QA=3, Rollout=2 → 3 points

## 📄 Original Description

Found while implementing a Story with an approved spec: the spec gate did not recognize the G2
record on the work item.
