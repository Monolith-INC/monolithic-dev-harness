# Harness baseline trial evidence

## Scope
Trial project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`. Request: bootstrap and continue `backlog/DAY-001-task-counts.md` through planning and artifacts, stopping before implementation.

## Initialization inspection
Command: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Working directory: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Relevant actual output: status `missing`; language `en`, `language_confirmed: false`; missing `tracker.tracker` and `artifacts_path`; Git present with committed HEAD `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`; available trackers are Azure DevOps Boards (organization, project), Linear (team), and Local tracker (no required values). `tracker_storage` and `workflow` are empty.

A first attempt using relative `bin/harness` returned `/bin/bash: line 1: bin/harness: No such file or directory`; the installed absolute executable above then succeeded.

## Current stage
Bootstrap; waiting on required project-language choice. No harness settings, tracker records, workflow artifacts, branches, or source files have been changed by this agent.

## Human decision and language save blocker
Human response relayed by root: `English`.

Read-only command used to check preference behavior: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference show --repo .`
Actual output: `en`.

Attempted the documented save command with the disposable project as repository: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `/home/monolith/.config/monolithic-dev-harness/preferences.json: [Errno 30] Read-only file system: '/home/monolith/.config/monolithic-dev-harness/preferences.json.tmp'`.

Blocker: even with `--repo .`, the supported command targets the host-level preference file under `/home/monolith/.config`, which is read-only and outside the authorized trial scope. No supported trial-local preference store was shown by the command interface. Stopped here without changing global preferences or continuing setup.

## Run identity and limits

Date: 2026-10-05. Installed harness manifest: 0.5.2.
Test agent: GPT-6 Luna, medium reasoning, as requested and accepted by the delegation tool.
No independent provider telemetry or token-usage measurement was available for this report.
Host: delegated native agent in this Codex desktop chat; questions relayed to the actual human
through the desktop question control. Local installed commands explicitly targeted the trial.
This was not a separate installed host session rooted at the disposable project. Project-specific
hook activation and workspace-bound gateway coverage were not verified.

The agent initially used an incorrect relative executable path, then located the installed
absolute executable; that invocation error is retained above and is not attributed to the harness.
The actual initialization sequence stopped at language persistence. The final agent label
WAITING_FOR_USER was inaccurate: the observed result is BLOCKED, and the run is stopped.

The failure establishes a host-level write dependency under this sandbox. It does not establish
that the command fails on an unrestricted host or that no possible isolation configuration exists.
No permissions escalation, repair, model upgrade, or workaround was attempted after this failure.
Planning, BMAD execution, tracker operations, and implementation remain untested in this run.
The disposable copy is retained for inspection; no real test-project changes were made.

## Recovery authorized by the human

The human requested fixing the blocker and recovering the same run. Inspection of installed
preferences.py establishes that HARNESS_USER_STATE_DIR already supplies an isolated preference
location. Existing test_workflow.py tests use this setting. The earlier command-interface lookup
missed it; this is a trial-preparation omission, not proof that the installed harness lacks isolation.
The resumed agent is instructed to use /tmp/monolithic-dev-harness-trial-locw4ixf/user-state for
that setting on every invocation, retry the authentic English decision, and stop at the next new
blocker or before implementation. No runtime code change is needed for this recovery.

## Recovered trial: current evidence

# Harness baseline trial evidence

## Scope
Trial project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`. Request: bootstrap and continue `backlog/DAY-001-task-counts.md` through planning and artifacts, stopping before implementation.

## Initialization inspection
Command: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Working directory: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Relevant actual output: status `missing`; language `en`, `language_confirmed: false`; missing `tracker.tracker` and `artifacts_path`; Git present with committed HEAD `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`; available trackers are Azure DevOps Boards (organization, project), Linear (team), and Local tracker (no required values). `tracker_storage` and `workflow` are empty.

A first attempt using relative `bin/harness` returned `/bin/bash: line 1: bin/harness: No such file or directory`; the installed absolute executable above then succeeded.

## Current stage
Bootstrap; waiting on required project-language choice. No harness settings, tracker records, workflow artifacts, branches, or source files have been changed by this agent.

## Human decision and language save blocker
Human response relayed by root: `English`.

Read-only command used to check preference behavior: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference show --repo .`
Actual output: `en`.

Attempted the documented save command with the disposable project as repository: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `/home/monolith/.config/monolithic-dev-harness/preferences.json: [Errno 30] Read-only file system: '/home/monolith/.config/monolithic-dev-harness/preferences.json.tmp'`.

