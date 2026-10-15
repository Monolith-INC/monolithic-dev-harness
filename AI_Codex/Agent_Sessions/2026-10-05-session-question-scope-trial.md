# Session-scoped question trial

Date: 2026-10-05
Project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Model: GPT-6 Luna, medium reasoning
Purpose: Check that a pending question belongs to its selected project work session.

## Setup

Created two active project work sessions:

- `WS-7d295fced37a` — “Focused question scope test A”
- `WS-c0f2d2586683` — “Focused question scope test B”

Recorded a `Continue` / `Stop` question only in session A. The candidate reported A as pending and
B as clear.

## Lower-tier run

Started a read-only Codex run against the test project with GPT-6 Luna at medium reasoning. The run
created host session `01a10b3b-5c99-78f1-911b-237a50f41985`. Its shell tools failed before reading
the project because the app-server socket directory did not meet the required ownership and mode.
The agent made no changes and did not answer the question. There were two failed shell attempts and
zero successful project reads. The retained JSONL transcript is
`AI_Codex/Agent_Sessions/2026-10-05-session-question-scope-trial.jsonl`.

## Candidate hook check

Bound that native Codex session id to work session B using the candidate adapter, then sent the
candidate Codex prompt hook a `Continue` test message for the bound host session. Session A's
question remained pending with an empty answer, and session B remained clear. This directly checks
candidate session routing with a real host id. It does not establish automatic hook delivery from
the installed plugin, because the lower-tier run could not start its shell tool.

## Result and remaining check

The scoped pending-question route passed; no project source or decision was changed. Automated
coverage passed with 786 tests and 286 subtests, and Ruff passed. Repeat this check in a fresh host
session after installing/reloading the candidate package. Test Codex and Claude native session
delivery; Cursor currently has no native session id in its adapter. Approval windows remain
project-wide and are outside this check.
