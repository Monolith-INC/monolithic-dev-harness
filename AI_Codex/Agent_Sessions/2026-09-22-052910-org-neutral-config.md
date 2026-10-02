---
title: Org-neutral configuration
type: agent-session
timestamp: 2026-09-22T05:29:10-03:00
created: 2026-09-22
status: closed
branch: techdebt/org-neutral-config
next: "[[2026-09-22-062208-repo-grooming]]"
tags:
  - dev-harness
---

# Org-neutral configuration

Previous session: [[2026-09-22-044237-dev-harness-build]]

## Goal

Remove every mention of the client organization's name from the harness files. `AZURE_DEVOPS_ORG`
becomes required (no built-in default). Enricher prompts read the subproject list from the
repository's router instead of hard-coding it.

## Constraints

- `TXT.txt` (the spike ticket, untracked) is the user's document: not edited.
- Git history (`6549e00`) still contains the old text; rewriting it needs the user's explicit decision.

## Progress

- [x] Edits applied; grep finds no mention outside `TXT.txt`.
- [x] All suites green (362 + 173); manifests validate; health check and bootstrap verified with the
      org supplied only through `AZURE_DEVOPS_ORG`.
- [x] README "spike" section rewritten as standalone design decisions; demo wording removed from the
      harness skill.
- [x] Client-specific content removed: example policy replaced by `examples/policy.example.json`;
      enrichers route to the repository's own router; test fixtures neutral.
- [x] Cruft sweep: `.gitkeep`, Codex `openai.yaml`, Gemini/Antigravity/Codex host adapters and hook
      wrappers, OpenAI schema translators, the old installer (only `configure_integrations` kept, now
      `scripts/harness/integrations_setup.py` with tests); 12 broken skill references fixed.
- [x] Rule codes renamed to self-describing names (`approval-required`, `protected-items`, …).
- [x] Suites: backlog 362 passed; delivery + harness 133 passed. Manifests validate.
- [x] Committed (`c726102`), then history rewritten at the user's request: `main` on GitHub is a
      single root commit `0f3f972` (same tree as `c726102`); old remote branches deleted. Local backup
      of the old commits: `backup/pre-rewrite`. Local checkout is `techdebt/clean-history` (= origin/main)
      because the git guard refuses to create a local `main`.
