---
title: Command and Contract Interfaces
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-28
---

# Command and Contract Interfaces

Every interface the harness exposes to people, hosts, and CI. Paths are relative to
`plugins/monolithic-dev-harness/` unless they start at the repository root.

## install.sh

### Purpose

Install, upgrade, or remove the plugin for Claude Code and/or Cursor in one command.

### Producer / Consumer

Published with every release; run by developers and by CI.

### Invocation / Shape

```bash
curl -fsSL https://github.com/Monolith-INC/monolithic-dev-harness/releases/latest/download/install.sh | bash -s -- [options]
bash install.sh [options]
```

### Inputs

| Option / variable | Default | Meaning |
| --- | --- | --- |
| `--host auto\|claude\|cursor\|all` | `auto` | hosts to install into; `auto` = every host found |
| `--org <name>` / `AZURE_DEVOPS_ORG` | asked on a TTY | Azure DevOps organization for the host-registered `azure-devops` server (repositories name theirs in `.harness/settings.json`) |
| `--version <x.y.z>` / `HARNESS_VERSION` | latest release | version to install |
| `--source <dir\|archive>` | download | install from a local build |
| `--uninstall` | | remove from every host |
| `--yes` | | never prompt |
| `HARNESS_HOME` | `~/.local/share/monolithic-dev-harness` | installed marketplace copy |
| `HARNESS_BIN_DIR` | `~/.local/bin` | where `harness` is linked |
| `CURSOR_PLUGIN_DIR` | `~/.cursor/plugins/local/monolithic-dev-harness` | Cursor plugin copy |
| `GH_TOKEN` / `GITHUB_TOKEN` | | private downloads without `gh` |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Claude settings to update |

### Outputs

The marketplace copy under `HARNESS_HOME`, the plugin registered and enabled in Claude Code,
`env.AZURE_DEVOPS_ORG` in Claude's `settings.json`, the Cursor plugin copy with the organization
pinned in `cursor.mcp.json`, and the `harness` link.

### Exit Codes

`0` success; `1` any failure (missing prerequisite, download or checksum failure, host refused the
plugin).

### Failure Behavior

Checksum mismatch refuses to install. Host directories are replaced atomically (`.new` then
rename), so a failed copy never leaves a half-installed plugin.

### Examples

```bash
curl -fsSL …/install.sh | bash -s -- --org contoso --host claude
bash install.sh --source dist/monolithic-dev-harness-0.1.0.tar.gz --yes
bash install.sh --uninstall
```

## harness

### Purpose

Day-to-day command installed on `PATH`: version, health check, bootstrap, sessions, trackers, and
safe adoption of implementation already in progress.

### Invocation / Shape

```bash
harness version
harness doctor [--repo <dir>] [--tools] [--azure]
harness bootstrap [--repo <dir>] [--settings-from <file>]
harness session start <work item> [--workflow <name>] [--base-ref <Feature branch>] [--repo <dir>]
harness session status | pause | resume | close [--repo <dir>]
harness tracker list | show <name> | stage <folder> [--repo <dir>]
harness adoption assess <work item> --base-ref <ref> [--repo <dir>]
harness adoption plan <HA-id> --branch <branch> --destination <path> [--repo <dir>]
harness adoption status | materialize <HA-id> [--repo <dir>]
harness knowledge init | refresh | catalog | find | resolve | fetch | status [...]
```

### Inputs

`bootstrap` defaults to the current git repository and `examples/settings.example.json`.
`doctor --tools` starts the selected tracker's server and checks it offers every tool the manifest
names; `doctor --azure` runs the Azure DevOps health check with the settings' organization and
project. `session start` records the work item's readiness and specification artifacts; with
`--workflow feature-implementation` it also needs `--base-ref`, the Feature branch the Story
branch descends from, and pins that branch and its commit. `session start` needs the checkout to be
on the work item's branch (the settings'
`branch_template` with the tracker's `ids.branch_key`) and the tracker to know the item.
`adoption assess` reads the work item and Tasks through the selected tracker. `adoption plan`
binds the source fingerprint, intended base, target branch, and separate worktree path. A
tree-bound **Approve adoption** click is required before `adoption materialize` stages the pinned
source delta on that base in the new worktree.

### Outputs

`doctor` prints one line per check (`ok`, `warn`, `skip`, `FAIL`), including the settings, the
selected tracker, broken tracker folders, the tracking mode, and the checkout's session.
`session` prints the session id, work item, branch, and phase. `tracker show` and `tracker stage`
print everything a person needs to review an onboarded tracker, and how to ask the user: a
**Trust** question, then a **Use it** question, plus the short `HT-` reply id for Cursor.
`tracker stage` takes `--value KEY=VALUE` for each value the tracker's settings need.
`adoption` prints JSON containing its immutable `HA-…` id, classifications, scope differences,
evidence, plan approval, and materialization result.