Blocker: even with `--repo .`, the supported command targets the host-level preference file under `/home/monolith/.config`, which is read-only and outside the authorized trial scope. No supported trial-local preference store was shown by the command interface. Stopped here without changing global preferences or continuing setup.

## Recovery with supported isolated user state
Correction from root: the installed preference command supports `HARNESS_USER_STATE_DIR`; my prior conclusion that no supported trial-local option existed was incorrect because I had only checked command-line help. Used the supported environment setting on every subsequent harness invocation, scoped to `/tmp/monolithic-dev-harness-trial-locw4ixf/user-state`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `preferred language: en`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Actual result: `language_confirmed: true`; setup remains `missing`, with `tracker.tracker` and `artifacts_path` missing. Available trackers remain Azure DevOps Boards, Linear, and Local tracker. No workflow or tracker storage is initialized yet.

Current stage: bootstrap, waiting for an authentic tracker choice. No tracker or artifact path has been selected, and no tracker records or planning artifacts have been created.

The actual human was asked to choose the tracker; no tracker selected yet.

## Next observed blocker

# Harness baseline trial evidence

## Scope
Trial project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`. Request: bootstrap and continue `backlog/DAY-001-task-counts.md` through planning and artifacts, stopping before implementation.

## Initialization inspection
Command: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Working directory: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Relevant actual output: status `missing`; language `en`, `language_confirmed: false`; missing `tracker.tracker` and `artifacts_path`; Git present with committed HEAD `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`; available trackers are Azure DevOps Boards (organization, project), Linear (team), and Local tracker (no required values). `tracker_storage` and `workflow` are empty.

A first attempt using relative `bin/harness` returned `/bin/bash: line 1: bin/harness: No such file or directory`; the installed absolute executable above then succeeded.

## Current stage
Bootstrap; waiting on required project-language choice. No harness settings, tracker records, workflow artifacts, branches, or source files have been changed by this agent.

## Human decision and language save blocker
Human response relayed by root: `English`.

Read-only command used to check preference behavior: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference show --repo .`
Actual output: `en`.

Attempted the documented save command with the disposable project as repository: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `/home/monolith/.config/monolithic-dev-harness/preferences.json: [Errno 30] Read-only file system: '/home/monolith/.config/monolithic-dev-harness/preferences.json.tmp'`.

Blocker: even with `--repo .`, the supported command targets the host-level preference file under `/home/monolith/.config`, which is read-only and outside the authorized trial scope. No supported trial-local preference store was shown by the command interface. Stopped here without changing global preferences or continuing setup.

## Recovery with supported isolated user state
Correction from root: the installed preference command supports `HARNESS_USER_STATE_DIR`; my prior conclusion that no supported trial-local option existed was incorrect because I had only checked command-line help. Used the supported environment setting on every subsequent harness invocation, scoped to `/tmp/monolithic-dev-harness-trial-locw4ixf/user-state`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `preferred language: en`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Actual result: `language_confirmed: true`; setup remains `missing`, with `tracker.tracker` and `artifacts_path` missing. Available trackers remain Azure DevOps Boards, Linear, and Local tracker. No workflow or tracker storage is initialized yet.

Current stage: bootstrap, waiting for an authentic tracker choice. No tracker or artifact path has been selected, and no tracker records or planning artifacts have been created.

## Human tracker choice and local-tracker preparation failure
Authentic human choice relayed by root: `Local tracker — in the disposable test project`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --prepare-local-tracker`
Actual output: `.harness/settings.json could not be read: [Errno 2] No such file or directory: '/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/settings.json'`.

Problems found: local-tracker preparation cannot run before repository settings exist. Observed cause is missing `.harness/settings.json`; whether the command expects settings to be created by applying the setup proposal is an inference, not yet verified. No recovery or alternate command has been attempted. Trial stopped at this failure pending direction.

Root checked installed setup.py: tracker preparation requires saved settings. The agent confused the pending human selection with configured tracker state. Run remains stopped; this is not verified as a tracker defect.

## Correct setup proposal reached

# Harness baseline trial evidence

## Scope
Trial project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`. Request: bootstrap and continue `backlog/DAY-001-task-counts.md` through planning and artifacts, stopping before implementation.

## Initialization inspection
Command: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Working directory: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Relevant actual output: status `missing`; language `en`, `language_confirmed: false`; missing `tracker.tracker` and `artifacts_path`; Git present with committed HEAD `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`; available trackers are Azure DevOps Boards (organization, project), Linear (team), and Local tracker (no required values). `tracker_storage` and `workflow` are empty.

A first attempt using relative `bin/harness` returned `/bin/bash: line 1: bin/harness: No such file or directory`; the installed absolute executable above then succeeded.

