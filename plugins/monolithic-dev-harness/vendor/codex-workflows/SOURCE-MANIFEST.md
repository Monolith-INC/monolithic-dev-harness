# Bundled codex-workflows source

## Provenance

- Upstream project: `codex-workflows-plugin` (local source `/home/monolith/projects/codex-workflows-plugin`)
- Version 0.5.26, source revision `75c22f0bfd9e7e3c428f33383970dfb2a3e0eabd`, copied 2026-10-16

## Files in this repository

`upstream/skills/` holds the eleven delivery skills exactly as the source has them, and
`upstream/skills/codex_workflows/` the four stage sequences (`resources/`) and their rule files.

The harness runs the copies under `../../skills/<name>/`, each copied over from `upstream/` and
aligned only where the source conflicts with the harness contract
([`CONSTITUTION.md`](../../../../CONSTITUTION.md)); each adds an "In the harness" section for the
harness steps it needs. The four stage sequences live in their skills as
`references/stage-workflow.md`.

| Seam | Source | Harness copy |
| --- | --- | --- |
| Git and pull requests | branches, stacked PRs and a Feature→trunk PR are part of every flow | Git steps only with Git-based delivery; a pull request only when the user asks, never a condition for done (Article 10) |
| Feature plan | an implementation plan published on the Feature | none: one approved plan per Story (Article 8) |
| Spec kinds | `write-spec` may write an implementation plan; its tech-spec template restates the plan | technical specs only (no `implementation-plan` template); the tech spec links the Story's approved plan |
| History rules | `.codex-workflows/active-stage` and `.agent/rules/*.ts` | the harness's `history-preserved` hook; merge only, never rebase |
| Paths | `integrations.json`, `.local-tracker/` | `.harness/settings.json` (`branch_template`), `Tickets/` |
| Approvals | implicit | harness gates: `move-item`, `approve-spec`, `publish-branch` |

Not copied: the source's `bootstrap` skill (the harness has its own setup skill of that name) and
its runtime scripts (the harness has its own).
