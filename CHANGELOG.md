# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.2.0...HEAD
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