## Current stage
Bootstrap; waiting on required project-language choice. No harness settings, tracker records, workflow artifacts, branches, or source files have been changed by this agent.

## Human decision and language save blocker
Human response relayed by root: `English`.

Read-only command used to check preference behavior: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference show --repo .`
Actual output: `en`.

Attempted the documented save command with the disposable project as repository: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `/home/monolith/.config/monolithic-dev-harness/preferences.json: [Errno 30] Read-only file system: '/home/monolith/.config/monolithic-dev-harness/preferences.json.tmp'`.

Blocker: even with `--repo .`, the supported command targets the host-level preference file under `/home/monolith/.config`, which is read-only and outside the authorized trial scope. No supported trial-local preference store was shown by the command interface. Stopped here without changing global preferences or continuing setup.

## Recovery with supported isolated user state
Correction from root: the installed preference command supports `HARNESS_USER_STATE_DIR`; my prior conclusion that no supported trial-local option existed was incorrect because I had only checked command-line help. Used the supported environment setting on every subsequent harness invocation, scoped to `/tmp/monolithic-dev-harness-trial-locw4ixf/user-state`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `preferred language: en`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Actual result: `language_confirmed: true`; setup remains `missing`, with `tracker.tracker` and `artifacts_path` missing. Available trackers remain Azure DevOps Boards, Linear, and Local tracker. No workflow or tracker storage is initialized yet.

Current stage: bootstrap, waiting for an authentic tracker choice. No tracker or artifact path has been selected, and no tracker records or planning artifacts have been created.

## Human tracker choice and local-tracker preparation failure
Authentic human choice relayed by root: `Local tracker — in the disposable test project`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --prepare-local-tracker`
Actual output: `.harness/settings.json could not be read: [Errno 2] No such file or directory: '/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/settings.json'`.

Problems found: local-tracker preparation cannot run before repository settings exist. Observed cause is missing `.harness/settings.json`; whether the command expects settings to be created by applying the setup proposal is an inference, not yet verified. No recovery or alternate command has been attempted. Trial stopped at this failure pending direction.

## Recovery from tracker-preparation sequencing failure
Root confirmed the installed preparation command loads saved settings and there were none. The preparation error therefore reflects command ordering before setup application; it is not evidence of a local-tracker defect. Per direction, did not retry preparation or create settings manually.

Inspected trial project documentation conventions. `backlog/README.md` says its work items are local drafts and identifies DAY-001 as the suggested first trial. `docs/README.md` organizes project documentation under `docs/00-context`, `docs/01-product`, `docs/02-design`, and `docs/03-engineering`. Based on those conventions, proposed `docs/planning` as the harness planning-draft destination.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --propose --tracker local --artifacts-path docs/planning`
Actual candidate values: tracker `local`; SCM `local`; artifacts path `docs/planning`; branch template `feature/{key}-{slug}`; schema version `1`.
Actual digest: `69303992ec0dd397c5f19f45a5e37301787d23de8184c5e002833767736038f0`.
Actual source digest: `57658985bc7bcdb1cc50fd7791c372def590d3be9bc04d7a4f551ffc5a032ce6`.

Current stage: setup proposal review. Waiting for authentic approval to apply this exact local setup proposal or a choice to change the setup. Proposal has not been applied; no tracker records or planning artifacts have been created.

Setup application review is pending the actual human choice.

## Approved setup applied and checked

# Harness baseline trial evidence

## Scope
Trial project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`. Request: bootstrap and continue `backlog/DAY-001-task-counts.md` through planning and artifacts, stopping before implementation.

## Initialization inspection
Command: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Working directory: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Relevant actual output: status `missing`; language `en`, `language_confirmed: false`; missing `tracker.tracker` and `artifacts_path`; Git present with committed HEAD `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`; available trackers are Azure DevOps Boards (organization, project), Linear (team), and Local tracker (no required values). `tracker_storage` and `workflow` are empty.

A first attempt using relative `bin/harness` returned `/bin/bash: line 1: bin/harness: No such file or directory`; the installed absolute executable above then succeeded.

## Current stage
Bootstrap; waiting on required project-language choice. No harness settings, tracker records, workflow artifacts, branches, or source files have been changed by this agent.

## Human decision and language save blocker
Human response relayed by root: `English`.

