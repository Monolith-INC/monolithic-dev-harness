---
title: Implementation plan — workflow alignment
type: implementation-plan
status: draft
created: 2026-10-15
branch: codex/planning-and-interaction-reliability
design: ../Specs/2026-10-15-workflow-alignment.md
---

# Implementation plan: workflow alignment

Implements the [workflow alignment design](../Specs/2026-10-15-workflow-alignment.md) and its owner
decisions 1–12. Paths are under `plugins/monolithic-dev-harness/` unless they start with `docs/` or
`AI_Codex/`. No compatibility path: removed files, commands and fields go outright.

Two rules apply throughout (owner, 2026-10-15): "six-stage onboarding" is renamed **onboarding**
everywhere, since the route now has seven stages; and anything this change makes obsolete — code,
config, tests, docs — is removed, not kept beside its replacement.

Each work package is test-first: write the failing tests named under **Tests**, make them pass, run
the package's suites, then commit. Packages are ordered so each one leaves the suites green.

## Work packages

### 1. Catalog: one route family, stages and requirements

The onboarding route becomes discovery → planning → hardening → **refinement** → preparation →
execution → **verify**, with **ideate** in front when the user chooses to explore an idea. The
`confirmation` stage goes: the plan approval moves into refinement.

The older route family is dead: every workflow starts at `discovery`, and the older stages are
reachable only through `harness workflow prepare --route`. Remove it.

- Routes: keep `onboarding` and an `explore-idea` route (`ideate` followed by the onboarding
  stages). Delete `investigate-request`, `prepare-artifacts`, `implement-approved-item`,
  `resume-work` and `suspend-checks`.
- Stages: delete `setup`, `discover`, `backlog`, `technical-plan`, `build` and `suspend`; the
  onboarding `verify` stage replaces the old one. Before deleting, move what the onboarding stages
  lack: `knowledge-acquire` and the read-only tracker operations from `discover` into `discovery`;
  `sequence-verifiable-units` from `technical-plan` into `preparation`, where it writes the
  verification document; the `build` checks and recovery text into `execution`. Suspension stays a harness control (`harness suspend`), not a
  stage.
- `scripts/harness/workflow.py`: one `STAGES` tuple — `ideate`, `discovery`, `planning`,
  `hardening`, `refinement`, `preparation`, `execution`, `verify` — and the comment about keeping
  older checkpoints readable goes.
- `scripts/harness/cli_workflow.py` (`render` accepts only `discovery`) and
  `scripts/harness/startup.py` (`_begin_output` matches only `discovery`) drop `discover`.
- `config/prepared-workflows.json`:
  - New `refinement` stage: skills `amend-workitems`, `validate-artifact`, `auto-fix-artifact`,
    `generate-work-item`, `enrich-work-item`, `decompose-backlog`, `split-story`,
    `generate-breakdown-work-items`, `generate-plain-language-documentation`; tracker operations
    `tracker_describe`, `tracker_search_work_items`, `tracker_get_work_item`,
    `tracker_list_children`, `tracker_create_work_item`, `tracker_publish_artifact`.
  - `preparation`: drop `bmad-spec` and `generate-work-item`; `sequence-verifiable-units` writes
    the verification document, `generate-plain-language-documentation` the risk document, and the
    harness the reading manifest.
  - `confirmation` stage removed; `onboarding` route updated.
  - `execution`: `start-ticket`, `write-spec`, `implement-story`, `tdd`, `check`.
  - Onboarding `verify`: `review`, `branch-and-pr`, `review-pr`, `resolve-ticket`,
    `finish-feature-development`, `reconcile-feature-stack`, `merge-story-stack-into-feature`.
  - `ideate`: add `bmad-spec` and `plan-initiative`.
  - Requirements `tasks_parented` and `plan_approved`: `stage` becomes `refinement`; `how` names
    the per-Story plan approval and no longer mentions a bundle.
- Git-only skills: add a `"delivery": "git"` marker on skill entries (`branch-and-pr`, `review-pr`,
  the two stack skills, `commit-prep`, `repository-sync`); `scripts/harness/prepared_workflows.py`
  leaves them out unless the settings choose Git delivery.
- `scripts/harness/review_decisions.py`: drop the `confirmation` checkpoint special case.

