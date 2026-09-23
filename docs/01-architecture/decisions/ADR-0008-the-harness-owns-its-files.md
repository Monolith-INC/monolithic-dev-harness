---
title: ADR-0008 The harness owns its files
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-23
---

# ADR-0008: The harness owns its files, and keeps them in one place

## Status

Accepted. Not yet implemented; see Follow-up.

## Context

The harness was built by copying in several earlier plugins (the backlog toolkit, codex-workflows,
the code-review toolkit). Some of their layout came along with the code:

- Four stack skills (`feature-implementation`, `reconcile-feature-stack`,
  `merge-story-stack-into-feature`, `finish-feature-development`) tell the agent to follow
  procedures and rule lists under `.agent/workflows/` and `.agent/rules/`. The original plugin's
  installer copied those files into each project. The harness does not, so the agent is pointed at
  files that are never there. The files themselves were copied into the plugin, under
  `skills/codex_workflows/resources/` and `skills/codex_workflows/rules/`, as a leftover of the
  original layout.
- A governed repository can end up with a dot-folder per original plugin: `.harness/`,
  `.codex-workflows/`, `.agile-backlog-toolkit/`, `.monolithic-code-review/`, and `.agentic/`.

The harness is one new product, not a set of references to other plugins.

## Decision

1. **The harness owns every file it uses.** Nothing points at another plugin, at an install
   location another plugin used, or at a folder the harness does not create itself.
2. **Instructions live in the skill that uses them.** Each stack skill's procedure and rules move
   into that skill's `SKILL.md`, with the rules as a plain Markdown list (the model reads them; they
   do not need to be TypeScript). The `.agent/…` references are removed from the skills and their
   manifests, and `skills/codex_workflows/` is removed once nothing else in it is worth keeping.
3. **One folder per repository.** Everything the harness writes into a governed repository lives
   under `.harness/`. Bootstrap moves the older folders (`.codex-workflows/`,
   `.agile-backlog-toolkit/`, `.monolithic-code-review/`, `.agentic/`) into it.
4. **Reconcile merges, never rebases.** The reconcile rule list already says merge only; the
   procedure text and the skill that say "merge or rebase" change to match.

## Options Considered

- **Point the skills at `skills/codex_workflows/`:** works, but keeps a folder named after another
  plugin and a split between a skill and the instructions it depends on.
- **Have bootstrap copy the files into each project's `.agent/` (the original behaviour):** spreads
  plugin internals into every repository and lets copies drift from the installed version.
- **Fold them into the skills, one repository folder (chosen).**

## Consequences

### Positive

- A skill is self-contained: reading `SKILL.md` gives the whole procedure.
- A governed repository has one harness folder to ignore, back up, or remove.
- No file can go stale because the plugin updated and a copy did not.

### Trade-offs

- Existing repositories need a one-time move of their older folders, done by re-running bootstrap.
- Every runtime path that reads the older folders changes, and needs tests.

## Follow-up

- Fold the four procedures and rule lists into their skills; remove `.agent/…` references and
  `skills/codex_workflows/` (after checking its coding rules and templates).
- Consolidate repository state under `.harness/`, with a bootstrap migration.
- Related, from the same review: block rebase, squash merges, and force-push on Story and Feature
  branches in governed repositories without relying on the agent to switch the guard on.

### Gaps found while documenting the workflow

Answering the product questions in the README ("Common questions") turned up gaps outside this
decision's scope, recorded here so they are not lost:

- **Work already in progress:** no workflow adopts an in-flight branch, maps its commits to the
  Story's Tasks, and resumes; the workflow hooks refuse writes on a branch outside the naming
  convention.
- **Test-first vs `tests-with-code`:** the `tdd` skill allows a Task with no practical automated
  test to use a manual check, but the hook blocks a source commit with no test changes in the
  commit or on the branch, so such a Task cannot be the first commit on a branch.
- **Brainstorming:** no step for exploring a problem or deciding whether to build something; the
  harness starts once the team knows what to build.
- **Worker agents:** implementation is one agent, one Task at a time; nothing dispatches Tasks or
  Stories to parallel agents.
- **Choosing the flow:** single-Story versus stacked-Feature is described in the conductor skill,
  not decided by code.
