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
echo x > .harness/policy.json                               -> denied, as today
```

## Observed

| Command | Denial |
| --- | --- |
| `cd <scratch> && git -C <scratch> sparse-checkout set skills/cloud/...` | "could write skills/cloud/*, which is human-owned harness state or policy" |
| `S=<scratch>; for d in "$S"/skills/cloud/*; do ... du ...; done` (read-only) | "could write /skills/cloud/*" |

Both ran fine once rewritten with literal absolute paths.

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

- [ ] A command whose writes all resolve outside the repository is not denied by `human-owned`.
- [ ] Read-only commands are not denied by `human-owned`.
- [ ] Relative paths after a `cd` in the same command resolve against the new directory.
- [ ] Writes to human-owned files are still denied, including through variables that resolve to them.
- [ ] Tests cover `cd`-then-relative-path and unexpanded-variable commands.

## 📊 Complexity

**2 points** — Largest driver: Scope=2, Uncertainty=2, Integrations=1, Data=1, QA=2, Rollout=1 → 2 points

## 📄 Original Description

Found while downloading Google skills into a scratch folder: the harness blocked a clone and a
read-only listing that never touched the repository.
