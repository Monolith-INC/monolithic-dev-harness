# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Optional, restartable onboarding and sessionless free mode. Preferences use safe defaults;
  missing language capture never blocks work. Required decisions and action approvals retain their
  enforcement, and cancelled settings reviews require fresh confirmation of the exact proposal.

- PR #36 recovery fixes: shared checked resume, deferred successful-startup conversation binding,
  and recoverable decision/checkpoint projection. Failed writes, stale instructions and replayed
  completion output preserve existing progress and approval boundaries.

- `harness begin --request` consolidates setup inspection, session routing and pinned discovery entry.
- Artifact review questions save workflow checkpoints automatically. `harness plan check` reports
  plan size estimates and advisory scope signals; the entry skill loads detailed guidance on demand.

- Bundled BMad `bmad-correct-course`, `bmad-project-context`, `bmad-deep-recon`, and
  `bmad-qa-generate-e2e-tests`, wired into the flow: change of direction at any stage, agent
  instruction drift found during discovery, reconnaissance for unfamiliar code or domains, and
  end-to-end tests when a Story is done.
- Discovery keeps a decision memlog beside the plan and offers **Deepen** (adversarial and
  edge-case review, elicitation, party mode) as a formal option at plan approval.
- Verify runs `bmad-review` edge-case (with claims and deletion checks) and verification-gap lenses
  alongside `thermos`, then triages all findings in one menu.
- `harness decision present` takes `--detail` (what each option means) and `--recommended`, and
  its chat fallback returns one numbered `menu`, identical on every host and every fallback.
- An answer about unchanged content is returned as `already_answered` instead of asking again.
- A stop guard (Claude, Codex) sends the agent back once when a turn would end mid-workflow with
  no question for the user and no pending menu, quoting the saved next action.
- No command needs a work-session id. Starting, resuming, or selecting a session makes it current,
  and `workflow` and `decision` commands use it; with no session, questions still work
  project-wide.
- Standard questions live in `config/gates.toml` in English and Brazilian Portuguese; agents ask
  them with `decision present --gate <id> --value name=value`. Approvals come only from gates.
- Approvals asked through a gate are tied to what was reviewed (drafts or spec, one item, branch,
  or pull request) and do not expire: they hold until revoked, the work session ends, or that
  context changes. A typed `approve HB-…` keeps the short general window.

### Changed

- Replies to a pending question are matched loosely on every transport: a number, an ordinal, the
  label in any case or accents, a unique prefix, or a unique set of its words. A loose reply never
  selects an approving option unless it says "approve". Typing after a dismissed picker or expired
  buttons now answers the question.
- The plan checkpoint is a three-option menu (*Approve and continue*, *Deepen*, *Approve and
  stop*); any other reply is a revision.
- Bundled BMad skills use subagents again for investigation, research, extraction, review lenses,
  and party mode (`auto` by default), asking once per run when the host needs permission.
- Discovery asks all open questions in one message with trade-offs and a recommendation, accepts
  answers in any form, re-checks scope after the answers, and never compresses a plan to fit the
  token budget. The approval summary lists every recorded decision instead of re-asking them.

## [0.6.2] - 2026-10-06

### Fixed

- Codex captures native question answers returned as JSON text and can recover a recorded reply
  from the matching host conversation when a hook misses it, preserving question identity and
  approval checks.
- Bootstrap shows the selected settings once with a native Yes / No confirmation, including before
  repository settings exist. Routing questions accept a real request entered through Other.
- Failed question delivery or capture quietly re-asks through blocking, asynchronous, or chat
  fallback in the same run. Missing replies never become assumed answers or approvals.
- Read-only formatter and Git diff commands no longer trigger the hook-execution guard; actual
  hook execution remains blocked. Doctor states that live question capture has not been checked.

## [0.6.1] - 2026-10-06

### Fixed

- Codex typed choices now resolve asynchronous questions when they exactly match an offered option;
  delayed button replies still require the matching call and question identity.
- Pending decisions allow read-only diagnosis and suspension-status checks while continuing to
  block writes. Reading hook source no longer counts as executing or copying a hook.
- Human suspension requests work before setup and with invalid conversation bindings, preserving
  pending decisions. Reply-capture exceptions report a visible diagnostic without private reply content.
- The decision protocol explains recovery without repeated answers or suspension just for diagnosis.

## [0.6.0] - 2026-10-06

### Added