Read-only command used to check preference behavior: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference show --repo .`
Actual output: `en`.

Attempted the documented save command with the disposable project as repository: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `/home/monolith/.config/monolithic-dev-harness/preferences.json: [Errno 30] Read-only file system: '/home/monolith/.config/monolithic-dev-harness/preferences.json.tmp'`.

Blocker: even with `--repo .`, the supported command targets the host-level preference file under `/home/monolith/.config`, which is read-only and outside the authorized trial scope. No supported trial-local preference store was shown by the command interface. Stopped here without changing global preferences or continuing setup.

## Recovery with supported isolated user state
Correction from root: the installed preference command supports `HARNESS_USER_STATE_DIR`; my prior conclusion that no supported trial-local option existed was incorrect because I had only checked command-line help. Used the supported environment setting on every subsequent harness invocation, scoped to `/tmp/monolithic-dev-harness-trial-locw4ixf/user-state`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `preferred language: en`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Actual result: `language_confirmed: true`; setup remains `missing`, with `tracker.tracker` and `artifacts_path` missing. Available trackers remain Azure DevOps Boards, Linear, and Local tracker. No workflow or tracker storage is initialized yet.

Current stage: bootstrap, waiting for an authentic tracker choice. No tracker or artifact path has been selected, and no tracker records or planning artifacts have been created.

## Human tracker choice and local-tracker preparation failure
Authentic human choice relayed by root: `Local tracker — in the disposable test project`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --prepare-local-tracker`
Actual output: `.harness/settings.json could not be read: [Errno 2] No such file or directory: '/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/settings.json'`.

Problems found: local-tracker preparation cannot run before repository settings exist. Observed cause is missing `.harness/settings.json`; whether the command expects settings to be created by applying the setup proposal is an inference, not yet verified. No recovery or alternate command has been attempted. Trial stopped at this failure pending direction.

## Recovery from tracker-preparation sequencing failure
Root confirmed the installed preparation command loads saved settings and there were none. The preparation error therefore reflects command ordering before setup application; it is not evidence of a local-tracker defect. Per direction, did not retry preparation or create settings manually.

Inspected trial project documentation conventions. `backlog/README.md` says its work items are local drafts and identifies DAY-001 as the suggested first trial. `docs/README.md` organizes project documentation under `docs/00-context`, `docs/01-product`, `docs/02-design`, and `docs/03-engineering`. Based on those conventions, proposed `docs/planning` as the harness planning-draft destination.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --propose --tracker local --artifacts-path docs/planning`
Actual candidate values: tracker `local`; SCM `local`; artifacts path `docs/planning`; branch template `feature/{key}-{slug}`; schema version `1`.
Actual digest: `69303992ec0dd397c5f19f45a5e37301787d23de8184c5e002833767736038f0`.
Actual source digest: `57658985bc7bcdb1cc50fd7791c372def590d3be9bc04d7a4f551ffc5a032ce6`.

Current stage: setup proposal review. Waiting for authentic approval to apply this exact local setup proposal or a choice to change the setup. Proposal has not been applied; no tracker records or planning artifacts have been created.

## Setup approval, application, and verification
Authentic human approval relayed by root: setup review question `Apply this setup to the test copy: local work items, plans in docs/planning, and local source control?`; answer `Apply setup`. This approval covered only the exact proposal digests recorded above. Root-relayed native approval is genuine user authorization; this delegated run does not establish native hook enforcement.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --propose --tracker local --artifacts-path docs/planning --apply-digest 69303992ec0dd397c5f19f45a5e37301787d23de8184c5e002833767736038f0 --source-digest 57658985bc7bcdb1cc50fd7791c372def590d3be9bc04d7a4f551ffc5a032ce6`
Actual result: wrote trial `.harness/settings.json`; wrote `.codex/config.toml` enabling request_user_input; selected `Local tracker (shipped)`; created knowledge with SHA-256 `a3ca24545234a769b5080139c8a353bb3b2bfbb52159e0365d95db9e3a523bb5`; result `{"setup": "ready"}`.

Ran the one required doctor check:
Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness doctor`
Actual result: healthy. Python, Git, npx, Claude Code, Cursor, and Codex checks passed. Settings valid; Local tracker folders exist at trial `.harness/tracker`; tracking enforced; no open session on branch `master` in this checkout.

Current stage: post-setup routing to the original request. No workflow has been started and no backlog or planning artifact has been drafted yet.

Post-setup routing choice is pending. No implementation started.

## Discovery reached plan review

# Harness baseline trial evidence

## Scope
Trial project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`. Request: bootstrap and continue `backlog/DAY-001-task-counts.md` through planning and artifacts, stopping before implementation.

## Initialization inspection
Command: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Working directory: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Relevant actual output: status `missing`; language `en`, `language_confirmed: false`; missing `tracker.tracker` and `artifacts_path`; Git present with committed HEAD `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`; available trackers are Azure DevOps Boards (organization, project), Linear (team), and Local tracker (no required values). `tracker_storage` and `workflow` are empty.

