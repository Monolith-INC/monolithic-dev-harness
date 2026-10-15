# Lower-tier project work-session entry trial

Date: 2026-10-05
Model requested: GPT-6 Luna, medium reasoning
Project checkout: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Harness checkout: `/home/monolith/projects/monolithic-dev-harness`
Human request: “Investigate DAY-001 task counts and prepare its plan.”

## Result

This trial could not enter a usable independent work session through the installed command interface. `harness doctor` reports a healthy installation and local tracker, but the project checkout is on `master`; `harness session start DAY-001` refuses because the branch does not follow the configured `feature/{key}-{slug}` convention. I stopped at that first blocker. I did not switch branches, create a session, edit project files, or advance its saved workflow.

The installed `harness` command does not expose a `work-session` subcommand. The project does contain two stopped records under `.harness/state/work_sessions/`; one record has the exact request and a start/pause/resume/stop event history. Reading those records confirms persisted state exists, but does not establish that this agent created or controlled it in this trial. The harness's documented `harness session` is a separate checkout-to-work-item binding interface.

The project already has a planning document and saved workflow history, including a prior plan review/approval and a pending next step to draft local work items. Because the requested trial was specifically about independent work-session entry and forbade advancing existing workflow state, I did not read or edit the planning document, invoke workflow actions, or resume that prior planning sequence.

## Commands exercised

Commands were run from `/tmp/monolithic-dev-harness-trial-locw4ixf/project`, except the initial harness repository inspection. Counts below count command invocations, not shell statements bundled into a single invocation.

1. `pwd; rg --files -g 'AGENTS.md' -g 'README*' -g 'pyproject.toml' -g 'package.json' -g '*.md' | head -80; ls -la /tmp/monolithic-dev-harness-trial-locw4ixf/project` — located the repository entry material and prepared checkout.
2. `rg --files .agents .codex | head -100; rg -n "start.*session|work session|harness session|entry point|work-session" README.md docs .agents .codex scripts src 2>/dev/null | head -120` — looked for local instructions and session command documentation.
3. `cat README.md; cat backlog/DAY-001-task-counts.md; cat docs/00-context/current-state.md; cat .harness/config.json 2>/dev/null; ls -la .harness; ls -la .harness/state 2>/dev/null; sed -n '65,120p' /home/monolith/projects/monolithic-dev-harness/docs/07-guides/user-guide.md; sed -n '75,90p' /home/monolith/projects/monolithic-dev-harness/docs/02-design/api.md` — read request/context and documented entry paths. `.harness/config.json` was absent, so that attempted read returned no content.
4. `command -v harness` — found `/home/monolith/.local/bin/harness`.
5. `harness session status --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project` — reported no open session on `master`.
6. `harness doctor --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project` — reported version 0.5.2, valid settings, shipped local tracker, enforced tracking, and no open session; overall healthy.
7. `harness tracker list --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project` — listed shipped Azure DevOps, Linear, and Local trackers. It did not list local work items.
8. `find .harness/tracker -maxdepth 3 -type f -printf '%p\n'; find .harness/state/work_sessions -maxdepth 3 -type f -printf '%p\n'; git status --short --branch` — found no files in the tracked local tracker folder, two session records, and branch `master` with pre-existing untracked `.codex/`, `.harness/`, and `docs/planning/`.
9. `rg --files .harness/tracker .harness/state .codex docs/planning; cat .harness/settings.json; cat .harness/state/workflow.json; for f in .harness/state/work_sessions/*/session.json; do cat "$f"; done` — inspected settings, saved workflow, and both stopped session records.
10. `harness --help` — enumerated supported top-level commands (`session`, `workflow`, and others); no `work-session` command is available.
11. `harness work-session --help` — rejected `work-session` as an invalid command.
12. `harness session start DAY-001 --repo /tmp/monolithic-dev-harness-trial-locw4ixf/project` — refused with: `branch 'master' does not follow the convention 'feature/{key}-{slug}' with a work item key`.

## File read counts

There were 10 successful content reads relevant to the trial: 7 project files (`README.md`, `backlog/DAY-001-task-counts.md`, `docs/00-context/current-state.md`, `.harness/settings.json`, `.harness/state/workflow.json`, and two `.harness/state/work_sessions/*/session.json` files); 2 harness documentation files (`docs/07-guides/user-guide.md` and `docs/02-design/api.md`); and 1 memory registry entry (`/home/monolith/.codex/memories/MEMORY.md`). The attempted `.harness/config.json` read found no file. File listings and help output are not counted as file-content reads.

## Exercised behavior and limits

Actually exercised: installed harness discovery; read-only health, session-status, and tracker-list commands; help enumeration; rejection of the unknown `work-session` command; refusal to start a bound harness session on a nonconforming branch; and inspection of existing saved session/workflow state.

Not exercised or established: starting or controlling an independent work session from the native Codex host; whether the pre-existing `work_sessions` records were written by a native host integration; native host handoff, pause/resume control, approval UI, or transcript retention; any end-to-end bridge between host agent threads and harness session records. The files show stored records, not a working integration. No tracker item was created, read via a tracker command, or changed.

No project workflow or tracker state was modified by this trial. The only new file is this trial transcript in the harness repository.