- Project work sessions: several tickets can be in flight in one project, each bound to its own
  host conversation, with `harness work-session` lifecycle commands (start, list, route, select,
  status, pause, stop, resume, complete), per-session workflow checkpoints, and routing that keeps
  the user's original request. A conversation binds to a session through its first session-scoped
  command and switches only with an exact `harness work-session select|resume <id>`, never while a
  decision is pending; a command naming another session is refused.
- The `hook-entry` rule refuses shell commands that run or copy the harness's own hook entry
  points, so an agent cannot answer or approve for the user by feeding them a payload.
- Human decisions: a question shown to the user is recorded as pending, and only a reply that picks
  one of its offered options, read by the prompt and answer hooks, resolves it; other messages stay
  ordinary prompts, so `harness revoke`, `harness suspend`, and typed approvals keep working. One
  gate holds work while a decision is pending: a project-wide decision holds everyone, a session's
  decision holds that session, and work with no session (an unbound conversation, or Cursor) is
  held by any pending decision. `harness decision status` reports it.
- Prepared workflows: a catalog of routes and steps (`config/prepared-workflows.json`) that hands
  each step its references, skills, operations, outputs, checks, and recovery.
- A subagent contract for agent hosts: `SubagentOps` (start, status, follow-up, cancel, events)
  with typed requests, handles, and statuses. Each host declares in `hosts/<host>.json`, checked
  against `config/host.schema.json`, which operations it supports and where that claim comes
  from. An undeclared operation returns `unsupported_capability`; a malformed answer or a crash
  returns `invalid_host_result`. No host supports any operation yet.
- Test-run tooling for harness acceptance trials: `scripts/acceptance_trial.py`, the
  `tools/project_fixture.py` test-project factory, and the `run-test-project` skill.

### Changed

- The harness now requires Python 3.12 or newer. Hooks, MCP servers, and the `harness` command
  start through `bin/harness-python`, which picks the first Python 3.12+ on the machine
  (`HARNESS_PYTHON`, then `python3.15` down to `python3.12`, then `python3`), so they work where the
  default `python3` is older. The installer and `harness doctor` check for it. CI tests 3.12 and 3.13.
- The installer installs Jinja2 into the plugin's own `runtime/python` folder
  (`requirements-runtime.txt`), never into the user's Python; a failure there is a warning, since
  only `harness workflow render` needs it. It also records the Python it found, which
  `bin/harness-python` tries first, so hosts started from the desktop find it. Without any Python
  3.12+, prompt and question hooks let the user's message through; tool calls fail closed.
- `/check` and `/review` run their scripts through `bin/harness-python`.
- An approval window now covers only the work session it was opened in. A write from another
  session needs its own approval; a window opened without a session (Cursor, or no session bound)
  covers only writes without one. `harness revoke` still closes every window; workflow back,
  resume, and cancel close only their session's.

### Fixed

- BMad is hooked back in. Stage 0 runs BMad Build's own clarify and plan steps instead of a
  hand-written checklist: `harness workflow render` renders them for the project after onboarding
  and pins the snapshot to the work session. `harness bootstrap` runs BMad's bundled setup and
  points its output folder at `artifacts_path`; BMad skills run their unchanged scripts through
  `bin/harness-python` instead of `uv`; the module record ships beside the skills, and BMad's
  ticket script is installed again. A pinned discovery snapshot is rendered again when only the setup
  around the run changed (Python, plugin path, settings); a change to the run's request, language,
  BMad configuration, or the discovery steps keeps the run on its snapshot.
- Approving through a pending decision now opens the window for `approvals.window_minutes`
  instead of a fixed 20 minutes.

## [0.5.4] - 2026-10-06

### Added

- The user can turn off every harness check in a repository by sending `harness suspend` as its own
  message, and turn them back on with `harness resume`. Only the user's own message can suspend the
  harness; no command or tool call lets an agent do it. While suspended, only direct edits to the
  harness's own records under `.harness/` stay blocked, and approval clicks are still recorded.
  Settings, tracker, sessions, and evidence are kept. It works even when the settings are invalid,
  so a blocked repository can always be released.
- `harness suspension status|resume`, the `suspend-harness` and `resume-harness` skills, and a
  `harness doctor` warning while a repository is suspended.

## [0.5.3] - 2026-10-02

### Fixed

- The Codex installer enables clickable questions before bootstrap begins and restores the previous setting on uninstall.
- Skills use the question control available in each Codex host. Bootstrap no longer asks users to type a choice when that control is missing.
- Git is optional during installation, consistent with local planning and review.

## [0.5.2] - 2026-10-02

### Fixed

- Bootstrap now prepares every folder needed by the bundled local tracker and reports its storage
  readiness. Existing local settings are repaired in the background without onboarding another
  tracker or replacing work items.
