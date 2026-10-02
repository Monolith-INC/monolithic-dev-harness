---
type: live-trial-log
project: Daybook
date: 2026-10-02
status: in-progress
host: Codex
tracker: local
---

# Daybook live trial

The trial uses a disposable copy of `test-project-template/`. The local tracker and language
preference are stored inside that temporary trial root. The user chose to keep the run local and
not create a pull request. No remote tracker or source-control writes have been made.

## Workflow progress

| Stage | Result |
| --- | --- |
| Prepare copy and install harness | Done in `/tmp/monolithic-dev-harness-trial-qj1wy9xw/project`; Codex reports healthy and the local tracker is ready. |
| Define the idea | Paused and redirected by the user. The user likes the Daybook concept, but says the product-ideation exercise is not the primary purpose of the harness’s first planning step. Keep it as a future optional path; review the technical-first flow before resuming the trial. |
| Backlog, technical plan, implementation, validation | Not started. |

## Issues and recoveries

| Workflow point | What went wrong | Effect | Recovery or current state |
| --- | --- | --- | --- |
| Repository preflight | The system Python did not have `pytest`, so the first test-suite command stopped before running tests. | The repository checks could not start with the default interpreter. | Used the project virtual environment, where the declared development dependency is installed. The suite then passed: 711 tests, 284 subtests, and the installer check. |
| Implementation quality check | Ruff flagged import ordering in the new disposable-copy helper. | The quality check failed. | Fixed the import order. Ruff and formatting checks now pass. |
| Verification command | The first version-check command used a nonexistent singular filename. | That check did not run. | Located and ran `scripts/check_versions.py`; all version sources agreed on 0.4.0. |
| Temporary host install | Codex warned that it could not create helper binaries under a temporary `CODEX_HOME`. | The warning could have prevented the host setup. | Plugin installation succeeded in the disposable Codex home; the harness doctor reported Codex installed. The temporary command directory was added to the host process path. |
| Host startup | The default shell sandbox blocked the Codex model and plugin-catalog network requests. | The first noninteractive Codex run could not start. | Reran the read-only host check with the approved network escalation and kept the child session restricted to the disposable project. |
| Host startup | An unsupported approval flag was passed to `codex exec`. | The CLI rejected the command before starting a session. | Removed the unsupported flag. The child CLI reports `approval: never`, so its run was limited to inspection and checkpointing; this did not exercise interactive approval gates. |
| Bootstrap | The first apply command omitted the settings choices used to create the proposal. | Bootstrap refused to apply the proposal and wrote no settings. | Repeated the proposal choices with the matching digests. Bootstrap then completed successfully. |
| Project setup | The template copy has no remote, while harness settings require GitHub or Azure Repos source control. | A real pull-request destination cannot be tested without creating a separate remote repository, which the user declined. | Used the user-approved, unused `local/daybook` GitHub settings placeholder. No GitHub calls or pull-request actions are allowed in this trial; source-control delivery remains untested. |
| First host checkpoint | The child Codex process did not inherit the temporary language-preference directory or helper command path. It reported the language as unset and the command as missing. | Its first checkpoint included a stale setup question. | Passed the temporary state directory to the harness and confirmed English. Verified that `.harness/state/` and `.harness/tracker/` are excluded by the trial repository's local Git rules. The child also reported a missing ignore rule, but that report was incorrect. |
| Flutter validation | The Puro launcher first tried to write global settings in a read-only location. A temporary Puro root that pointed at the installed SDK then failed while trying to write the SDK's `update.lock`. The Flutter tools snapshot is also absent from the installed SDK. | `flutter test` and full `flutter analyze` cannot run here. | Direct Dart formatting and analysis of `lib/domain/task.dart` passed using temporary user/cache folders. Flutter-level validation remains blocked by the incomplete SDK and Puro environment. |

## Evidence

- Full harness suite: 711 tests and 284 subtests passed; installer confirmation check passed.
- Ruff: all checks passed; all 371 Python files formatted.
- ShellCheck, Bash syntax, and version checks passed.
- Dart domain model analysis: no issues found; all four Dart files formatted.
- Harness doctor in the disposable project: healthy; Codex plugin installed; local tracker ready.
- No Flutter test run, pull request, remote tracker write, or push.

### Brainstorm checkpoint — 2026-10-02

