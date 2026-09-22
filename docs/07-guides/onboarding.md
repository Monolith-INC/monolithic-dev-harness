---
title: Onboarding
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-22
---

# Onboarding

## Goal

Get a new contributor from a fresh clone to a merged change.

## Audience

Engineers changing the harness itself. To use the harness, see [user-guide.md](user-guide.md).

## Prerequisites

Python 3.10+, git, Node.js, Claude Code, and access to the repository.

## Procedure

1. Read [../00-product/vision.md](../00-product/vision.md),
   [../01-architecture/architecture.md](../01-architecture/architecture.md), and the ADRs in
   [../01-architecture/decisions/](../01-architecture/decisions/).
2. Set up the toolchain:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install pytest ruff==0.16.4 jsonschema shellcheck-py
   ```

3. Run the outcome gate from [../03-engineering/development.md](../03-engineering/development.md#full-outcome-gate).
4. Branch (`feature/…`, `bugfix/…`, `techdebt/…`), make the change with its tests, and try it with a
   sandboxed install (`bash install.sh --source .` under a temporary `HOME` and
   `CLAUDE_CONFIG_DIR`).
5. Open a pull request. CI must be green; a maintainer reviews and merges.

Contribution contract:

- The sources under `plugins/monolithic-dev-harness/` are authoritative; never edit an installed
  copy or `dist/`.
- A rule change ships with a deny test and an allow test through `hook.py`.
- Anything that must always hold is a hook, not skill text.
- No organization, client, or project names in the plugin.
- Update `docs/` with user-visible changes and `CHANGELOG.md` under `[Unreleased]`.

## Expected Result

A merged pull request with CI green and documentation current.

## Verification

CI on the pull request runs the same gate plus a sandboxed install of the built release.

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) and
[../03-engineering/development.md](../03-engineering/development.md#common-failure-modes).

## Related Documentation

- [../03-engineering/testing.md](../03-engineering/testing.md)
- [../03-engineering/coding-standards.md](../03-engineering/coding-standards.md)
- [../06-delivery/release-process.md](../06-delivery/release-process.md)
