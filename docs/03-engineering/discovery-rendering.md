---
title: Discovery Runtime Rendering
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-06
---

# Discovery runtime rendering

Onboarding is session-free. Bootstrap prepares settings, language confirmation, local tracker
storage, and the bundled BMAD runtime. The CLI refuses to start project work until this setup is
verified. Project work then selects a work session and starts its workflow.

`harness workflow render --stage discover --session-id <id> --repo <project>` resolves the project
path, original saved request, language, tracker, source control, preference environment, route,
and session-bound workflow commands. It runs the unchanged vendored BMAD renderer against the
shipped Stage 0 templates. Conditional branches are resolved before the agent receives instructions;
cross-step references are absolute paths in the resulting snapshot.

Snapshots live under `_bmad/render/bmad-build/`. BMAD records consumed configuration, template and
renderer hashes, and output hashes in `manifest.json`, publishing through a staging directory.
The harness validates the project/session context and output contents before recording
`discovery-render.json` in the selected work session. The command returns one absolute `entry`.
Agents must follow that entry, never execute the unrendered skill templates directly.

Repeated rendering returns the pinned snapshot after verification. Resume also verifies it before
changing workflow state. Changed settings, language, preference environment, or BMAD configuration,
missing output files, and modified manifests or outputs cause a failure; the original evidence is
preserved. A plugin upgrade does not silently replace an existing session's instructions. Mutable
progress and human decisions remain in the normal workflow records, outside the immutable snapshot.

Workflow mutations require an explicit session ID. Session-free status/list operations can inspect
legacy records for recovery, but cannot mutate them. Onboarding commands remain session-free.
Rendered instructions never open approval windows or replace existing tracker/SCM enforcement.

The installer places the declared Jinja2 dependency and its dependencies in the owned plugin's
`runtime/python` directory. The isolated renderer process loads them there. Development uses the
same dependency declaration through `requirements-dev.txt`; no user-global Python install is needed.

`scripts/render_bmad.py` synchronizes the canonical Stage 0 templates into the shipped skill;
`--check` checks their consistency. It no longer resolves a throwaway project's context and restores
placeholders. The discovery tests exercise real runtime rendering, pin reuse, session separation,
corruption refusal, CLI binding, onboarding readiness, and resume verification.
