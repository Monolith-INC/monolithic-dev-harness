# Session Entry Routing Trial — 2026-10-05

## Scope

Tested only project-session discovery and routing for the exact user request:

> Continue DAY-001 task counts — investigate the existing request and prepare its plan

The trial stopped at the first routing blocker. No session was started, selected, resumed, or changed. No workflow, tracker record, setting, or project file was edited. The only file written was this report.

## Setup and exact commands

Candidate project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`

Candidate command: `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness`

Candidate skill: `/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/skills/harness/SKILL.md`

Read the candidate skill with:

```sh
sed -n '1,240p' /home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/skills/harness/SKILL.md
```

The skill says to inspect the supplied project, then use `harness work-session route --request` to identify whether to continue an active exact match, start a new session, or ask the human to choose. It says routing itself never starts or resumes a session, and paused/stopped sessions must not be resumed silently.

Inspected the project using:

```sh
/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness bootstrap --inspect --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project
```

Observed: setup reports `ready`; the shared tracker is local; the repository is on `master`; and a project-wide workflow is active at backlog point 4. That workflow records an approved DAY-001 discovery plan and the request “Bootstrap the harness and continue the existing request backlog/DAY-001-task-counts.md through planning and artifacts, stopping before implementation.” Its saved artifact is `docs/planning/DAY-001-task-counts-plan.md`.

Listed session files with:

```sh
find .harness/state/work_sessions -maxdepth 2 -type f -name session.json -print 2>/dev/null | sort
```

Read the two listed session records. `WS-22ebb757709f` is stopped and records “Investigate DAY-001 task counts and prepare its plan.” `WS-66b279ef2af9` is stopped and records a separate DAY-002 task-count issue. Both also have session-specific workflow files.

Ran the exact routing request:

```sh
/home/monolith/projects/monolithic-dev-harness/plugins/monolithic-dev-harness/bin/harness work-session route --request "Continue DAY-001 task counts — investigate the existing request and prepare its plan" --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project
```

Observed output:

```json
{
  "request": "continue day-001 task counts — investigate the existing request and prepare its plan",
  "action": "start_new",
  "session_id": null,
  "matches": []
}
```

## Result and blocker

Routing did not surface the stopped DAY-001 session as a human-choice gate, even though its saved request is clearly related to the exact request. It also did not surface the active project-wide DAY-001 workflow as legacy state. The command lowercased the supplied request in its output and returned no candidates. The skill would direct the agent to create a session for `start_new`, but this trial does not do so: creating one would bypass the unresolved choice about existing DAY-001 work.

This does not prove that the matcher is wrong to require exact requests; it proves the current behavior does not meet the tested safe-entry expectation for a paused/stopped related session. The route needs to expose related candidates (including their status and saved request) for a human choice, while keeping routing read-only. The legacy workflow also needs an explicit safe presentation or other defined handling so it is not overlooked.

## Read count and host coverage

Three project/workflow/session file contents were read directly during the trial: the skill file and the two `session.json` records. `bootstrap --inspect` and `work-session route` may read additional files internally; those reads are not exposed by the commands, so their count is unknown. Directory listings do not count as file-content reads.

This exercised the candidate bundled command in a local shell against the disposable project. It did not test an installed skill invocation or a native Codex/host UI. The lower-tier model assignment for this trial was GPT-6 Luna at medium reasoning; no higher-tier model was used.
