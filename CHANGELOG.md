# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-09-23

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
- Bootstrap reads `git@ssh.dev.azure.com:v3/<org>/<project>/<repo>` remotes correctly; the
  Azure project falls back to `.harness/policy.json` when the integrations file lacks it.
- `scm_create_pull_request` accepts `isDraft`, which `draft-reviewed-prs` requires; before, a pull
  request could not be opened through it at all.
- `human-owned` no longer blocks reading `.harness/` (for example `cat .harness/policy.json
  2>/dev/null`); it parses the command and blocks only writes.

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

[Unreleased]: https://github.com/Monolith-INC/monolithic-dev-harness/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.2
[0.1.1]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.1
[0.1.0]: https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.1.0
