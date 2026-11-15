---
date: 2026-09-23
type: ticket
work_item_type: Bug
provider: local
story_points: 2
language: en
tags: [ticket, bug, hooks, human-owned]
---

# The human-owned rule blocks commands that only touch folders outside the repository

## 🎯 What

The `human-owned` rule denies shell commands that never write inside the repository. It resolves
relative paths against the repository root instead of the command's working directory, and treats
an unexpanded shell variable as an empty string.

## 💡 Why

Legitimate work outside the repository (a scratch folder, a temporary clone) is blocked with a
message about harness policy, and the agent can only get through by rewriting the command with
literal absolute paths. A read-only listing was blocked the same way, so the rule is not even
limited to writes in practice.

## 📋 Expected Behavior

```text
cd /tmp/scratch && git sparse-checkout set skills/cloud/x   -> allowed (writes under /tmp/scratch)
S=/tmp/scratch; find "$S"/skills -type f                    -> allowed (read-only, outside repo)
echo x > .harness/settings.json                             -> denied, as today
```

## Observed

| Command | Denial |
| --- | --- |
| `cd <scratch> && git -C <scratch> sparse-checkout set skills/cloud/...` | "could write skills/cloud/*, which is human-owned harness state or policy" |
| `S=<scratch>; for d in "$S"/skills/cloud/*; do ... du ...; done` (read-only) | "could write /skills/cloud/*" |

Both ran fine once rewritten with literal absolute paths.

### Seen again on 2026-10-22, 0.7.0-rc.2, inside the repository

Two read-only inspections of harness state in a consuming project were denied:

| Command | Denial |
| --- | --- |
| `cd <repo>/.harness/state && ls host_sessions work_sessions; grep -l ...; python3 -c "<reads decision-history.json>"` | "could write <repo>/.harness/state/cd" — the word `cd` itself was taken as a path to write |
| `S=<repo>/.harness/state; cat $S/work_sessions/current.json; for d in $S/work_sessions/WS-*; do ls $d; head -c 400 $d/*.json; done` | "could write .harness/state/work_sessions/WS-*" |

Nothing in either command writes. The agent fell back to the Read tool and a plain `ls -R`, which passed.
Diagnosing a harness malfunction means reading `.harness/state`, so this rule blocks self-diagnosis.

## 🔧 Technical Notes

- `scripts/harness/rules.py` → `rule_human_owned` → `shell_human_owned_write` uses
  `shellscan.scan(call.command, _shell_start(call, repo), repo)`; `cd` inside the command is not
  applied to later relative paths, and `$VAR` expansions become empty, so `"$S"/skills` turns into
  `/skills`.
- Track `cd` within the command when resolving later relative paths; treat unresolvable variables as
  unknown and match them only against human-owned globs that could still apply.
- Only count paths in write positions (redirections, `cp`/`mv`/`rm` targets, known writers), not
  every path argument.
- `generated-files` uses the same scanner (see the ticket about generators that name generated
  files); fix both together.

## ✅ Acceptance Criteria

- [x] A command whose writes all resolve outside the repository is not denied by `human-owned`.
- [x] Read-only commands are not denied by `human-owned`.
- [x] Relative paths after a `cd` in the same command resolve against the new directory.
- [x] Writes to human-owned files are still denied, including through variables that resolve to them.
- [x] Tests cover `cd`-then-relative-path and unexpanded-variable commands.

## 🛠️ Resolution

Fixed for both rules (`human-owned` and `generated-files`), which read commands through the same scan,
and for the `hook-entry` rule that refused staging or copying the hook source:

- A loop or `case` header (`for d in …`, `select`, `case`), a `[[ … ]]` test and an assignment in front
  of a command (`FOO=$BAR ls …`) are shell syntax, not commands that write the words after them.
- `python3 -c` and `python3 - <<EOF` code that only reads (it imports only reading modules, opens
  files only for reading and names nothing that writes) is followed to no writes. Other code still
  counts every word it holds.
- Words of code the scan cannot follow are judged from the directory they run in after a `cd … &&`,
  and a `.harness` folder beyond the repository is not the project's.
- The scan never raises: a variable operand of `git apply` used to crash it, and any command it cannot
  read now counts as naming the words it contains.
- `hook-entry` fires only when a command would run the hook: `git add`, `git commit` and the like, and
  `cp`/`mv`/`ln`/`install`, may name its source.

Still refused on purpose: a `cd` joined by `;` (it may fail, so the starting directory is checked too),
an unknown command naming a human-owned path, and code that may write such a path.

## 📊 Complexity

**2 points** — Largest driver: Scope=2, Uncertainty=2, Integrations=1, Data=1, QA=2, Rollout=1 → 2 points

## 📄 Original Description

Found while downloading Google skills into a scratch folder: the harness blocked a clone and a
read-only listing that never touched the repository.
