---
date: 2026-09-23
type: ticket
work_item_type: Bug
provider: local
story_points: 3
language: en
tags: [ticket, bug, bootstrap, worktrees]
---

# A new worktree of an opted-in repository is not governed

## 🎯 What

A git worktree created from an opted-in repository starts without `.harness/`, so the harness
treats it as not opted in. The backlog artifacts folder is missing there too.

## 💡 Why

Bootstrap keeps `.harness/` untracked on purpose (it writes it to `.git/info/exclude`), which is
right for teams that do not version it. But untracked files do not travel to new worktrees, so
every worktree silently drops out of governance until someone notices and copies the folder by
hand. The same applies to a gitignored `backlog.artifacts_path` (for example a vault folder): specs
and plans the stages read are not present in the worktree.

## 📋 Expected Behavior

```text
git worktree add ...           (repository opted in, .harness/ untracked)
  -> harness doctor in worktree: governed, same policy
  -> stages can read the artifacts path
  -> approvals and check evidence stay per worktree
```

## Observed

- `harness doctor` inside a fresh worktree: `not opted in (run harness bootstrap)`.
- Workaround used: copying `.harness/` from the main checkout. Copying (not linking) was needed so
  approval windows and check evidence did not leak between the two agents.
- The approved tech spec lived in the gitignored vault of the main checkout; the worktree had no
  copy, and an isolated worktree session could not write to it.

## 🔧 Technical Notes

- Resolve the policy from the main checkout when the worktree has none: `git rev-parse
  --git-common-dir` identifies the shared repository.
- Split `.harness/` into shared configuration (policy, integrations, review sources, backlog
  config) and per-worktree state (approvals, check evidence), and say which is which in
  `docs/01-architecture/data-model.md`.
- Resolve `backlog.artifacts_path` the same way when it is untracked: read and write the main
  checkout's folder.
- `harness doctor` should report which checkout a worktree takes its policy from.

## ✅ Acceptance Criteria

- [ ] A worktree of an opted-in repository is governed with no manual copying.
- [ ] Approvals and check evidence recorded in one worktree do not count in another.
- [ ] Stages running in a worktree can read and write the configured artifacts path.
- [ ] `harness doctor` in a worktree names the checkout its policy comes from.
- [ ] A repository that versions `.harness/` behaves as today.

## 📊 Complexity

**3 points** — Largest driver: Scope=3, Uncertainty=2, Integrations=1, Data=2, QA=3, Rollout=2 → 3 points

## 📄 Original Description

Found while starting a Story in a worktree: the worktree reported "not opted in" because
`.harness/` is excluded from git, and the vault holding the spec was absent.
