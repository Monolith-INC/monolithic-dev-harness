---
date: 2026-09-23
type: ticket
work_item_type: Bug
provider: local
story_points: 5
language: en
tags: [ticket, bug, hooks, worktrees]
---

# Hooks judge a worktree session against the wrong repository

## 🎯 What

When an agent session starts in a repository's main checkout and then works in a git worktree, the
workflow hooks judge every call against the main checkout instead of the worktree: its branch, its
work item, its policy.

## 💡 Why

Worktrees are the normal way to run two agents on one repository without disturbing each other.
In that setup the harness currently does two wrong things at once:

- it **blocks correct work**: a commit on the worktree's Story branch was denied because the
  work item on the *other* agent's branch had no accepted spec;
- it **lets ungoverned work through**: edits to files inside the worktree fall outside the hook's
  root, so the spec-before-code gate never runs for them.

## 📋 Expected Behavior

The repository a hook evaluates is the one the tool call acts on:

```text
Edit/Write        -> the repository that contains the file path
Bash (git, shell) -> the repository of the command's working directory (or -C target)
MCP tracker call  -> unchanged (tracker scope comes from that repository's policy)
```

## Observed

Session started in the main checkout (branch of another Story, worked on by another agent), then
switched into `.claude/worktrees/<name>` on the Story branch being implemented.

| Action in the worktree | Result |
| --- | --- |
| `git commit` on the Story branch | denied: "Work item \<other agent's item\> has no accepted specification artifact." |
| Write/Edit on `projects/**` source and test files | allowed without any spec-gate evaluation |

## 🔧 Technical Notes

- `scripts/hook_runtime.py` → `get_project_root()` returns `CLAUDE_PROJECT_DIR` (also
  `CURSOR_PROJECT_DIR`, `CODEX_PROJECT_ROOT`) before looking at anything else. That variable is the
  session's start folder and does not follow a worktree switch.
- `run()` then computes `current_branch(project_root)`, so the branch, and therefore the work item,
  comes from the main checkout.
- `_edits_code()` resolves the edited path relative to that root; a worktree path raises
  `ValueError` and returns `False`, which reads as "not code" and allows the edit.
- Fix direction: derive the root per call, from the file path for edit tools and from the command's
  start directory for shell tools (the `rules.py` side already has `_shell_start`), falling back to
  the environment variable only when neither is available. Treat "path outside the evaluated root"
  as "resolve its own root", never as "not code".

## ✅ Acceptance Criteria

- [ ] A commit made from a worktree is evaluated against the worktree's branch and work item.
- [ ] An edit to a governed file inside a worktree goes through the spec-before-code gate.
- [ ] An edit to a file outside every governed repository is still allowed.
- [ ] Sessions that never leave the start folder behave exactly as today.
- [ ] Tests cover a session rooted in the main checkout acting on a sibling worktree, for Edit, Write
      and `git commit`.

## 📊 Complexity

**5 points** — Largest driver: Scope=3, Uncertainty=3, Integrations=2, Data=1, QA=5, Rollout=3 → 5 points

## 📄 Original Description

Found while implementing a Story in a worktree next to another agent's checkout: the harness
checked commits against the other agent's work item and did not govern edits in the worktree.
