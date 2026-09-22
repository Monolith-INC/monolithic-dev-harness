---
title: Coding Standards
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Coding Standards

## Purpose

Keep the runtime small, predictable, and safe to run before every tool call.

## Prerequisites

`ruff` 0.16.4 and `shellcheck` (see [development.md](development.md)).

## Authoritative Source Files

- `pyproject.toml` — ruff configuration: Python 3.10 target; rules `E4 E7 E9 F I UP B SIM DTZ`.
- `.editorconfig` — whitespace and line endings.

## Generated Files

None.

## Development Workflow

### Python

- Target Python 3.10; standard library only in anything a hook or the installer runs.
- `ruff check` and `ruff format` clean; no blanket `noqa` (a targeted one carries a reason).
- Timezone-aware datetimes (`DTZ`); every subprocess call has a timeout.
- A rule returns a `Decision`; it never raises for an expected condition and never performs the
  call it is judging.
- Deny messages start with `[harness <rule>]`, say what was found, and say how to fix it.

### Shell

- `set -euo pipefail`; `shellcheck` clean; portable to macOS bash 3.2 (no empty arrays under
  `set -u`, no associative arrays).
- Replace directories atomically (`.new` then `mv`).

### Skills and documentation

- A skill's frontmatter `name` equals its folder name; the description says when to use it.
- Skills explain rules; they never are the rule. Anything that must hold goes into a hook.
- No organization, client, or project names in the plugin; they belong in a repository's policy.
- Documents follow `docs/_templates`-style frontmatter (`title`, `status`, `owner`,
  `last_reviewed`) and use ASCII diagrams in `text` blocks.

## Tests

See [testing.md](testing.md).

## Full Outcome Gate

See [development.md](development.md#full-outcome-gate).

## Definition of Done

See [development.md](development.md#definition-of-done).

## Common Failure Modes

- A hook that imports a third-party package fails on a user's machine: keep hooks on the standard
  library.
- A rule that reads the conversation or model output: impossible and unsafe; rules read tool
  inputs, git, the policy, and evidence only.