The installed `brainstorm-ideas` skill saved 36 speculative situations and possible directions to the disposable copy at `docs/Planning/daybook/idea/.decision-log.md`. Each is labeled `[ASSUMPTION]`; there is no evidence, validated need, or selected feature. The skill stopped and asked the user to choose a moment before the topic was exhausted. The later user direction clarified that product ideation should be optional, so this branch is paused before any feature selection, backlog write, or code change. No remote source-control actions or pull requests were made.

| Workflow point | What went wrong | Effect | Recovery or current state |
| --- | --- | --- | --- |
| Trial ledger update | The shell could not find a command named `python`. | The brainstorm checkpoint and issue could not be appended on the first attempt. | Used `./.venv/bin/python` from the project; the ledger update and whitespace check completed. |
| Brainstorming | The installed skill stopped after 36 ideas and asked the user to pick one, although its guidance says to aim past 100 and continue until the topic is spent. | The trial ended the ideation pass early and shifted selection work to the user. | Recorded the observed behavior. The user clarified that ideation is an optional future route, so this run will not continue that branch. |

### User direction — 2026-10-02

The user clarified that the main first planning step should start from a rough product-owner request or draft requirement and make it technically concrete: inspect the real project, identify implementation constraints and flaws, compare viable approaches and trade-offs, and prepare a grounded proposal and implementation plan. The user clarified that ideation is valuable as an optional path, but it must not be the default. See `AI_Codex/Artifacts/stage-zero-technical-discovery-review.md` for the BMad comparison and proposed routing. The user also clarified that the fixture itself needs a clear product purpose, functioning baseline features, and a realistic product-owner request for an addition. The proposed app domain is a support-ticket desk, and the candidate request is merging duplicate tickets while preserving history; these still need the user’s confirmation before replacing the canonical template. Do not continue the Daybook ideation branch until the revised fixture and trial path are agreed.

| Workflow point | What went wrong | Effect | Recovery or current state |
| --- | --- | --- | --- |
| BMad reference research | The first lookup used a nonexistent English overview path. | That overview comparison did not run. | Used the actual BMad skill instructions as primary evidence and the available English planning guide at `docs/plan/design-ux-and-architecture.md`. |

Append each new failure or recovery here with its workflow stage as the trial continues.

### Technical-first trial — 2026-10-02

The technical-first trial was restarted from a fresh disposable copy at
`/tmp/monolithic-dev-harness-trial-ynlyr7ac/project`, using the request: “I can see how many tasks I
still need to do, but I also want to see how many I have finished. Show both counts on the task
screen.” The local harness setup and Stage 0 `bmad-build` workflow were prepared. The workflow then
stopped at checkpoint 2, “Working tree review,” because setup had created untracked files in
`.codex/`, `.harness/`, and `_bmad/`. Its clean-checkout gate required a decision before discovery
could continue.

**Outcome: inconclusive.** The agent followed the stop rule and did not inspect the feature, produce
a grounded proposal, or draft backlog items. No code was changed in the disposable copy. The pending
decision in the checkpoint is whether to keep the setup-generated files and continue, or clean the
checkout first. This run remains untouched so that decision does not rewrite its evidence. To get a
useful product-planning result, prepare a new disposable run with setup artifacts handled before the
feature request begins, then repeat the same request and observe Stage 0 through its review point.

### Clean-checkout rule review — 2026-10-02

The stop came from the explicit VCS sentence in the rendered BMad Step 1, not from a harness Git
guard: “If the tree is dirty or the branch is an obvious mismatch, HALT and ask the human before
proceeding.” Setup had just generated the untracked files. A developer's first run would therefore
have stopped before inspecting the requested feature and been asked to clean or approve the setup
files.

The harness's local `bmad-build/step-01-clarify-and-route.md` now treats dirty state and branch names
as evidence to inspect, not automatic stop conditions. It directs the agent to preserve all changes,
continue read-only discovery, treat unclear file ownership as user-owned, and ask only before a
specific conflicting write or a write that would land on an unintended branch. A fresh project copy
was rendered with the updated source while `_bmad/` was untracked. A focused check confirmed the
rendered Step 1 contains the continue-and-preserve instructions and no longer contains the old
dirty-tree halt. This verifies the rendered rule; a complete post-fix planning run has not yet been
performed. The sub-agent's retained transcript is in
`2026-10-02-daybook-stage-zero-subagent-transcript.md`.