### Exit Codes

`version` `0`; `doctor` `0` when nothing failed, `1` otherwise; `bootstrap` as `bootstrap.py`;
`session` and `tracker` `0` on success, `2` with the reason on stderr.

## Hook entry point — `scripts/harness/hook.py`

### Purpose

Decide whether a tool call may run, and record approvals, manual checks, and tracker trust from
what the user typed or clicked.

### Producer / Consumer

Invoked by the host for every governed event (`hooks/hooks.json`, `hooks/cursor.hooks.json`).

### Invocation / Shape

```bash
python3 scripts/harness/hook.py --host claude|cursor --event pre-tool|prompt|shell|mcp|ask|answer < payload.json
```

### Inputs

The host's hook payload on stdin (`tool_name`, `tool_input`, `cwd`, or `prompt`).

### Outputs

| Host / event | Allow | Deny |
| --- | --- | --- |
| Claude pre-tool | no output | `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "[harness <rule>] …"}}` |
| Cursor pre-tool / shell / mcp | `{"permission": "allow"}` | `{"permission": "deny", "agent_message": …, "user_message": …}` |
| Claude prompt | notes such as `[harness] approval HB-7Q2K recorded …` | — |
| Cursor prompt | `{"continue": true}` | — |

### Exit Codes

Always `0`; the decision is in stdout.

### Cross-field Invariants

A deny reason always starts with `[harness <rule>]` (`human-owned`, `tracker-invalid`,
`approval-required`, `protected-items`, `tests-with-code`, `generated-files`, `guarded-paths`, `feature-branch`,
`draft-reviewed-prs`, `history-preserved`, `harness-error`) or comes from the workflow policy.

### Failure Behavior

Ungoverned repository (no `.harness/settings.json`): allow. Unreadable settings, or rules that
raise or run out of time: deny write-class calls (edits, shell commands, every MCP call), allow the
rest.

### Examples

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push"},"cwd":"."}' \
  | python3 scripts/harness/hook.py --host claude --event pre-tool
