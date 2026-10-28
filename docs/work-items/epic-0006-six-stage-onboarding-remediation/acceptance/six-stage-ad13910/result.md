---
title: Six-stage task-count acceptance result (Claude Code)
status: reached-confirmation-with-claude-question-defects
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-14
---

Host: Claude Code CLI, interactive, started in the fixture with the trial's own `TMPDIR` and `HARNESS_USER_STATE_DIR`.
Plugin: 0.6.2 installed from `ad13910`; the Claude plugin cache matched source (619 files).
Fixture: `temp/test-006/project`, unconfigured profile. Session `WS-fb43eefd702c`.

## Outcome

The workflow ran Discovery, Planning, Hardening, Preparation and Confirmation and stopped at execution entry.
At `implementation-confirm` the human chose **Stop here**. The bundle was not approved, and the workflow is
`paused` at the Confirmation stage with every artifact kept.

- Setup: local tracker, planning drafts in `backlog/`, confirmed by the human.
- Decisions: standalone work; planning depth Light; counts shown on one line.
- Artifacts in `backlog/`: discovery, approach, plan, plan memlog, spec, manifest, and unpublished tracker drafts.
- Boundaries held: no application code or test edits, no tracker items created, no remote writes.
  `git status` shows only new files under `.harness/`, `_bmad/` and `backlog/`.

## Defects found

1. **Native questions denied (blocking).** Of the five menus prepared with `harness decision present`, four were
   denied by the harness's own `AskUserQuestion` hook even though the agent sent them verbatim: setup-confirm,
   initiative, count wording and implementation-confirm. Only planning-depth went through natively. Cause:
   `Pending.matches_presentation` required the question `id`, which Claude's `AskUserQuestion` does not carry.
2. **Fallback refused (blocking).** The denial told the agent to run
   `harness decision fallback ... --host claude --native-unavailable`, and the waiting gate then refused that exact
   command, because `_fallback_options` accepted only `--async-available`. The agent escaped by switching to
   `--async-available`, or by asking in plain chat, and the human's typed replies were captured each time.
3. **Manifest hash goes stale (minor).** Logging the final "Stop here" answer appended to the memlog after the
   manifest recorded its SHA-256. Resuming needs a rebuilt manifest before approval is asked again.

Defects 1 and 2 are fixed in `467fe1c`, with Claude-host regression tests, including a replay of this trial's
free-text menu. Defect 3 is open.

## Not verified

- The fixes in `467fe1c` have not been through a live Claude trial; this run used `ad13910`.
- The raw transcript stays under `~/.claude/projects/` and is not committed.
