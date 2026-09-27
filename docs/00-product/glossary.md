---
title: Glossary
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Glossary

| Term | Meaning |
| --- | --- |
| Adapter | A tracker folder's `adapter.py`: pure translation between the harness's contract and one provider, exporting `adapter(context) -> TrackerOps`. |
| Approval batch | The exact set of tracker/SCM writes the agent proposes, labeled with a batch id such as `HB-7Q2K`. |
| Approval window | A time-limited permission (default 20 minutes, `approvals.window_minutes`) to perform tracker/SCM writes, opened only by the user: a click on `Approve`, or a typed `approve HB-…`. |
| Artifacts path | The repository folder where backlog drafts, plans, and reports are written (`artifacts_path` in the settings). The plugin never creates it. |
| Check evidence | The recorded result of the repository's configured checks for one git tree. |
| Checkout | One working copy on one branch: its worktree folder, its git directory, and its branch. A session binds to exactly one. |
| Conductor | A skill that sequences other skills (`harness`, `implement-story`, `review`). |
| Draft pull request | A pull request created with `isDraft: true`; publishing it is a human step. |
| Evidence | A file under `.harness/state/` keyed to a git tree or commit id, written by a script and read by a hook. |
| Feature Owner | The person who owns a Feature end to end: backlog split, staging validation. |
| Gate (G1–G4) | A point where a person decides: backlog approval, spec approval, staging validation, pull-request approval. |
| Gateway | The `workflow-integrations` MCP server: provider-neutral `tracker_*`, `scm_*`, and `workflow_*` tools that dispatch to the selected adapter. |
| Governed repository | A repository with `.harness/settings.json`; only these are subject to the rules. |
| Guarded path | A path whose commits need specific evidence (`check:<name>` or `manual:<name>`). |
| Hook runtime | `scripts/harness/hook.py` plus the workflow policy runtime; runs before every governed tool call. |
| Manual check | Evidence that a person validated a guarded change by hand, recorded from their own prompt. |
| Onboarded tracker | A tracker folder under `.harness/trackers/<name>/` that the repository brought in; it counts only while the user trusts it as it reads now. |
| Orchestrator | An MCP server that validates a skill's inputs and outputs and runs its Actor-Critic loop. |
| Protected work item | A work item id listed in `protected_work_items` that the agent may never write, link, parent, or mention in text the tracker turns into a link, not even with approval. |
| Review verdict | `ready` or `blocked`, recorded for one HEAD commit by the review stage. |
| Rule | One named deterministic check: `human-owned`, `tracker-invalid`, `approval-required`, `protected-items`, `tests-with-code`, `generated-files`, `guarded-paths`, `draft-reviewed-prs`, `history-preserved`. |
| Session | A binding of one work item to one checkout (`harness session start`); governed code changes need an active one, and the workflow checks its work item. Phases: active, paused, closed. |
| Settings | `.harness/settings.json`, the repository's only settings file: tracker, SCM, branch template, rules. Human-owned; the harness only reads it. |
| Stacked branches | Story branches based on a Feature branch, landed into it in order. |
| Tracker contract | What every tracker meets: `tracker.json` checked against `config/tracker.schema.json`, and an adapter returning `TrackerOps`. |
| Tracker manifest | A tracker folder's `tracker.json`: kinds, states, hierarchy, id formats, which tools write, how to connect, which settings it needs. |
| Tracker policy | What the rules know about trackers for one hook call, built from every usable tracker folder: which calls write, how ids look, which text links. |
| Tracker trust | The user's typed `harness trust-tracker <name> <digest>`, pinning an onboarded tracker to its folder's exact content. |
| Tracker | Where work items live. The repository selects one in the settings: a shipped one (`azure-devops`, `linear`, `local`) or an onboarded one. |
| Tracking mode | `enforced` or `skipped` (`/skip-tracker`, `/resume-tracker`), kept in `.harness/state/tracking.json`. Skipped turns off tracker tools and the session requirement. |
| Tree mode | `decompose-backlog` run on an Epic: Features and their Stories in one pass. |
| Workflow policy | The workflow rules: an active session for code changes, new branches on the convention, the session's work item in progress, spec before code (source and test files), completion evidence, protected branches. |
