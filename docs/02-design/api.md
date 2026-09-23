---
title: Command and Contract Interfaces
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
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
| `--org <name>` / `AZURE_DEVOPS_ORG` | asked on a TTY | Azure DevOps organization |
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

Day-to-day command installed on `PATH`: version, health check, repository bootstrap.

### Invocation / Shape

```bash
harness version
harness doctor [--repo <dir>] [--azure --project <project>]
harness bootstrap [--repo <dir>] [--policy-from <file>] [--branch-template <tpl>] [--discover] [--force]
```

### Inputs

`bootstrap` defaults to the current git repository and `examples/policy.example.json`; its other
arguments pass through to `scripts/harness/bootstrap.py`.

### Outputs

`doctor` prints one line per check (`ok`, `warn`, `skip`, `FAIL`).

### Exit Codes

`version` `0`; `doctor` `0` when nothing failed, `1` otherwise; `bootstrap` as `bootstrap.py`.

## Hook entry point — `scripts/harness/hook.py`

### Purpose

Decide whether a tool call may run, and record approvals and manual checks from prompts.

### Producer / Consumer

Invoked by the host for every governed event (`hooks/hooks.json`, `hooks/cursor.hooks.json`).

### Invocation / Shape

```bash
python3 scripts/harness/hook.py --host claude|cursor --event pre-tool|prompt|shell|mcp < payload.json
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

A deny reason always starts with `[harness <rule>]` (`human-owned`, `approval-required`,
`protected-items`, `tests-with-code`, `generated-files`, `guarded-paths`, `draft-reviewed-prs`,
`history-preserved`, `harness-error`) or comes from the workflow policy.

### Failure Behavior

Ungoverned repository: allow. Rules raise: deny write-class calls, allow the rest.

### Examples

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push"},"cwd":"."}' \
  | python3 scripts/harness/hook.py --host claude --event pre-tool
```

## Evidence scripts

| Command | Writes | Exit codes |
| --- | --- | --- |
| `scripts/harness/checks.py [--head \| --staged] [--only <name>…]` | `.harness/state/checks/<tree>.json` | `0` all passed or none applied; `1` a check failed; `2` `--head` with uncommitted tracked changes |
| `scripts/harness/review_verdict.py --verdict ready\|blocked --summary <text>` | `.harness/state/review/<commit>.json` | `0` recorded; `2` `ready` with uncommitted tracked changes |
| `scripts/harness/bootstrap.py --repo <dir> --policy-from <file>` | policy, `.git/info/exclude`, `integrations.json`, backlog config | `0`; `2` not a repository root, invalid policy, missing organization, or missing backlog values |
| `skills/azure-devops/scripts/health-check.mjs --project <p> [--org <o>]` | nothing | `0` healthy; `1` call failed; `2` bad arguments; `124` timeout |
| `bin/agile-backlog-toolkit <command>` | backlog config, reports | per command; `config` exits non-zero while required values are missing |

## Repository policy — `.harness/policy.json`

### Schema

`config/policy.schema.json` (JSON Schema 2020-12). `schemaVersion` must be `1`.

### Inputs

| Field | Type | Used by |
| --- | --- | --- |
| `azure.organization`, `project`, `team`, `repository` | string | bootstrap, stages |
| `azure.protected_work_items` | integer[] | `protected-items` |
| `backlog.artifacts_path` | string | backlog stage |
| `git.base_branch` | string | branch diffs, `tests-with-code`, `check` |
| `approvals.window_minutes` | 1–240 | `approval-required` |
| `checks[]` | `{name, run, when[]}` | `checks.py`, `guarded-paths`, `draft-reviewed-prs` |
| `tests_required[]` | `{source[], tests[], exclude[]}` | `tests-with-code` |
| `generated[]` | glob[] | `generated-files` |
| `guarded_paths[]` | `{path, evidence: check:<name>\|manual:<name>}` | `guarded-paths` |
| `pull_requests` | `{require_draft, require_review_verdict}` | `draft-reviewed-prs` |

### Cross-field Invariants

Every `guarded_paths[].evidence` of the form `check:<name>` must name an entry in `checks`.
Globs are repository-relative; `**` matches across directories.

### Compatibility

New optional fields may be added in minor releases; `schemaVersion` changes only with a breaking
change.

## Prompt protocol

| You type | Effect |
| --- | --- |
| `approve HB-XXXX` / `aprovo HB-XXXX` | opens an approval window (`approvals.window_minutes`) |
| `harness revoke` | closes every open window |
| `harness manual-check <name> ok` | records manual evidence for the currently staged tree |