**Tests:** the catalog has exactly the `onboarding` and `explore-idea` routes and the eight stages;
a checkpoint at a removed stage is refused; stage order of the onboarding route;
`refinement` prepares the toolkit skills; requirement stages; Git-only skills prepared only with
Git delivery.

### 2. Gates

`config/gates.toml`, both languages:

- `refinement-split` (required, no writes): Gate 1, approve the proposed split.
- `implementation-confirm` reworded to one Story: "Approve the implementation plan for {story}?";
  options approve / revise / stop; still `binds = "artifacts"`.
- `approve-document` (approval, artifact, binds artifacts): any created document that is not a
  work item, plan or technical spec (preparation's risk and verification documents).
- `refined-start` (required): "This Story already has Tasks and an approved plan. Run discovery,
  planning and hardening first, or go straight to delivery?"
- `idea-continue` (required): "Continue into technical discovery, or stop with this brief or spec?"
- `publish-items` and `approve-spec` unchanged.

**Tests:** every new gate loads in `en` and `pt-br` with matching options; `implementation-confirm`
requires the `story` value.

### 3. Per-Story plan approval replaces the bundle

`scripts/harness/bundle.py` becomes `scripts/harness/plan_review.py`, keeping only the two rules
still needed: the plan was **shown** unchanged (and, on Claude, appears in the agent's own reply),
and it is **ready**.

- `ready`: exactly one `--artifact`, a note of type `implementation-plan` whose `story` field names
  a Story or Bug that exists in the selected tracker. Tasks are not required yet: they follow the
  plan approval.
- `show`: prints the plan and records its digest.
- Removed: `Draft`, `load_drafts`, `check_drafts`, `outline`, `publish`, `_create_all`,
  `_description`, `covers`, `_approved`, `DRAFTS_NAME`, `PUBLISHED`.
- `scripts/harness/cli.py`: remove `harness tracker publish` and `--drafts`.
- `scripts/harness/cli_workflow.py`, `scripts/harness/hook.py`: call `plan_review`.
- `scripts/harness/workflow_requirements.py`: `_plan` reads only the approved plan note (or the
  tracker's `implementation_plan` artifact); `bundle.covers` goes.
- Delete `references/tracker-drafts.md`.

**Tests:** replace `tests/harness/test_bundle.py` with `tests/harness/test_plan_review.py`: refused
with no plan, two artifacts, a non-plan note, a Story missing from the tracker, an unshown or
changed plan; accepted when shown unchanged. Hook test: approving `implementation-confirm` pins the
note and `plan_approved` holds. `harness tracker publish` is an unknown command. Rewrite
`tests/delivery/contract/test_knowledge_first_and_bundle_order.py` for the per-Story order.

### 4. Toolkit skills run as written

- Delete the "Six-stage preparation mode" sections of `generate-work-item`, `decompose-backlog`,
  `generate-breakdown-work-items`.
- Gate wiring through `harness decision present`: `decompose-backlog` Gate 1 → `refinement-split`,
  Gate 2 → `publish-items`; `generate-work-item` and `enrich-work-item` creation → `publish-items`;
  `generate-breakdown-work-items` PHASE 2 plan wait becomes required (`harness workflow show`, then
  `implementation-confirm --value story=<key>`), PHASE 3 Task selection → `publish-items`; fan-out
  runs plan and Tasks per Story.
- `amend-workitems`, `split-story`, `auto-fix-artifact`: approvals through `decision present`.
- Fix the copy defects from the toolkit's find-and-replace: `backup-and-artifacts path.md`, the
  `split-story` and `auto-fix-artifact` canonical paths, the `parent_id_artifacts path` field.

**Tests:** a contract test that no skill or reference mentions `tracker-drafts`,
`harness tracker publish` or "Six-stage preparation mode"; `generate-breakdown-work-items` names
`implementation-confirm` before Task creation; no broken relative links in the toolkit skills.

### 5. Specs

- `skills/write-spec/SKILL.md`: remove the "Six-stage preparation" section; it writes only the
  technical kinds still missing, with its critic review, approved with `approve-spec`; a spec that
  changes scope stops and goes back to refinement (`amend-workitems` / `enrich-work-item`).
- Drop the `implementation-plan` kind: `scripts/spec_runtime.py` (`SPEC_KINDS`,
  `DEFAULT_KINDS_BY_SIGNAL`), `scripts/artifact_profiles/spec.py`,
  `scripts/orchestrator/handlers.py`, and the `implementation-plan` template.

**Tests:** `spec_runtime` kinds and defaults no longer include `implementation-plan`; the spec
profile rejects it.

### 6. Sessions track the entry item

- `scripts/harness/work_sessions.py`: `Session` gains `entry_item` (an Epic, Feature, Story or Bug
  key), set by `harness work-session track --work-item <key>` when refinement first resolves the
  item the user started with. `work_item` stays the Story being implemented (the code gate's
  subject).
- `link` refuses a Story outside the entry item's tree (tracker parent chain); code baselines stay
  per work item.

**Tests:** track sets the entry item; link inside the tree succeeds; link outside is refused;
relinking Story to Story within one session keeps each Story's own baseline.

### 7. Refined Story and the idea route

- Discovery (`skills/bmad-build/` step 1 and `discovery.render`): when the request names a Story
  that has Tasks and an approved plan, present `refined-start`. "Deliver" saves a checkpoint at
  `execution` with `start-ticket` as next action; "front half" continues discovery.
- Refinement starts by asking whether the approach changed existing items, then routes to
  `amend-workitems` (Epic or Feature tree) or `enrich-work-item` plus the breakdown rules (one
  Story); the changed plan and Tasks are approved again.
- `ideate` ends with `idea-continue`; "stop" completes the workflow with the brief or spec as its
  output.

**Tests:** discovery render carries the refined-Story check; a `deliver` answer lands the workflow
at `execution`; `idea-continue` "stop" completes the workflow.

### 8. Feature close without Git

- `skills/finish-feature-development/SKILL.md`: a local mode when Git delivery is off — read the
  Feature and its Stories through the tracker, refuse while one is not done, publish closing
  evidence, one `move-item` approval, move the Feature to done. Steps 3–5 apply only with Git
  delivery.

**Tests:** contract test for both modes in the skill text; with Git delivery off, the verify stage
prepares `finish-feature-development` and no stack skills.

### 9. Preparation documents

- Risk and verification documents are each shown and approved with `approve-document` when
  created, saved in the artifacts path, and, with a remote tracker, published to the Story with
  `tracker_publish_artifact` so the team sees them where the work item lives. The reading manifest
  is harness state, not a user document.

**Tests:** the `approve-document` approval pins the document; editing it afterwards needs a new
approval.

### 10. Planning-folder files as code

- `scripts/policy/commands.py` `is_code`: with no source globs, nothing in the planning folder
  counts as code (today only `.md` and `acceptance-evidence/*.json[l]` are exempt) — trial 02
  finding 4.

**Tests:** a `.json`, `.yaml` and `.csv` file in the planning folder is not code; a file outside it
still is.

### 11. Rename and docs

- Rename "six-stage onboarding" to "onboarding": `references/six-stage-onboarding.md` →
  `references/onboarding.md`, `tests/harness/test_six_stage_recovery.py` →
  `test_onboarding_recovery.py`, `docs/02-design/specs/six-stage-onboarding-implementation.md`
  (refactored to the current route or deleted if the design doc covers it), and every mention in
  skills, references, catalog text, tests and docs. Trial evidence folders keep their recorded names.
- `references/workflow-storyboard.md`,
  `references/harness-stage-guide.md`, `references/human-decisions.md`, `skills/harness/SKILL.md`
  (no "one final bundle confirmation"), `skills/start-ticket`, `skills/implement-story`,
  `skills/feature-implementation`, `skills/branch-and-pr`.
- `docs/02-design/workflows.md`, `docs/02-design/specs/harness-main-flow.md` and its diagram,
  `docs/02-design/specs/six-stage-onboarding-implementation.md`.
- Plans, handoffs and checkpoints under `docs/06-delivery/` that describe the drafts flow, the
  older routes or the six-stage name as current are refactored or deleted; trial evidence and
  transcripts stay as records.
- `CHANGELOG.md`.

**Tests:** markdownlint; `check_repo.py`.

### 12. Branch verification

Full suites (backlog, plugin, installer scripts), `ruff check`, `ruff format --check`,
`check_repo.py`, markdownlint. Then handoff steps 4–6: trial setup, DAY-001 rerun, thermos review.