A first attempt using relative `bin/harness` returned `/bin/bash: line 1: bin/harness: No such file or directory`; the installed absolute executable above then succeeded.

## Current stage
Bootstrap; waiting on required project-language choice. No harness settings, tracker records, workflow artifacts, branches, or source files have been changed by this agent.

## Human decision and language save blocker
Human response relayed by root: `English`.

Read-only command used to check preference behavior: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference show --repo .`
Actual output: `en`.

Attempted the documented save command with the disposable project as repository: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `/home/monolith/.config/monolithic-dev-harness/preferences.json: [Errno 30] Read-only file system: '/home/monolith/.config/monolithic-dev-harness/preferences.json.tmp'`.

Blocker: even with `--repo .`, the supported command targets the host-level preference file under `/home/monolith/.config`, which is read-only and outside the authorized trial scope. No supported trial-local preference store was shown by the command interface. Stopped here without changing global preferences or continuing setup.

## Recovery with supported isolated user state
Correction from root: the installed preference command supports `HARNESS_USER_STATE_DIR`; my prior conclusion that no supported trial-local option existed was incorrect because I had only checked command-line help. Used the supported environment setting on every subsequent harness invocation, scoped to `/tmp/monolithic-dev-harness-trial-locw4ixf/user-state`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `preferred language: en`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Actual result: `language_confirmed: true`; setup remains `missing`, with `tracker.tracker` and `artifacts_path` missing. Available trackers remain Azure DevOps Boards, Linear, and Local tracker. No workflow or tracker storage is initialized yet.

Current stage: bootstrap, waiting for an authentic tracker choice. No tracker or artifact path has been selected, and no tracker records or planning artifacts have been created.

## Human tracker choice and local-tracker preparation failure
Authentic human choice relayed by root: `Local tracker — in the disposable test project`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --prepare-local-tracker`
Actual output: `.harness/settings.json could not be read: [Errno 2] No such file or directory: '/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/settings.json'`.

Problems found: local-tracker preparation cannot run before repository settings exist. Observed cause is missing `.harness/settings.json`; whether the command expects settings to be created by applying the setup proposal is an inference, not yet verified. No recovery or alternate command has been attempted. Trial stopped at this failure pending direction.

## Recovery from tracker-preparation sequencing failure
Root confirmed the installed preparation command loads saved settings and there were none. The preparation error therefore reflects command ordering before setup application; it is not evidence of a local-tracker defect. Per direction, did not retry preparation or create settings manually.

Inspected trial project documentation conventions. `backlog/README.md` says its work items are local drafts and identifies DAY-001 as the suggested first trial. `docs/README.md` organizes project documentation under `docs/00-context`, `docs/01-product`, `docs/02-design`, and `docs/03-engineering`. Based on those conventions, proposed `docs/planning` as the harness planning-draft destination.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --propose --tracker local --artifacts-path docs/planning`
Actual candidate values: tracker `local`; SCM `local`; artifacts path `docs/planning`; branch template `feature/{key}-{slug}`; schema version `1`.
Actual digest: `69303992ec0dd397c5f19f45a5e37301787d23de8184c5e002833767736038f0`.
Actual source digest: `57658985bc7bcdb1cc50fd7791c372def590d3be9bc04d7a4f551ffc5a032ce6`.

Current stage: setup proposal review. Waiting for authentic approval to apply this exact local setup proposal or a choice to change the setup. Proposal has not been applied; no tracker records or planning artifacts have been created.

## Setup approval, application, and verification
Authentic human approval relayed by root: setup review question `Apply this setup to the test copy: local work items, plans in docs/planning, and local source control?`; answer `Apply setup`. This approval covered only the exact proposal digests recorded above. Root-relayed native approval is genuine user authorization; this delegated run does not establish native hook enforcement.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --propose --tracker local --artifacts-path docs/planning --apply-digest 69303992ec0dd397c5f19f45a5e37301787d23de8184c5e002833767736038f0 --source-digest 57658985bc7bcdb1cc50fd7791c372def590d3be9bc04d7a4f551ffc5a032ce6`
Actual result: wrote trial `.harness/settings.json`; wrote `.codex/config.toml` enabling request_user_input; selected `Local tracker (shipped)`; created knowledge with SHA-256 `a3ca24545234a769b5080139c8a353bb3b2bfbb52159e0365d95db9e3a523bb5`; result `{"setup": "ready"}`.

