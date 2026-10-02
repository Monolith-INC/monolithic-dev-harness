---
type: implementation-plan
created: 2026-09-24
area: delivery-workflow
stack: [python]
tags: [implementation-plan, spec-gate, hooks]
---

# Spec gate reads plans and specs from the artifacts path

## Problem

The "spec before code" rule (`_evaluate_work_context` in `plugins/monolithic-dev-harness/scripts/hook_runtime.py`)
allows edits and commits to source files only when the work item has a spec-like artifact. It looks in one place,
the tracker (`tracker.list_artifacts`). With the Azure DevOps adapter, that means the work item's comments.

Teams that keep plans and specs in the repository's artifacts path (`backlog.artifacts_path` in
`.harness/policy.json`) never satisfy the gate. That includes where `generate-breakdown-work-items` itself writes
its implementation plan. Found on 2026-09-24 in the aplicatudo monorepo, where story 7824's plan lived in the AI
Codex vault: every `src/` change needed tracker enforcement paused and resumed by hand, four times in one session.

## Change

1. **Local lookup when the tracker has none.** When the tracker lists no spec-like artifact, look for one under the
   policy's `backlog.artifacts_path`. The tracker path is unchanged and still checked first. When `artifacts_path`
   is empty, behaviour is exactly as before.
2. **What counts.** A Markdown file whose frontmatter meets both conditions:
   - `type`, normalized by the existing `_artifact_kind`, is one of the kinds the gate already accepts: `spec`,
     `tech_spec`, `design_doc`, `implementation_plan`, `bugfix_spec`, in any spelling `_artifact_kind` maps to them;
   - one of the work-item fields `story`, `ticket` or `work_item` equals the work item's key. A field holding a list
     matches if the list contains the key.

   No status check, matching the tracker path, which checks kinds only.
3. **Reuse, don't copy.** Parse frontmatter with `parse_frontmatter` from
   `runtime/orchestrator_core/ingest.py`. The new module adds the plugin's `runtime/` directory to `sys.path`,
   the same way `hook_runtime.py` adds `scripts/`.
4. **Bounded scan.** Only `*.md` files, only their frontmatter (the first 16 KB of each file), and unreadable files
   are skipped. The scan runs only on the fallback path, when the tracker has no artifact.
5. **Clearer denial.** The deny message names both places: "…has no accepted specification artifact in the tracker
   or under `<artifacts_path>`."

## Files

- `plugins/monolithic-dev-harness/scripts/harness/local_artifacts.py` (new):
  `has_local_spec_artifact(project_root, key, accepted_kinds) -> bool`.
- `plugins/monolithic-dev-harness/scripts/hook_runtime.py`: accepted kinds as one constant, used by both paths; the
  fallback call; the new message.
- `plugins/monolithic-dev-harness/tests/delivery/contract/test_hook_runtime.py`: cases below.
- `CHANGELOG.md`: an `Unreleased → Fixed` entry.

## Tests

- A local plan with a matching `story` allows a code edit when the tracker has no artifact.
- A matching `ticket` also allows it.
- A different key denies.
- A non-spec `type` (for example `session`) denies.
- An empty `artifacts_path` denies, as before.
- Tracker artifacts still allow without any local file.

## Out of scope

- Checking acceptance status (G2) on either path.
- Version bump and release.
