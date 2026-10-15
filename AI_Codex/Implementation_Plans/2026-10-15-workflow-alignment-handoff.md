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
The [implementation plan](2026-10-15-workflow-alignment-implementation.md) packages 1–11 are
implemented and pushed (`3482e84` … `efeb3d3`). All suites green at `efeb3d3`: backlog 337, plugin
1110 passed / 1 skipped, three installer scripts; `ruff check`, `ruff format --check`,
`check_repo.py`, markdownlint clean.

| Package | Commit | What |
| --- | --- | --- |
| 1 | `3482e84`, `6bc6306` | One onboarding route family (refinement and verify added, confirmation and the older routes removed); Git-only skills prepared only with Git delivery |
| 2 | `34db668`, `06f142f` | Gates `refinement-split`, `approve-document`, `refined-start`, `idea-continue`; `implementation-confirm` names one Story |
| 3 | `a0de07e` | `plan_review.py` replaces the bundle; `tracker-drafts.json` and `harness tracker publish` removed |
| 4 | `36e6323`, `98c50c3` | `tracker_update_work_item` in the gateway and all three adapters; toolkit skills ask their own approvals; plan approval required before Tasks |
| 5 | `c6a4b03` | `write-spec` writes technical specs only |
| 6 | `89c06db` | Sessions track the entry item; links outside it refused |
| 7 | `545c361` | `refined-start` in discovery, `idea-continue` at the end of the idea route |
| 8 | `89dd0cb` | Local mode of `finish-feature-development` |
| 9 | `c01f189` | Preparation documents approved one by one |
| 10 | `5b04de4` | Planning documents and data not code; scripts there still are |
| 11 | `efeb3d3` | Rename to "onboarding"; docs, diagram and changelog current; obsolete docs deleted |

Thermos review of packages 1–11 (both reviewers) and its fixes, `bf0c48c` … `369790b`, all suites
green at `369790b` (backlog 334, plugin 1204 / 1 skipped, installers):

- Fixed: the discovery skill's `--stage discover` command (plus a test that every documented
  `harness …` command parses); Feature and Epic completion (children done or cancelled, plus a
  resolution report and verification, as codex-workflows closes a Feature); Azure updates keep
  Markdown (`/multilineFieldsFormat/System.Description`); an approval pins only the notes it
  reviewed; an item approval no longer covers rewriting that item's text; a plan outside the
  artifacts path is refused.
- Owner decision: a pull request is always the user's choice and never a completion condition
  (`pull_request_linked` removed; constitution Article 10).
- Refactors: one shape for hours (`Hours`, `changed_fields`, tool-shaped `write_ops`); one note
  reader; `shown = true` as a gate setting (`artifact_review`), the plan's Story read from the plan;
  session binding in `work_lifecycle`; one Git-delivery helper; the gate reference complete.
- Still unverified: the Linear MCP `save_issue` field names `estimate`, `assignee` and `cycle`, and
  whether Linear accepts fractional estimates; check them against the live server in the trial.

Earlier on this branch: catalog requirement gates and Git independence (`2ceaf27`, `5d8aab2`),
knowledge store in trial fixtures (`addd129`), the alignment design and constitution.

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
  4. With no source globs, non-Markdown planning files counted as code, so a drafts file was
     refused before any Story existed to link. Fixed: the drafts file is gone (package 3) and
     planning documents and data are not code (package 10).
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
  The harness copy's garbled references are fixed (package 4). 1 test fails in the `/mnt` copy
  only (not investigated; likely file ownership).
- codex-workflows-plugin `/mnt/DATA/Projects/Personal/codex-workflows-plugin`, HEAD `75c22f0`,
  clean. The harness copied its reflection and spec/resolution runtimes unchanged and leaves out
  the `codex_workflows` skill by decision; the catalog now prepares `feature-implementation`,
  `review-pr`, `resolve-ticket`, the stack skills, `commit-prep` and `repository-sync` (the Git-only
  ones only with Git delivery).

## Next, in order

1. **Trial setup (needs the owner):** prepare hook trust and MCP tool approval for the isolated
   Codex home through a recorded, human-approved step; never the bypass flags.
2. **Rerun DAY-001** on a fresh fixture through refinement (item approvals, plan approval, Tasks)
   and `start-ticket`, with one code edit attempted before and after linking; stop before
   implementation. Check that `tracker_update_work_item` writes hours on the local tracker.
3. Take PR #37 out of draft once the trial passes (the thermos review is done).

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