Ran the one required doctor check:
Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness doctor`
Actual result: healthy. Python, Git, npx, Claude Code, Cursor, and Codex checks passed. Settings valid; Local tracker folders exist at trial `.harness/tracker`; tracking enforced; no open session on branch `master` in this checkout.

Current stage: post-setup routing to the original request. No workflow has been started and no backlog or planning artifact has been drafted yet.

## Discovery instructions actually loaded and request investigation
After authentic choice `Continue DAY-001 task counts — investigate the existing request and prepare its plan`, read the installed `skills/bmad-build/SKILL.md`, `skills/harness/references/technical-discovery.md`, and `references/workflow-storyboard.md`. The technical-discovery document supplies six numbered local steps (resolve request, inspect relevant code, compare approaches, prepare plan, review, save progress); the run followed these instructions. No generated or project-copied BMad workflow, numbered BMad module, renderer, or module installation was entered or run.

Started the workflow with the original request using `harness workflow start --request ...`; actual result status `active`, stage `setup`, request preserved verbatim. Read the named file `backlog/DAY-001-task-counts.md` directly, the linked/current product and engineering notes, and relevant current code in `lib/domain/task.dart`, `lib/application/daybook_providers.dart`, `lib/presentation/task_list_page.dart`, `lib/domain/auth.dart`, `lib/main.dart`, `lib/presentation/login_page.dart`, `test/domain/task_test.dart`, and `pubspec.yaml`.

Discovery finding: the task screen already computes active tasks from the full list before filtering. It has no completed count. The existing immutable task state already contains completion status, so the plan keeps count calculation in the screen and adds widget coverage for both counts, pluralization, state updates, and independence from search/filters. No source code or tests were changed or run.

Wrote the plan at `docs/planning/DAY-001-task-counts-plan.md`. Content SHA-256 recorded by the workflow: `962d563a6f54648ab1376f820ca16feb9c9ec5358f0bdd069ea51e12614c4968`.

Checkpoint command used `harness workflow checkpoint --point 2 --stage discover --label 'DAY-001 technical plan' --artifact docs/planning/DAY-001-task-counts-plan.md --pending 'Human review: approve, revise, or stop this technical plan' --next-action 'On approval, continue to local backlog drafting; stop before implementation.'`. Actual result contains discovery point 2, the artifact path and SHA-256, pending human review, and the next action to continue local backlog drafting only on approval. Workflow remains active. No implementation session, branch, tracker transition, tracker item, or source edit was created.

Current stage: discovery plan review; waiting for human approval, revision, or stop choice.

Root retained a copy of the exact discovery artifact at AI_Codex/Artifacts/2026-10-05-trial-DAY-001-plan.md. Review pending; no tests or implementation performed.

## Approved plan, backlog handoff, and stop

# Harness baseline trial evidence

## Scope
Trial project: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`. Request: bootstrap and continue `backlog/DAY-001-task-counts.md` through planning and artifacts, stopping before implementation.

## Initialization inspection
Command: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Working directory: `/tmp/monolithic-dev-harness-trial-locw4ixf/project`
Relevant actual output: status `missing`; language `en`, `language_confirmed: false`; missing `tracker.tracker` and `artifacts_path`; Git present with committed HEAD `a2549ed11e043ba65c6a380f43c3bbe1a2d22c30`; available trackers are Azure DevOps Boards (organization, project), Linear (team), and Local tracker (no required values). `tracker_storage` and `workflow` are empty.

A first attempt using relative `bin/harness` returned `/bin/bash: line 1: bin/harness: No such file or directory`; the installed absolute executable above then succeeded.

## Current stage
Bootstrap; waiting on required project-language choice. No harness settings, tracker records, workflow artifacts, branches, or source files have been changed by this agent.

## Human decision and language save blocker
Human response relayed by root: `English`.

Read-only command used to check preference behavior: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference show --repo .`
Actual output: `en`.

Attempted the documented save command with the disposable project as repository: `/home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `/home/monolith/.config/monolithic-dev-harness/preferences.json: [Errno 30] Read-only file system: '/home/monolith/.config/monolithic-dev-harness/preferences.json.tmp'`.

Blocker: even with `--repo .`, the supported command targets the host-level preference file under `/home/monolith/.config`, which is read-only and outside the authorized trial scope. No supported trial-local preference store was shown by the command interface. Stopped here without changing global preferences or continuing setup.

## Recovery with supported isolated user state
Correction from root: the installed preference command supports `HARNESS_USER_STATE_DIR`; my prior conclusion that no supported trial-local option existed was incorrect because I had only checked command-line help. Used the supported environment setting on every subsequent harness invocation, scoped to `/tmp/monolithic-dev-harness-trial-locw4ixf/user-state`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness preference language en --repo .`
Actual output: `preferred language: en`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --inspect`
Actual result: `language_confirmed: true`; setup remains `missing`, with `tracker.tracker` and `artifacts_path` missing. Available trackers remain Azure DevOps Boards, Linear, and Local tracker. No workflow or tracker storage is initialized yet.

