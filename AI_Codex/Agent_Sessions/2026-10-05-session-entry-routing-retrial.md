# Session entry routing retrial

## Trial setup

- Model: GPT-6 Luna, medium reasoning.
- Project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`.
- Candidate command: `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness`.
- Skill followed: `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/skills/harness/SKILL.md`.
- Exact request preserved: `Continue DAY-001 task counts — investigate the existing request and prepare its plan`.
- Scope: read-only; stop at first human-choice or related legacy-workflow gate.

## Commands and observations

The trial ran:

```text
/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness bootstrap --inspect --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project
/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness work-session route --request "Continue DAY-001 task counts — investigate the existing request and prepare its plan" --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project
```

Inspect reported a ready project, configured local tracker and settings, confirmed English, and a committed repository on `master` at `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`. It also reported an active project-wide legacy workflow at point 4 in backlog, labeled `Approved DAY-001 discovery plan`, with `docs/planning/DAY-001-task-counts-plan.md`. That workflow's saved request is `Bootstrap the harness and continue the existing request backlog/DAY-001-task-counts.md through planning and artifacts, stopping before implementation.` Policies are suspended.

For the exact request, routing returned `action: ask_user`, `session_id: null`, and `matches: []`. It returned these stopped candidates:

- `WS-22ebb757709f` — `Investigate DAY-001 task counts and prepare its plan.`
- `WS-66b279ef2af9` — `Investigate a separate task-count issue, DAY-002.`

The route output echoed the new request exactly. To verify matching separately, read-only route calls with each candidate's saved request returned `ask_user` and a match for the corresponding stopped session. The DAY-001 query still included both stopped sessions in its candidate list; the DAY-002 query likewise included both. Neither query selected or changed a session.

The agent stopped before displaying or asking a choice. The skill says `ask_user` should present all unfinished sessions and **Start a new session**, but also says that when a related project-wide legacy workflow exists, stop before creating another session because there is no safe way to choose or migrate that unbound workflow. The active legacy workflow is related to DAY-001, so that specific stop rule applies. The route output does not flag the legacy workflow or explain that the human-choice menu must be withheld; the agent must cross-check inspect output and apply the skill's legacy rule.

## Read count and limits

The Luna trial directly read one file: `harness/SKILL.md`. The inspect and route results came from command output, not direct file reads. This count does not include files the executable may read internally, and does not measure shell history, runtime file access, or files read before this trial.

No session was started, selected, resumed, paused, stopped, or completed; no question was asked or answered; and no checkpoint or artifact was written. The trial verifies only the candidate local executable against this disposable project. It does not verify the installed plugin, native host routing, or native question controls.
