---
title: Security Model
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Security Model

## Scope

The plugin on a developer's machine, its hooks, and the calls it makes to Azure DevOps with the
developer's identity. Out of scope: the hosts themselves, Azure DevOps, and the model provider.

## Assets / Authority

| Asset | Why it matters |
| --- | --- |
| Azure Boards work items | the team's plan; protected items must stay intact |
| Azure Repos branches and pull requests | what reaches review and production |
| The repository's code and history | commits must meet the team's rules |
| The developer's Azure DevOps session | every call runs as the developer |
| `.harness/policy.json`, approvals, manual checks | the controls themselves |

## Trust Boundaries

```text
untrusted                          |  trusted to decide
-----------------------------------+-----------------------------------
model output                       |  the hook runtime (code, tests)
content the agent reads            |  the developer's own prompt
(work items, web pages, files)     |  the committed policy
tool results                       |  git ids
```

The model and everything it reads are treated as untrusted. Decisions come only from code, the
committed policy, git, and the developer's prompt.

## Role Permissions

See [../01-architecture/system-context.md](../01-architecture/system-context.md#authority-boundaries).

## Threats

See [threat-model.md](threat-model.md).

## Controls

| Control | Rule / mechanism |
| --- | --- |
| No tracker/SCM write or push without a person's approval | `approval-required`; windows exist only from the prompt hook |
| The agent cannot approve itself or weaken the policy | `human-owned` |
| Protected items are never modified, even indirectly by links | `protected-items` |
| Nothing unreviewed reaches a pull request; people publish and approve | `draft-reviewed-prs` |
| Code ships with tests; generated files are not hand-edited | `tests-with-code`, `generated-files` |
| Sensitive paths need evidence for the exact change | `guarded-paths` |
| Stacked branches keep their history: no rebase, squash merge, or force-push | `history-preserved` |
| Branch, state, spec, and evidence discipline | workflow policy |
| Reviewer subagents have no file-edit tools | `tools:` in their frontmatter (Read, Grep, Glob, Bash, Skill, WebFetch); their Bash calls still pass the hooks |
| No stored credentials | the Azure DevOps server uses interactive OAuth; no PAT |

## Host Enforcement Differences

Both hosts run the same runtime. Claude Code's `PreToolUse` matcher covers Bash, file edits, and
every MCP tool. Cursor's `preToolUse`, `beforeShellExecution`, and `beforeMCPExecution` cover the
same classes; enforcement in a live Cursor session is pending first observation.

## Fail-closed Behavior

If the policy is invalid, any rule or the workflow runtime raises, or the rules run past their
10-second budget, write-class calls are denied with `harness-error`: file edits, every shell
command, and tracker/SCM writes. Read-only tools continue. The budget sits below the hosts' 15-second
hook timeout because a hook that times out or exits with an error does not block the call.
Corrupt state files are treated as absent, which can only cause a deny.

## How Shell Commands Are Read

`generated-files`, `human-owned`, `approval-required`, and `protected-items` all need to know what a
`Bash` call runs and what it writes. `scripts/harness/shellscan.py` tokenizes the command once and
answers both. It is a best-effort reader, not a sandbox: it catches the ways an agent plausibly
retries a blocked action, and every form a review has found is pinned in
`tests/harness/test_shellscan.py`, but a command string cannot be read completely. The fix that would
make these guarantees hold regardless of the command is tracked in
[issue 7](https://github.com/Monolith-INC/monolithic-dev-harness/issues/7).

- It walks every command the shell would run: each line, continuations, subshells, `{ }` groups,
  `if` and loop bodies, `$(…)` and backticks, wrappers (`sudo`, `env`, `timeout`, `nice`, `time`,
  `exec`), `sh -c`, `eval`, `xargs`, and `find -exec`. So `sudo git push`, `(git push)`, and
  `time git push` are pushes, and need approval like `git push`.
- It resolves each path against the directory the command runs in (`cd`, the session's working
  directory) and also against where the command started, in case a `cd` failed. It collapses `..`
  and resolves symlinks, so `.harness/state/checks/../approvals/x.json` is an approval.
- A command it does not know is treated as writing every path it names. Readers are listed
  explicitly; a new reader that names a protected file is refused until it is added.
- Where it cannot follow a write (inline interpreter code, a script, a path in a variable, `xargs`
  fed from a pipe), it treats any protected path named on the line as written.
- It reads the patch behind `git apply` and `patch`, and the member list of an archive being
  extracted, to see which files they would write. A patch it cannot read now (piped in, not yet
  written, written earlier in the same command) counts as writing anything under its directory.
- If reading the command fails or takes longer than 10 seconds, the call is refused (see
  Fail-closed Behavior).

## Tracker Text Is Fenced

Work-item titles, descriptions, and review comments reach the agent through the
`workflow-integrations` server wrapped in an untrusted-content fence with a random nonce, the same
way the Azure DevOps server fences its own output. Errors from those tools are fenced too.

## Supply-chain Validation

- Releases are built by CI from a tagged commit with `git archive` (committed files only).
- `install.sh` verifies the archive's SHA-256 against the release's `SHA256SUMS` before installing.
- The hook runtime and installer use the Python standard library only.
- Vendored sources and their licenses are listed in `THIRD_PARTY_NOTICES.md`.
- `@azure-devops/mcp` is fetched by `npx` at run time and is the one unpinned runtime dependency.

## Residual Risks

- An approval window covers any tracker/SCM write for its duration, not only the batch shown.
- The shell reader is a guard against a model that routes around a rule, not a sandbox
  ([issue 7](https://github.com/Monolith-INC/monolithic-dev-harness/issues/7)). Not inspected: a
  script run by path; deliberate obfuscation (brace expansion, `$'…'` quoting, a directory name
  assembled from variables); a merge, pull, or branch checkout that brings in a changed tracked
  policy; a commit message read from a file with `git commit -F`; a patch downloaded and applied
  in the same command. Commits are also checked.
- The workflow runtime writes a debug log to `/tmp/codex_hook_debug.log`, readable by other local
  users on shared machines.
- `@azure-devops/mcp` is not pinned to a version.
- Report vulnerabilities privately to the maintainers; do not open a public issue.
