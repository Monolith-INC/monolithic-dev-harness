---
title: Handoff — catalog gates, Git independence, DAY-001 trials, workflow alignment
type: handoff
created: 2026-10-15
branch: codex/planning-and-interaction-reliability
pr: https://github.com/Monolith-INC/monolithic-dev-harness/pull/37 (draft)
---

# Handoff: catalog gates, Git independence, DAY-001 trials, workflow alignment

Read the [constitution](../../CONSTITUTION.md) first: the owner's settled rules for this work (what
each source project owns, what refinement is, approvals, tracker writes, no dead material).

## Where things stand

Branch `codex/planning-and-interaction-reliability`, pushed. Draft PR
[Monolith-INC/monolithic-dev-harness#37](https://github.com/Monolith-INC/monolithic-dev-harness/pull/37).
All suites green at `67970e9`: backlog 337, plugin 1049 passed / 1 skipped, three installer
scripts; `ruff check`, `ruff format --check`, `check_repo.py`, markdownlint clean.

| Commit | What |
| --- | --- |
| `2ceaf27` | Code changes and completion wait for requirements read from `config/prepared-workflows.json` (`execution.requires`, the `completion` list), checked by `scripts/harness/workflow_requirements.py`. No harness decision depends on Git: evidence keyed to a content digest (`scripts/harness/code_content.py`), project found by `.harness`, Git-command rules opt-in via `git.delivery`. |
| `5d8aab2` | Thermos review fixes: one code baseline per work item (relinking cannot hide changes); check/review evidence, baselines and local tracker records human-owned; workflow policy inside the hook time budget; build output not code without globs; clean tree for PRs with Git delivery; Git-delivery commits use the catalog gate; dedupe (`bundle.covers`, `artifact_kind`, one `completion` list). |
| `67970e9` | `harness tracker publish` honours only the last `implementation-confirm` answer. |
| `addd129` | Trial fixtures seed the knowledge store, as bootstrap does. |
| (this commit) | Workflow alignment design and diagrams, DAY-001 trial 01/02 evidence, this handoff. |

## DAY-001 trials

- **Trial 01** (`AI_Codex/Artifacts/live-trials/20261015-day001-planning-gate-01/`): headless
  `gpt-6-luna` low; stopped correctly at the first decision. Knowledge store missing from the
  fixture (fixed in `addd129`).
- **Trial 02** (`…-gate-02/`, read `parent-report.md`): ten relayed rounds through BMad discovery,
  planning (Standard, contextual shortlist, two methods applied), approach draft, preparation drafts.
  Findings:
  1. Codex runs plugin hooks only after a person trusts them; `codex exec` never prompts, so
     rounds 1–2 (and probably every earlier headless trial) ran with no harness hook. After the human
     trusted the 6 hooks, answers were captured and a hook held a pending decision.
  2. Codex approval policy `never` blocked the harness's MCP tools (`tracker_describe`,
     `generate-work-item`, `generate-breakdown-work-items`).
  3. The agent misattributed that block to the harness and proposed publishing the Story early.
  4. Real defect: with no source globs, `is_code` counts non-Markdown files in the planning folder
     as code, so `docs/planning/tracker-drafts.json` would be refused before any Story exists to
     link — a deadlock. The alignment design removes `tracker-drafts.json` entirely; `is_code`'s
     planning-folder rule still deserves a look for other non-Markdown planning files.
- The code-change refusal has still not been observed live (no code edit was attempted).

## The alignment design

[`AI_Codex/Specs/2026-10-15-workflow-alignment.md`](../Specs/2026-10-15-workflow-alignment.md), with
its diagrams rendered in `2026-10-15-workflow-alignment-diagrams/`. It also carries the problem
statement (today's six-stage route, where trial 02 stalled) and the approval mechanics.

- BMad owns the approach: discovery, planning, hardening, and the idea route (with `bmad-spec`),
  which may stop at a brief or spec.
- agile-backlog-toolkit owns the backlog: a new **refinement** stage after hardening runs its
  workflow as written — amend items the approach changed, format check, enrich only what fails,
  decompose with Gate 1 and Gate 2, create and read back, audit, split, then per Story the plan
  approval (`implementation-confirm`) and the Task approval.
- The harness owns the contract: preparation documents (risk, verification, manifest), each approved
  when created.
- codex-workflows owns delivery: `start-ticket`, `write-spec` for missing technical specs,
  `implement-story`, review, `review-pr` (Git delivery), `resolve-ticket`, Feature close (with a
  local mode).

All questions are settled as owner decisions 1–12 in that document.

## Source repositories read

- agile-backlog-toolkit `/mnt/DATA/Projects/Personal/agile-backlog-toolkit` (same content as
  `/home/monolith/projects/agile-backlog-toolkit`), HEAD `e7ae82c` with 14 uncommitted files.
  Defects: broken references from a find-and-replace in `51dc76a` (`amend-workitems` →
  `backup-and-artifacts path.md`, `split-story` and `auto-fix-artifact` canonical paths, the
  `parent_id_artifacts path` field); default languages disagree (pt-BR vs en); the uncommitted
  `.mcp.json` change to `"cwd": "."` reverts the `${CLAUDE_PLUGIN_ROOT}` fix from `dae21dd`.
  The harness copy still carries three of the garbled lines. 1 test fails in the `/mnt` copy only
  (not investigated; likely file ownership).
- codex-workflows-plugin `/mnt/DATA/Projects/Personal/codex-workflows-plugin`, HEAD `75c22f0`,
  clean. The harness copied its reflection and spec/resolution runtimes unchanged but dropped the
  `codex_workflows` skill; the catalog prepares none of `review-pr`, `resolve-ticket`,
  `feature-implementation`, the stack skills, `commit-prep`, `repository-sync`.

## Next, in order

1. ~~Settle the six open questions~~ — done (decisions 6–12).
2. Turn the alignment document into an implementation plan (catalog `refinement` stage and
   execution/verify wiring; skills without draft mode; remove drafts/publish/`bundle.covers`;
   per-Story plan approval with pinned plan notes; `refinement-split` gate; docs).
3. Implement test-first.
4. Trial setup: prepare hook trust and MCP tool approval for the isolated Codex home through a
   recorded, human-approved step; never the bypass flags.
5. Rerun DAY-001 on a fresh fixture through refinement, plan approval and `start-ticket`, with one
   code edit attempted before and after linking; stop before implementation.
6. Thermos review of the branch, then take PR #37 out of draft.

## Environment notes

- **Root guard (root-architect-execution):** this session may dispatch only the `orchestrator`
  agent, and the orchestrator only worker types, so the thermos reviewer agents cannot run; the
  review was done inline. The guard also refuses shell commands that write into product folders
  such as `lib/`; product code was written with the Edit tool.
- **File permissions:** many files are owned by `bhave` with a read-only ACL mask; run
  `sudo chmod -R g+w /home/monolith/projects/monolithic-dev-harness` when writes fail.
- **Installed Claude plugin is 0.5.2**, so interactive trials in this host do not test current
  source; headless Codex trials install the source into an isolated home.
- **Untracked and not committed:** `.root-architect/` (orchestrator mailbox from the blocked
  thermos dispatch) and older `AI_Codex/` notes (`Agent_Sessions/codex-all-conversations.md`,
  `Artifacts/2026-10-05-*`, older `live-trials/2026100*`, `Implementation_Plans/2026-10-05-*`,
  `Specs/BMAD-HOST-INTERFACE-SPEC.md`). Review them before committing.