- Bootstrap reports the current commit and saved workflow together, so an old pause note cannot be
  mistaken for the repository's present state.
- Technical discovery runs from instructions included in the plugin, without downloading planning
  dependencies or asking the user to repair workflow infrastructure.
- Setup asks for the project's language and keeps hosting and version control optional. Planning
  can continue without Git, an initial commit, a branch, or an implementation session.
- User decisions throughout the workflow, including later branch decisions, remain in clickable
  question controls. Local tracker records and planning drafts are described as separate folders.

## [0.5.1] - 2026-10-02

### Added

- Added a post-setup route for continuing a task, preparing work items, or exploring an idea, with
  a ready reference to workflow steps and tracker tools.

### Changed

- Made setup and review work without a hosted code service, and made user decisions use clickable
  choices with Codex's built-in **Other** field.
- Kept BMad setup within the bundled plugin, recognized plugin-managed module metadata, and made
  setup and rendering failures offer clear recovery choices.

## [0.5.0] - 2026-10-02

### Added

- Added technical-first Stage 0 discovery for ordinary feature requests, with BMAD-inspired
  clarification, product, design, architecture, specification, and review skills.
- Added the Stage 0 workflow to the harness default entry point and included the supporting
  templates, validators, party-mode routing, and vendor references.
- Expanded the test project template into a local-first Daybook example with authentication,
  shared application state, due dates, and backlog examples.

### Changed

- Updated plugin descriptions and first-run guidance to explain the ordinary feature-request path,
  bundled command fallback, and same-run setup completion.

## [0.4.0] - 2026-09-30

### Added

- Added Codex as a supported host with a local marketplace, compatibility manifest, MCP server
  configuration, `PreToolUse` and `UserPromptSubmit` hooks, and two read-only review subagents.
- Added an optional BMAD-inspired Stage 0 workflow for shaping an initial idea through
  brainstorming, research, product definition, experience design, architecture, and a canonical
  product specification before backlog or implementation artifacts are created.
- Added a structured **Plan the idea** or **Draft work items** starting-point choice to the harness
  UI when a user brings an idea without selecting a workflow.

### Changed

- Host adapters now translate native hook payloads and decisions at the boundary. The harness
  rules and workflow policy consume normalized tool calls, including every `apply_patch` target.
- The installer registers the Codex marketplace, installs only its managed custom-agent files,
  and refuses to overwrite an unmanaged agent with the same name.
- Backlog decomposition, Story specifications, and Task architecture now inherit and trace Stage 0
  product capabilities, functional requirements, experience decisions, and architecture decisions.

### Security

- Codex plugin hooks require user trust, and some specialized tool paths do not invoke hooks.
  Documentation now treats them as a guardrail, not a complete security boundary.

## [0.3.0] - 2026-09-29

Implementation that predates a session can be adopted safely, Feature Stories are pinned to their
Feature branch, manual guarded changes are approved by a click, and gateway calls reuse one MCP
connection. Local tracker records stay in the clone: re-run bootstrap to ignore them, and if they
were committed, stop sharing them with `git rm -r --cached --ignore-unmatch .harness/tracker/`.

### Added

- Deterministic `harness adoption assess | plan | status | materialize` workflow for implementation
  already in progress: Task classification, scope/evidence reporting, exact-plan approval, source
  fingerprint checks, and a separate correctly based worktree with a verified staged snapshot.
- Tree-bound **Approve change** questions for manual guarded-path evidence in button-capable hosts.
- Feature-managed sessions pin and verify the Feature branch ancestry and require Story pull
  requests to target that branch.

### Changed

- Session start captures work-item readiness and specification artifacts. Ordinary edit checks use
  that snapshot; pushes and completion still revalidate against the tracker.
- Provider-neutral tracker and SCM calls reuse one process-local MCP connection, avoiding a fresh
  interactive OAuth process per gateway call.
- Plans and specifications must be shown in a host document pane or in chat before approval; a
  path alone is no longer sufficient.
- `check --staged` fails closed unless the working-file tree exactly matches the staged tree.
- Local tracker records (`.harness/tracker/`) are local to the clone: bootstrap ignores them through
  `.git/info/exclude` alongside `.harness/state/` and warns when they are still committed; every
  worktree of the clone reads the same records; adoption never inventories or carries either.

### Fixed

- Ordinary edits covered by the session's readiness snapshot no longer open the tracker, and a
  specification published after session start is checked live instead of denied.
- The `feature-branch` rule accepts a remote Feature base (`origin/feature/x`) and skips sessions
  started without a pinned base.