```

## Evidence scripts

| Command | Writes | Exit codes |
| --- | --- | --- |
| `scripts/harness/checks.py [--head \| --staged] [--only <name>…]` | `.harness/state/checks/<tree>.json` | `0` all passed or none applied; `1` a check failed; `2` `--head` with uncommitted tracked changes, or `--staged` when the working files differ from the index |
| `scripts/harness/review_verdict.py --verdict ready\|blocked --summary <text>` | `.harness/state/review/<commit>.json` | `0` recorded; `2` `ready` with uncommitted tracked changes |
| `scripts/harness/bootstrap.py --repo <dir> --settings-from <file>` | `.harness/settings.json` (once), `.git/info/exclude`, the knowledge store | `0`; `2` not a repository root, invalid settings, or an unusable selected tracker |
| `skills/azure-devops/scripts/health-check.mjs --project <p> [--org <o>]` | nothing | `0` healthy; `1` call failed; `2` bad arguments; `124` timeout |
| `bin/agile-backlog-toolkit <command>` | backlog reports | per command; `config --show` exits non-zero while required values are missing |

## Repository settings — `.harness/settings.json`

### Schema

`config/settings.schema.json` (JSON Schema 2020-12), checked by `scripts/core/schema.py`.
`schemaVersion` must be `1`. The file is human-owned; see
[data-model.md](../01-architecture/data-model.md#authority-boundaries) for the one change the
harness makes when the user chooses a tracker.

### Inputs

| Field | Type | Used by |
| --- | --- | --- |
| `tracker` | `{name, source?: shipped\|onboarded, values{}}` | registry, gateway, rules, backlog stage |
| `scm` | `{name: github\|azure-repos, values{}}` | gateway |
| `branch_template` | string containing `{key}` | workflow policy, `harness session start` |
| `protected_work_items` | string[] | `protected-items` |
| `artifacts_path` | string | backlog stage, spec gate |
| `git.base_branch` | string (default `develop`) | branch diffs, `tests-with-code`, `check` |
| `approvals.window_minutes` | 1–240 (default 20) | `approval-required` |
| `checks[]` | `{name, run, when[]}` | `checks.py`, `guarded-paths`, `draft-reviewed-prs` |
| `tests_required[]` | `{source[], tests[], exclude[]}` | `tests-with-code`, spec gate |
| `generated[]` | glob[] | `generated-files` |
| `guarded_paths[]` | `{path, evidence: check:<name>\|manual:<name>}` | `guarded-paths` |
| `pull_requests` | `{require_draft, require_review_verdict}` (both default true) | `draft-reviewed-prs` |

### Cross-field Invariants

- Every `guarded_paths[].evidence` of the form `check:<name>` names an entry in `checks`.
- `tracker.values` holds every setting the tracker's manifest marks required, and nothing it
  does not declare.
- `scm.values` holds `owner` and `repo` for GitHub, `organization`, `project`, and `repository` for
  Azure Repos.
- Globs are repository-relative; `**` matches across directories.

### Compatibility

New optional fields may be added in minor releases; `schemaVersion` changes only with a breaking
change.

## Tracker contract — `trackers/<name>/`

### Schema

`tracker.json` against `config/tracker.schema.json`, plus the registry's own checks: an
`adapter.py` exists; artifact names are unique, children are declared, the hierarchy has no cycle;
every kind names an artifact and an epic holds features, a feature user stories and bugs, a user
story tasks; `ids.pattern`, `ids.branch_key` (with a named group `id`), and every `ids.mention`
(with `{id}`) are valid regular expressions; connection placeholders name declared settings.

### Fields

| Field | Meaning |
| --- | --- |
| `connection` | `{kind: mcp, command, args[], timeout?}` or `{kind: local}`; `{<setting>}`, `{plugin_root}`, `{repo}` fill in |
| `settings[]` | `{key, required, description}`: what `tracker.values` gives |
| `kinds`, `states` | the provider name for each harness kind and state |
| `artifacts[]` | `{name, children[], estimate?}`: provider types and containment |
| `tools` | provider tool names the adapter calls |
| `ids` | `pattern`, `branch_key`, `mention[]`, `mentions_link` |
| `writes` | `{server, tools[]}`: host tools that change the tracker (`*` matches any run) |
| `planning` | `{replies[]}` of `{key, description}`: the provider replies its planning reads, and how to fetch each |
| `attachments`, `text_format` | where artifacts go; markdown, html, or plain |

### Operations

`adapter.py` exports `adapter(context: AdapterContext) -> TrackerOps`
(`scripts/integrations/contracts.py`). `TrackerOps` holds `get_work_item`, `search_work_items`,
`create_work_item`, `transition_work_item`, `list_children`, `list_artifacts`, `add_artifact`,
`link_development_artifact`, and the planning operations `read_iteration`, `iteration_items`, and
`hour_fields` (the sprint model is in `scripts/integrations/planning.py`; the sprint reference
`current`, or none, means the active sprint). Every tracker provides all of them; each returns
`Ok` or `Err` and never raises for an expected condition.

## Gateway tools — `workflow-integrations`

| Tool | Write (needs approval) |
| --- | --- |
| `tracker_describe`, `tracker_get_work_item`, `tracker_search_work_items`, `tracker_list_children`, `tracker_list_artifacts` | no |
| `tracker_create_work_item`, `tracker_transition_work_item`, `tracker_publish_artifact`, `tracker_link_development_artifact` | yes |
| `scm_get_pull_request`, `scm_list_review_threads` | no |
| `scm_create_pull_request` (drafts only), `scm_reply_to_thread`, `scm_link_work_item` | yes |
| `workflow_tracking_status`, `workflow_resume_tracker` | no |
| `workflow_skip_tracker` | yes |

Arguments are checked against each tool's input schema before anything runs. Tracker and SCM text
reaches the agent fenced as untrusted content. While tracking is skipped, the `tracker_*` tools are
not offered.

## Prompt protocol

| You type | Effect |
| --- | --- |
| `approve HB-XXXX` / `aprovo HB-XXXX` | opens an approval window (`approvals.window_minutes`) |
| `harness revoke` | closes every open window |
| `harness manual-check <name> ok` | records manual evidence for the currently staged tree (in Claude, click **Approve change**) |
| `approve HT-XXXXXX` | Cursor: trusts the onboarded tracker whose current version has that short id |
| `use HT-XXXXXX` | Cursor: selects that trusted tracker, writing it into the settings file |
| `stop trusting <tracker>` | Cursor: withdraws trust from the tracker named by label or name |

Each tracker reply counts only as the whole message, so a quoted or negated mention does nothing.

In Claude, the same happens by click: a question that says "tracker", names an onboarded tracker,
and offers **Trust**, **Use it**, or **Stop trusting**. The question hook pins the tracker's version when the
question is shown; the answer hook acts only on the user's click, and only if the folder has not
changed since.
