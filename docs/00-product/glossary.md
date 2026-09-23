---
title: Glossary
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Glossary

| Term | Meaning |
| --- | --- |
| Approval batch | The exact set of tracker/SCM writes the agent proposes, labeled with a batch id such as `HB-7Q2K`. |
| Approval window | A time-limited permission (default 20 minutes) to perform tracker/SCM writes, opened only when the user replies `approve HB-…`. |
| Artifacts path | The repository folder where backlog drafts, plans, and reports are written (`backlog.artifacts_path`). |
| Check evidence | The recorded result of the repository's configured checks for one git tree. |
| Conductor | A skill that sequences other skills (`harness`, `implement-story`, `review`). |
| Draft pull request | A pull request created with `isDraft: true`; publishing it is a human step. |
| Evidence | A file under `.harness/state/` keyed to a git tree or commit id, written by a script and read by a hook. |
| Feature Owner | The person who owns a Feature end to end: backlog split, staging validation. |
| Gate (G1–G4) | A point where a person decides: backlog approval, spec approval, staging validation, pull-request approval. |
| Governed repository | A repository with `.harness/policy.json`; only these are subject to the rules. |
| Guarded path | A path whose commits need specific evidence (`check:<name>` or `manual:<name>`). |
| Hook runtime | `scripts/harness/hook.py` plus the workflow policy runtime; runs before every governed tool call. |
| Manual check | Evidence that a person validated a guarded change by hand, recorded from their own prompt. |
| Orchestrator | An MCP server that validates a skill's inputs and outputs and runs its Actor-Critic loop. |
| Protected work item | A work item id listed in the policy that the agent may never write, link, or parent. |
| Review verdict | `ready` or `blocked`, recorded for one HEAD commit by the review stage. |
| Rule | One named deterministic check: `human-owned`, `approval-required`, `protected-items`, `tests-with-code`, `generated-files`, `guarded-paths`, `draft-reviewed-prs`, `history-preserved`. |
| Stacked branches | Story branches based on a Feature branch, landed into it in order. |
| Tree mode | `decompose-backlog` run on an Epic: Features and their Stories in one pass. |
| Workflow policy | The workflow rules: branch key, in-progress state, spec before code (source and test files), completion evidence, protected branches. |