- Adoption never writes through a symbolic link on the base. It stages carried files the base
  ignores, builds patches independent of the user's diff settings, and removes the worktree and
  branch on any failure.
- `check --staged` reports a git failure instead of a traceback.

## [0.2.0] - 2026-09-28

Trackers become adapters, a repository keeps one settings file, work is bound to sessions, and
sprint planning goes through the tracker contract. Repositories set up with 0.1.x run bootstrap
again with a settings file; there is no migration.

### Breaking

- One settings file: `.harness/settings.json` (schema `config/settings.schema.json`) replaces
  `.harness/policy.json`, `.harness/integrations.json`, and `.harness/backlog/config.json`. People
  write it; the harness changes only its `tracker` section, when the user chooses a tracker.
  `harness bootstrap --settings-from <file>` replaces `--policy-from`, `--tracker`, `--scm`,
  `--discover`, and `--force`. Start from `examples/settings.example.json`.
- `protected_work_items` is a top-level list of strings; the Azure-only `azure` block is gone.
- Governed code changes need an active session for the checkout (`harness session start`), unless
  tracking is skipped.
- Workflow artifacts on a tracker use the envelope `harness-artifact:v1`.
- `bin/agile-backlog-toolkit` and the backlog-orchestrator tools: `config --set` and
  `config --require-team` are gone (the backlog stage reads the settings file);
  `capacity --provider azure-devops` is now `--provider tracker` (beside `filesystem`, your
  planning files); `--process` is gone (the process comes from the tracker's settings); and
  `--payloads` is now `--replies`, on `capacity` and `estimate-breakdown` alike.

### Added

- Trackers are adapters: each tracker is one folder, `trackers/<name>/`, holding `tracker.json`
  (checked against `config/tracker.schema.json`) and `adapter.py` (exporting
  `adapter(context) -> TrackerOps`). Azure DevOps, Linear, and a repository-local tracker ship.
- Onboarding: `harness tracker list | show | stage` brings in a tracker the harness does not ship.
  `tracker stage <folder> --value KEY=VALUE` keeps the values its settings need in the staged
  folder, and refuses a tracker missing a required value. Every onboarded folder, trusted or not,
  counts toward which tools need approval; one whose `writes` cannot be read fails closed.
- Trust and selection by click. The agent asks "Trust the <name> tracker as I just described it?"
  (Trust / Not now), then "Use <name> as this project's tracker now?" (Use it / Keep the current
  one). The harness pins the folder's exact version when the question is shown, acts only on the
  user's click, and writes the tracker selection into the settings itself; "Stop trusting" works
  the same way. Any edit to the folder drops trust. In Cursor, which has no buttons, the user
  replies `approve HT-XXXXXX`, `use HT-XXXXXX`, or `stop trusting the <name> tracker`; each reply
  counts only as the whole message.
- Sessions: `harness session start | status | pause | resume | close` bind one work item to one
  checkout; the workflow checks the session's work item instead of guessing it from the branch.
- Rule `tracker-invalid`: while the selected tracker is missing, invalid, untrusted, or lacks its
  values, tracker and SCM writes are refused.
- Sprint planning is part of the tracker contract: every `TrackerOps` provides `read_iteration`,
  `iteration_items`, and `hour_fields`, and every `tracker.json` lists the replies its planning
  reads under `planning.replies`. Azure DevOps, Linear, and the local tracker implement them;
  Linear reports cycle dates and point estimates but no team capacity or hours.
- `harness doctor --tools` checks the tracker's server offers every tool its manifest names;
  `harness doctor --azure` takes its values from the settings.
- The gateway checks every call's arguments against the tool's input schema.
- One shared reference for the active tracker (`references/tracker-contract.md`).

### Changed

- Which calls write, how ids look, and which text links a protected item come from every usable
  tracker folder: Linear writes need approval, Linear and Azure protected ids are both caught, and
  every Azure link form is caught.
- Branch keys come from each tracker's `ids.branch_key` (Azure accepts `AB-123`; Linear and local
  keys are matched without regard to case).
- When the rules cannot run, every MCP call counts as a write and is refused. While the selected
  tracker (or a shipped one) is broken, the same holds for every server but the harness's own.
- The hook checks sessions in the checkout the call happens in, not the host's project folder.
- Each hook call reads the settings and each tracker folder once, and asks git one question for
  the checkout.