Current stage: bootstrap, waiting for an authentic tracker choice. No tracker or artifact path has been selected, and no tracker records or planning artifacts have been created.

## Human tracker choice and local-tracker preparation failure
Authentic human choice relayed by root: `Local tracker — in the disposable test project`.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --prepare-local-tracker`
Actual output: `.harness/settings.json could not be read: [Errno 2] No such file or directory: '/tmp/monolithic-dev-harness-trial-locw4ixf/project/.harness/settings.json'`.

Problems found: local-tracker preparation cannot run before repository settings exist. Observed cause is missing `.harness/settings.json`; whether the command expects settings to be created by applying the setup proposal is an inference, not yet verified. No recovery or alternate command has been attempted. Trial stopped at this failure pending direction.

## Recovery from tracker-preparation sequencing failure
Root confirmed the installed preparation command loads saved settings and there were none. The preparation error therefore reflects command ordering before setup application; it is not evidence of a local-tracker defect. Per direction, did not retry preparation or create settings manually.

Inspected trial project documentation conventions. `backlog/README.md` says its work items are local drafts and identifies DAY-001 as the suggested first trial. `docs/README.md` organizes project documentation under `docs/00-context`, `docs/01-product`, `docs/02-design`, and `docs/03-engineering`. Based on those conventions, proposed `docs/planning` as the harness planning-draft destination.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --propose --tracker local --artifacts-path docs/planning`
Actual candidate values: tracker `local`; SCM `local`; artifacts path `docs/planning`; branch template `feature/{key}-{slug}`; schema version `1`.
Actual digest: `69303992ec0dd397c5f19f45a5e37301787d23de8184c5e002833767736038f0`.
Actual source digest: `57658985bc7bcdb1cc50fd7791c372def590d3be9bc04d7a4f551ffc5a032ce6`.

Current stage: setup proposal review. Waiting for authentic approval to apply this exact local setup proposal or a choice to change the setup. Proposal has not been applied; no tracker records or planning artifacts have been created.

