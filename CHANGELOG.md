# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.4
[0.1.3]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.3
[0.1.2]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.2
[0.1.1]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.1
[0.1.0]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.0