- The backlog runtime reads a tracker's sprints only through that tracker's adapter. A tracker's
  sprint reference `current`, or none, means the active sprint.
  - Azure DevOps: a named sprint is found in the iteration listing (by id, name, or path) instead
    of taking the current one. A `work_items` reply that lists only ids is refused with how to
    read the items (`wit_work_item[get_batch]`); a sprint with no work items is an empty sprint.
  - Linear: `current` takes the active cycle; a named cycle is found by id, name, or number.
  - Local: a sprint is read from `.harness/tracker/capacity/<sprint>.json` and must be named. Its
    planning fields use the same names as a planning file's front matter (`story_points`,
    `effort_hours`, `remaining_hours`, ...).
- Capacity is checked when asked (replies passed, or a sprint named). Once asked, a check that
  cannot run stops `estimate-breakdown` instead of skipping the limit: a missing reply, a reply
  that holds no data, an unusable tracker, a sprint or items that cannot be read, or a local sprint
  with no capacity file. The error says which replies to fetch and how.
- Hour writes come from the selected tracker's `hour_fields`. A tracker that records no hours, or
  none usable, gets no hour writes and a note to record the figures by hand.
- `estimate-breakdown` prints every note (tracker warnings, why capacity was not checked, hours to
  record by hand), and lists writes only when there are some.
- `bin/agile-backlog-toolkit config` shows the selected tracker and the values its `tracker.json`
  declares, for any tracker.
- Numbers read from replies and files must be finite: "nan" and "inf" are not numbers.
- The knowledge store's seed points at the settings file instead of copying it.
- Schemas are checked with the harness's own standard-library checker; `jsonschema` is no longer
  needed anywhere.
- CI and release run on `actions/checkout` and `actions/setup-python` v7, and CI on
  `actions/setup-node` v7 (Node 24).

### Removed

- The backlog runtime's own Azure DevOps and Linear providers and settings types; Azure field names
  and capacity mapping live only in `trackers/azure-devops/adapter.py`.
- The Azure adapter shim, the discovery presets, the integrations setup writer, the layout
  migration, and the copies of templates, references, and scripts inside tracker folders.

### Fixed

- `scm_link_work_item`'s `workItemRef` (and `issueId`) are checked against protected items.
- A command merely containing `workflow-integrations` no longer skips the session and spec checks;
  only a lone bootstrap command does.
- A defect in one gateway call answers with an error instead of stopping the server.
- Large provider replies and chatty servers are read without deep recursion.

### Security

- The backlog runtime no longer has its own HTTP client with a personal access token, and the
  enrich skill's Azure reference no longer offers personal-access-token or direct REST fallbacks.
  Every provider call goes through the host's OAuth-signed MCP servers.

## [0.1.10] - 2026-09-24

### Added

- Harness-owned knowledge stores under `.harness/knowledge/`. The `harness knowledge` command lists, finds, resolves,
  fetches, and refreshes source-backed units from append-only, immutable revisions. Bootstrap sets up the `project`
  store from `.harness/policy.json`, and the new `knowledge-acquire` skill tells agents to read from it instead of
  guessing a project convention.

### Fixed

- The spec-before-code gate also finds plans and specs kept in the repository's artifacts path. The tracker is
  still checked first. When it has no spec-like artifact, a Markdown file in the artifacts path counts if all of
  these hold:
  - its frontmatter `type` is `spec` or one of the kinds write-spec produces;
  - its `story` or `work_item` names the work item (`ticket` does not count: the work-item templates use it for
    the parent);
  - it says `status: approved`, and the user approved afterwards. Each approval pins the exact content of the notes
    marked approved at that moment. A draft, a note edited after the approval, or a note under a revoked approval
    does not count.

  The artifacts path is read the same way the backlog skills read it: the `AGILE_WORKFLOW_ARTIFACTS_PATH`
  environment variable first, then `.harness/backlog/config.json`, with `~` expanded. The gate reads only the
  notes an approval pinned, so a large artifacts folder does not slow it down. Teams that keep plans outside
  the tracker no longer have to pause enforcement to edit source files.
- The spec gate accepts every kind write-spec produces, including `rfc`, `adr`, `srs` and `api-contract`. Before,
  it kept its own shorter list.

## [0.1.9] - 2026-09-23

### Fixed

- Bootstrap no longer edits the repository's shared `.gitignore`. It keeps `.harness/state/` out of
  git through `.git/info/exclude`, which belongs to the local clone, so setting a repository up
  leaves no change to commit. `review-setup` keeps `.harness/review/` out of git the same way.

## [0.1.8] - 2026-09-23

### Added

- Approval by click in Claude. The agent asks one question with an **Approve** option; picking it
  opens the approval window, so nobody has to type `approve HB-…`. Typing still works, and is how
  Cursor approves. Only questions that passed the check below count, once each, and a question that
  arrives with answers already filled in is refused.
