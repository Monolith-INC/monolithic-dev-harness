---
title: Glossary
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-30
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
| Architecture spine | The lean set of stable `AD-N` invariants that prevents separately built Features, Epics, or Stories from making incompatible technical choices. |
| Capability | A stable `CAP-N` entry in a product spec: one outcome intent plus one observable success condition. |
| Conductor | A skill that sequences other skills (`harness`, `plan-initiative`, `implement-story`, `review`). |
| Draft pull request | A pull request created with `isDraft: true`; publishing it is a human step. |
| Evidence | A file under `.harness/state/` keyed to a git tree or commit id, written by a script and read by a hook. |
| Feature Owner | The person who owns a Feature end to end: backlog split, staging validation. |
| Gate (G1–G4) | A point where a person decides: backlog approval, spec approval, staging validation, pull-request approval. |
| Gateway | The `workflow-integrations` MCP server: provider-neutral `tracker_*`, `scm_*`, and `workflow_*` tools that dispatch to the selected adapter. |
| Governed repository | A repository with `.harness/settings.json`; only these are subject to the rules. |
| Guarded path | A path whose commits need specific evidence (`check:<name>` or `manual:<name>`). |
| Hook runtime | `scripts/harness/hook.py` plus the workflow policy runtime; runs before every governed tool call. |
| Manual check | Evidence that a person validated a guarded change by hand, recorded from their own prompt or their click on **Approve change** for the exact staged tree. |
| Onboarded tracker | A tracker folder under `.harness/trackers/<name>/` that the repository brought in; it counts only while the user trusts it as it reads now. |
| Adoption | Taking over implementation that predates a session: `harness adoption` assesses it, the user approves one exact plan with **Approve adoption**, and the verified delta is staged on the approved base in a separate worktree. |
| Orchestrator | An MCP server that validates a skill's inputs and outputs and runs its Actor-Critic loop. |
| Protected work item | A work item id listed in `protected_work_items` that the agent may never write, link, parent, or mention in text the tracker turns into a link, not even with approval. |
| Product spec | The compact pre-backlog contract for one epic or coherent outcome: Why, capabilities, constraints, non-goals, success signal, and load-bearing companions. |
| Review verdict | `ready` or `blocked`, recorded for one HEAD commit by the review stage. |
| Rule | One named deterministic check: `human-owned`, `tracker-invalid`, `approval-required`, `protected-items`, `tests-with-code`, `generated-files`, `guarded-paths`, `feature-branch`, `draft-reviewed-prs`, `history-preserved`. |
| Session | A binding of one work item to one checkout (`harness session start`); governed code changes need an active one, and the workflow checks its work item. Phases: active, paused, closed. |
| Settings | `.harness/settings.json`, the repository's only settings file: tracker, SCM, branch template, rules. Human-owned: the harness changes only its `tracker` section, when the user chooses a tracker. |
| Stacked branches | Story branches based on a Feature branch, landed into it in order. |
| Suspension | The user's own `harness suspend` message turns off every harness check in one repository except `human-owned`; `harness resume` (or `harness suspension resume`) restores them. Kept in `.harness/state/suspension.json`. |
| Tracker contract | What every tracker meets: `tracker.json` checked against `config/tracker.schema.json`, and an adapter returning `TrackerOps`. |
| Tracker manifest | A tracker folder's `tracker.json`: kinds, states, hierarchy, id formats, which tools write, how to connect, which settings it needs. |
| Tracker policy | What the rules know about trackers for one hook call: which calls write (from every shipped and onboarded tracker folder, trusted or not), and how ids look and which text links (from every usable one). |
| Tracker trust | The user's click on **Trust** in a question that names an onboarded tracker, pinning it to its folder's exact content as it read when the question was shown. |
| Tracker | Where work items live. The repository selects one in the settings: a shipped one (`azure-devops`, `linear`, `local`) or an onboarded one. |
| Tracking mode | `enforced` or `skipped` (`/skip-tracker`, `/resume-tracker`), kept in `.harness/state/tracking.json`. Skipped turns off tracker tools and the session requirement. |
| Tree mode | `decompose-backlog` run on an Epic: Features and their Stories in one pass. |
| Workflow policy | The workflow rules: an active session for code changes, new branches on the convention, the session's work item in progress, spec before code (source and test files), completion evidence, protected branches. |