## Setup approval, application, and verification
Authentic human approval relayed by root: setup review question `Apply this setup to the test copy: local work items, plans in docs/planning, and local source control?`; answer `Apply setup`. This approval covered only the exact proposal digests recorded above. Root-relayed native approval is genuine user authorization; this delegated run does not establish native hook enforcement.

Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness bootstrap --propose --tracker local --artifacts-path docs/planning --apply-digest 69303992ec0dd397c5f19f45a5e37301787d23de8184c5e002833767736038f0 --source-digest 57658985bc7bcdb1cc50fd7791c372def590d3be9bc04d7a4f551ffc5a032ce6`
Actual result: wrote trial `.harness/settings.json`; wrote `.codex/config.toml` enabling request_user_input; selected `Local tracker (shipped)`; created knowledge with SHA-256 `a3ca24545234a769b5080139c8a353bb3b2bfbb52159e0365d95db9e3a523bb5`; result `{"setup": "ready"}`.

Ran the one required doctor check:
Command: `HARNESS_USER_STATE_DIR=/tmp/monolithic-dev-harness-trial-locw4ixf/user-state /home/monolith/.codex/plugins/cache/monolithic-dev-harness/monolithic-dev-harness/0.5.2/bin/harness doctor`
Actual result: healthy. Python, Git, npx, Claude Code, Cursor, and Codex checks passed. Settings valid; Local tracker folders exist at trial `.harness/tracker`; tracking enforced; no open session on branch `master` in this checkout.

Current stage: post-setup routing to the original request. No workflow has been started and no backlog or planning artifact has been drafted yet.

## Discovery instructions actually loaded and request investigation
After authentic choice `Continue DAY-001 task counts — investigate the existing request and prepare its plan`, read the installed `skills/bmad-build/SKILL.md`, `skills/harness/references/technical-discovery.md`, and `references/workflow-storyboard.md`. The technical-discovery document supplies six numbered local steps (resolve request, inspect relevant code, compare approaches, prepare plan, review, save progress); the run followed these instructions. No generated or project-copied BMad workflow, numbered BMad module, renderer, or module installation was entered or run.

Started the workflow with the original request using `harness workflow start --request ...`; actual result status `active`, stage `setup`, request preserved verbatim. Read the named file `backlog/DAY-001-task-counts.md` directly, the linked/current product and engineering notes, and relevant current code in `lib/domain/task.dart`, `lib/application/daybook_providers.dart`, `lib/presentation/task_list_page.dart`, `lib/domain/auth.dart`, `lib/main.dart`, `lib/presentation/login_page.dart`, `test/domain/task_test.dart`, and `pubspec.yaml`.

Discovery finding: the task screen already computes active tasks from the full list before filtering. It has no completed count. The existing immutable task state already contains completion status, so the plan keeps count calculation in the screen and adds widget coverage for both counts, pluralization, state updates, and independence from search/filters. No source code or tests were changed or run.

Wrote the plan at `docs/planning/DAY-001-task-counts-plan.md`. Content SHA-256 recorded by the workflow: `962d563a6f54648ab1376f820ca16feb9c9ec5358f0bdd069ea51e12614c4968`.

Checkpoint command used `harness workflow checkpoint --point 2 --stage discover --label 'DAY-001 technical plan' --artifact docs/planning/DAY-001-task-counts-plan.md --pending 'Human review: approve, revise, or stop this technical plan' --next-action 'On approval, continue to local backlog drafting; stop before implementation.'`. Actual result contains discovery point 2, the artifact path and SHA-256, pending human review, and the next action to continue local backlog drafting only on approval. Workflow remains active. No implementation session, branch, tracker transition, tracker item, or source edit was created.

Current stage: discovery plan review; waiting for human approval, revision, or stop choice.

## Plan revision from authentic user review
The human chose `Revise` on the first discovery-plan review and wrote exactly: `i would examine state management details before closing the plan`. The human later added exactly: `the test must be realistic`. These comments are the controlling feedback; root's earlier topic list was treated as nonbinding suggestions. No code or test file was changed.

Re-examined the state flow from current source:
- `taskListProvider` is the sole task-list provider; `TaskListController.build()` seeds it from `sampleTasks` (`lib/application/daybook_providers.dart`).
- `setCompletion` assigns a new immutable result from `setTaskCompletion`. That transformation creates an unmodifiable list and replaces the matching immutable `Task`, preserving other task values (`lib/domain/task.dart`).
- `TaskListPage.build()` watches the provider as `allTasks`; provider state changes notify the screen and rerun `build`. Search and filter state only produce `visibleTasks`; current active count is already computed from `allTasks` (`lib/presentation/task_list_page.dart`).
- Existing test coverage is only domain transformations (`test/domain/task_test.dart`); no presentation tests exist.

Revised the plan to explain this source of truth, subscription/rebuild and completion transition, why both totals derive in the same build from `allTasks`, and realistic widget tests that sign in through the demo screen and toggle task checkboxes while exercising search and filters. New plan digest: `3b43bca461415807f77239587c2947b2cda1b2ce4ce2ab93ed869c92a238227c`.

Created discovery checkpoint 3 for the revised plan. It records artifact path and new digest, pending human review, and next action to continue only to local backlog drafting after approval. Checkpoint 2 remains as history; checkpoint 3 supersedes it for current review. No implementation has started.

## Approved backlog continuation and tracker-definition blocker
Authentic human response to the revised discovery-plan review: `Approve and continue`. Recorded in workflow checkpoint 4, stage `backlog`, with the revised plan path and digest. Its next action is to draft, enrich, decompose, and break down local work items for human batch review without publishing.

Loaded the installed `generate-work-item`, `enrich-work-item`, `decompose-backlog`, and `generate-breakdown-work-items` skill instructions. Their active-tracker/tracker-contract requirement is to call `tracker_describe` before choosing work-item hierarchy, destination, provider operation, or id format. The installed tools available to this delegated run do not expose `tracker_describe` or local tracker record operations. The provider-aware `mcp__backlog_orchestrator__*` gateway is fixed to the parent repository, so it is out of bounds for this disposable trial.

Local CLI evidence:
- `harness tracker show local --repo .` returned `no onboarded tracker named 'local'; stage it first`.
- `harness tracker list --repo .` returned `azure-devops (shipped)`, `linear (shipped)`, and `local (shipped): Local tracker`.
- `bin/agile-backlog-toolkit config --show` points to trial `docs/planning` and `tracker: local (shipped)`.

The local tracker is explicitly shipped and prior harness guidance says not to stage it. Thus `show local` cannot provide the required descriptor and staging it is disallowed. This leaves no supported trial-targeted way to retrieve the authoritative `kinds`, hierarchy, ids, and capabilities required by the backlog skills. No alternative gateway was called and no backlog work-item artifact, tracker record, implementation session, branch, or source edit was created. Stopped at this capability blocker.

Root records the result as BLOCKED rather than waiting for another product choice. No implementation began.

## Ended by the human

Human instruction: "we can end the run here". Agent was already completed at the blocker and was interrupted to enforce the stop. No further trial actions. Reading-volume counts and complete saved transcript retained alongside this report.