- `plain-questions` hook: a question to the user is sent back to be rewritten when it is long, asks
  several things, or contains file names, code, or the harness's own names (rule names, batch ids,
  tool names).
- The harness skill tells the agent to raise only what blocks the user's current task, and to keep
  everything else for one short list at the end of the stage.

### Fixed

- "Spec before code" now covers code only: the source and test globs in the policy's
  `tests_required`. Setting a repository up, editing `.gitignore` or `.git/info/exclude`, or writing
  a note into the vault on a Story branch was refused with "has no accepted specification
  artifact". A policy that names no globs still covers every file except `.git/` and `.harness/`.

## [0.1.7] - 2026-09-23

### Fixed

- The workflow policy no longer treats any `>` in a shell command as a file write. Read-only
  commands such as `ls -la 2>&1` or `harness doctor 2>/dev/null` were refused on branches without a
  work item. It now reads commands through the same reader as the harness rules, counting only a
  redirect into the repository or a command known to write.
- The protected-branch guard checks every `git` on a line, not only the first: `git status && git
  commit` on `develop` is refused, as are wrapped forms such as `(git commit …)`.

## [0.1.6] - 2026-09-23

### Changed

- Everything the harness keeps in a repository now lives under `.harness/` (ADR-0008), instead of
  one folder per source plugin: `integrations.json`, `review/`, `backlog/`, `tracker/`, and
  `state/` (which now also holds the orchestrator's prompts and the amendment backups). Re-run
  `harness bootstrap` to move an existing repository's `.codex-workflows/`, `.agile-backlog-toolkit/`,
  `.monolithic-code-review/`, `.agentic/`, and `.local-tracker/` in; nothing is overwritten. Until
  then, the old files are still read.

### Security

- New rule `history-preserved`: rebase, `git pull --rebase`, squash merges, force-push, and
  `filter-branch` are refused in every governed repository, as is completing a pull request by
  squash or rebase. It replaces a guard that only ran while the agent had written a marker file for
  the landing step, did not block squash despite the skill saying so, and missed wrapped commands.
  The agent no longer has to switch anything on.

## [0.1.5] - 2026-09-23

### Fixed

- The four stacked-Feature skills (`feature-implementation`, `reconcile-feature-stack`,
  `merge-story-stack-into-feature`, `finish-feature-development`) pointed the agent at procedures
  under `.agent/`, a folder the harness never creates. Each skill now contains its own procedure and
  rules ([ADR-0008](docs/01-architecture/decisions/ADR-0008-the-harness-owns-its-files.md)).
- `reconcile-feature-stack` merges only; it no longer offers rebase, which its own rules forbade.
- `feature-implementation` no longer opens every Story's pull request up front. Each Story's draft
  pull request comes from its review stage, the only point the harness allows one.

### Removed

- `skills/codex_workflows/`, a leftover of a source plugin's layout (45 skills, down from 46), the
  manifests' unused `stage` blocks, and `scripts/validate_plugin.py`.

### Documentation

- README: the Story and Feature implementation workflows, and answers to common questions about
  the harness, including what it does not do yet.
- ADR-0008: the harness owns its files, and the gaps found while documenting the workflow.

## [0.1.4] - 2026-09-23

### Fixed

- The installer finds a release's files by the release's id instead of its tag. GitHub's by-tag
  view listed no files for v0.1.3 although all three were uploaded, so `install.sh` failed with
  "could not download" for everyone. It now uses one API route for `gh`, a `GH_TOKEN`, and public
  access alike.

## [0.1.3] - 2026-09-23

Reviews of 0.1.2 found holes in the rules it had just rewritten. Upgrade: 0.1.2 is not safe to rely
on. The shell-command checks remain best-effort — they catch the ways an agent plausibly retries a
blocked action, not deliberate evasion; the fix that would make them complete is tracked in
[issue 7](https://github.com/Monolith-INC/monolithic-dev-harness/issues/7).

### Security

- **The hook fails closed.** A crash, or rules running past a 10-second budget, used to exit in a
  way the host treats as "no decision", letting the call run. Now every shell command, file edit,
  and tracker/SCM write is refused with `harness-error` instead.
- **An agent could approve itself.** `cp x .harness/state/checks/../approvals/HB-1.json` was
  allowed. Paths are now normalized and symlinks resolved, for shell commands and edit tools.
- **A push could skip approval.** `(git push)`, `bash -c 'git push'`, `env X=1 git push`,
  `time git push`, `{ git push; }`, `` echo `git push` ``, and pushes inside `if` or loops were not
  recognized — already true in 0.1.1. Every rule now reads commands through one parser.
- **More writes to human-owned files are caught:** after a `cd` that fails; with `2>/dev/null`;
  behind `timeout`, `nice`, `$(…)`, or backticks; via `dd of=`, `--directory=`, `1<>`, `yq -i`,
  `sort -o`, `uniq`, `xxd -r`, `tree -o`; `git checkout`/`restore` of a directory; `git apply` and
  `patch` (the patch is read, and one that cannot be read counts as writing its whole directory);
  archive extraction (members are listed); globs; and removing the whole tree.
- Relative paths in a shell command resolve from the session's working directory, not the
  repository root.
- `protected-items` checks commit messages when the commit is made, for `#<id>` as well as
  `AB#<id>` (Azure Repos' commit mention linking turns both into links), and refuses setting the
  parent field (`System.Parent`, the gateway's `parentRef`).
- `generated-files` fails closed the same way as `human-owned`.
- Tracker errors are fenced as untrusted content, like tracker results.

### Fixed

- Reads that 0.1.2 refused are allowed: behind `timeout`, through `bat`, `realpath`, `tar -t`, a pipe
  into `python3 -c`, a heredoc that mentions a protected path as data, `find … -exec grep`, and after
  a subshell's `cd`. `mkdir -p .harness/state` is allowed.
- Re-running bootstrap repairs a 0.1.1 `.codex-workflows/integrations.json` in place: it fills
  `tracker.project`, corrects an organization misread as `v3`, and drops unused bindings. Before,
  every tracker call failed with `tracker.project is not set`. A file broken by hand is reported,
  not rewritten.
- `bootstrap --force` never replaces an existing `.harness/policy.json`; it rewrites only the
  integrations file.
- `search_work_items` accepts conditions on custom fields (`[Custom.Team] = 'A'`).
- If Azure creates a pull request but reading it back fails, the error names the pull request.
- Status `0` maps to `notSet` / `unknown` instead of the string `"0"`.

### Changed

- A command the shell reader does not recognize is treated as writing every path it names. That
  fails closed: a harmless new reader that names `.harness/` is refused until it is listed.

### Corrections to 0.1.2

- It said `human-owned` "decides from what a command writes, not from the paths it mentions". A
  command the reader does not know is treated as writing what it names; that default is deliberate.
- It said a bare `#<id>` in a commit message links nothing. With commit mention linking on, it does.
- It said `protected-items` "detects every form that links a work item". It missed the parent
  field and commit messages not pushed in the same call.
- It said a truncated artifact list "says so". Only `search_work_items` reports truncation;
  `list_artifacts` reads up to 200 comments and does not.

## [0.1.2] - 2026-09-23

### Security

- `human-owned` decides from what a command *writes*, not from the paths it mentions. The old check
  denied any line containing `>`, and missed a write it could not see on one: a second line, a
  wrapper (`sudo`, `env`), a dispatcher (`xargs`, `eval`), a loop or conditional, a substituted
  target, or a directory target such as `cp policy.json .harness/`. Command parsing now lives in
  `scripts/harness/shellscan.py`, and a write it cannot follow fails closed.
- `protected-items` detects every form that links a work item: `#123`, `AB#123`, `US#123`, all
  three work item URL shapes, and `vstfs:` URIs. In a commit message only `AB#123` links, so that
  is all it blocks there. An HTML entity and a `#004007` colour are not mentions.
- The gateway hands tracker text to the agent fenced as untrusted data. It parses the Azure DevOps
  server's own fence off to read a payload, and now puts its own back.

### Changed

- A Feature no longer needs a parent Epic, and a User Story no longer needs a parent Feature. The
  backlog skills stop asking for one, the Definition of Ready no longer requires the link, and the
  validator passes a Story with no parent. A parent, when given, must still be the right type
  (a Story is never placed under an Epic), and a Task still needs its Story.
- Drafts with no parent and no id yet are named `draft-<slug>.md`.

### Fixed

- `protected-items` now also refuses a write whose text mentions a protected work item as `#<id>`
  or by work item URL. Azure DevOps turns such a mention into a link, so copying a description
  that mentioned the original would have changed it. Name the original in plain text instead.
- The tracker and pull-request tools (`workflow-integrations`) now call the current
  `@azure-devops/mcp` tools (`wit_query`, `wit_work_item_write`, `repo_pull_request_write`, ...)
  and read Azure's real payloads. They used the retired tool names and failed with "tool not
  found".
- Bootstrap reads `git@ssh.dev.azure.com:v3/<org>/<project>/<repo>` remotes correctly, and takes
  the Azure project and repository from the policy it just read instead of guessing again.
- The Azure adapters no longer carry `bindings`. They call their tools by name, so a binding could
  only drift from the code, and bootstrap could fail on one nothing reads.
- `scm_create_pull_request` accepts `isDraft`, which `draft-reviewed-prs` requires; before, a pull
  request could not be opened through it at all.
- `human-owned` no longer blocks reading `.harness/` (for example `cat .harness/policy.json
  2>/dev/null`); it parses the command and blocks only writes.
- `generated-files` likewise fires on writes only: a read-only `grep --include=*.g.dart` was
  refused because the line contained a redirect.
- A pull request can actually be opened. `repo_pull_request_write[create]` returns a trimmed
  payload whose `repository` is a string, which crashed the adapter *after* Azure had created the
  pull request; it is now read back, which also gives it a URL.
- Azure enum fields (pull request and thread status) come back as names, not numbers.
- `list_artifacts` asks for enough comments to find an artifact it published earlier, instead of
  the server's default of 50, and a truncated search says so.
- Provider errors are unwrapped from the untrusted-content fence, so `code` and `retryable` survive.

## [0.1.1] - 2026-09-22

### Fixed

- The release archive now contains `hooks/` and `.mcp.json`. A global gitignore had kept them out of
  git, so 0.1.0 installed with no hooks and no MCP servers: the rules never ran and the Azure DevOps
  and orchestrator servers never started. The repository's `.gitignore` now re-includes them.

### Added

- Guards so an incomplete release cannot ship: `check_repo.py` fails when a required plugin file is
  not tracked, `build_release.sh` refuses an archive without it, CI asserts that Claude Code loads
  the plugin's hooks and all four MCP servers, and `install.sh` fails if it does not.

## [0.1.0] - 2026-09-22

First release.

### Added

- **Plugin for Claude Code and Cursor** covering four stages: backlog, plan, build, and verify, with
  gates G1–G4 and the `harness` conductor skill.
- **Backlog stage:** Epic → Features → Stories → Tasks in one run (tree mode in
  `decompose-backlog`), Story Points written to the Azure points field and read back, Tasks with
  Staging, Review, and Breakdown, and a coverage audit.
- **Plan and build:** `write-spec` takes the backlog output as input; `implement-story` runs
  `architect` → `tdd` → implement → `check` → `deslop` → commit per Task.
- **Verify:** `review` runs `review-story-preflight` (requirements coverage) and `thermos` (two
  parallel reviewers), records a verdict for HEAD, and opens a draft pull request via
  `branch-and-pr`.
- **Hook runtime** shared by both hosts with seven rules: `human-owned`, `approval-required`,
  `protected-items`, `tests-with-code`, `generated-files`, `guarded-paths`, and
  `draft-reviewed-prs`, plus the workflow policy (branch key, state, spec, evidence, protected
  branches, stack order). Fails closed for writes.
- **Approval protocol:** tracker/SCM writes and `git push` need a window opened by the user's own
  `approve HB-…` message.
- **Evidence:** `checks.py` and `review_verdict.py` record results keyed to git tree and commit ids.
- **Per-repository opt-in** through `.harness/policy.json`, with a JSON Schema, an example, and
  `harness bootstrap`.
- **Azure DevOps skill** with host-agnostic tool discovery, a tool map for the current
  `@azure-devops/mcp` server, and a dependency-free health check. `AZURE_DEVOPS_ORG` is required.
- **One-shot installer** (`install.sh`): host detection, checksum-verified release download,
  Claude marketplace registration, Cursor local plugin, organization setup, upgrade in place,
  `--uninstall`.
- **`harness` command:** `version`, `doctor`, `bootstrap`.
- **CI:** ruff lint and format, shellcheck, JSON and schema validation, tests on Python 3.10 and
  3.12, plugin validation, and a sandboxed install of the built release. Tag-driven release
  workflow.
- **Documentation** under `docs/`, including seven architecture decision records.

[Unreleased]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.6.2...HEAD
[0.6.2]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.6.1
[0.6.0]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.5.4...v0.6.0
[0.5.4]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.5.0
[0.4.0]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.4.0
[0.3.0]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.3.0
[0.2.0]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.2.0
[0.1.10]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.10
[0.1.9]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.9
[0.1.8]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.8
[0.1.7]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.7
[0.1.6]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.6
[0.1.5]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.5
[0.1.4]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.4
[0.1.3]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.3
[0.1.2]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.2
[0.1.1]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.1
[0.1.0]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.0
