---
name: feature-implementation
description: Implement a Feature with several User Stories on stacked branches — a Feature branch, one Story branch per Story, each Story through spec, implementation, and review — then land the stack and close the Feature. Use when the user wants to build a whole Feature rather than a single Story.
---

# Feature implementation

A Feature with several Stories runs the Story flow once per Story, on branches stacked under one
Feature branch:

```text
<base branch>
  +-- <Feature branch>          e.g. feature/1200-short-title
        +-- <Story 1 branch>    branched from the Feature
        +-- <Story 2 branch>
        +-- <Story 3 branch>
```

Before using the tracker, call `workflow_tracking_status`. If tracking is paused, report that this
skill is unavailable until `/resume-tracker`.

## Procedure

1. **Read the Feature.** Fetch the Feature and its child Stories through the tracker. Confirm each
   Story's acceptance criteria and state, and the stack order (which Story builds on which).
2. **Plan.** Publish an implementation plan on the Feature as a tracker artifact: the Stories in
   stack order and what each one delivers. Publishing is a tracker write: approval batch.
3. **Create the Feature branch** from the base branch, named with the branch template selected at
   bootstrap (`branchTemplate` in `.codex-workflows/integrations.json`). If the user wants a
   different name, ask; do not invent one.
4. **For each Story, in stack order:** `start-ticket` → `write-spec` (gate G2) →
   `implement-story` on a Story branch cut from the Feature branch → `review`. Review ends with a
   **draft** pull request from the Story branch **into the Feature branch**, linked to the Story.
   Pull requests are not opened earlier: the harness only allows one after a `ready` verdict.
5. **Keep the stack current.** When an earlier branch changes after a later Story branched from it,
   run `reconcile-feature-stack` before adding commits to the later Story.
6. **Land the stack** with `merge-story-stack-into-feature` once the Stories are ready.
7. **Close the Feature** with `finish-feature-development`.

Every tracker write, push, and pull request goes through the approval protocol in the `harness`
skill.

## Rules

- Read the Feature and its Stories through the configured tracker; do not work from memory.
- Use the bootstrap-selected branch template; ask the user when a custom name is needed.
- Every Story pull request targets the Feature branch and is linked to its Story.
- Never open the Feature → base-branch pull request here; that is `finish-feature-development`.
