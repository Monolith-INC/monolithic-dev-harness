---
title: RC8 installation source acceptance
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-25
---

# RC8 installation source acceptance

These are source-checkout trials in disposable homes and projects. They are not archive or
Desktop acceptance, and do not supersede the Codex adapter's remaining qualification gates.

## Storage and registration

- Restored the original package and CLI locations for both scopes. No per-project package,
  project command directory, release-version store, or package version pin is created.
- Registered two independent projects against the shared current package. Independent project
  registrations are distinct scopes, not duplicate activations.
- Removing one project preserved the package and the second project's registration.
- Removing user registration while a project remained also preserved the shared package/CLI.
- All-scope purge removed the remaining known registration, shared package and command link.
- The piped Bash entry point was exercised with explicit local scope and project paths containing
  spaces. A controlling-terminal probe accepted local scope and rejected a missing project
  before writing installation files.

The shared-storage fixture was `/tmp/mdh-shared-storage-otasWw`. Native app-server discovery
observed eight project hooks and three responding services: backlog-orchestrator (22 tools),
workflow-orchestrator (22), workflow-integrations (21). No model inference or visible Desktop
selection was exercised. An isolated profile supplied project trust for this fixture only.

## User registration and removal

Actual Claude and Codex CLIs installed the source into a separate temporary user profile.
Both native plugin and marketplace registrations were subsequently removed. Foreign Zed
settings and the explicit Codex question-feature preference were preserved. No change was made
to the actual user's Desktop or model profiles. The fixture was
`/tmp/mdh-native-user-MJnIKU`.

## Review closure and focused checks

- Marketplace ownership requires the expected or receipt-recorded root; finding a product
  manifest at an unrelated root does not authorize removal.
- Package publication rejects a symlink at the destination or any ancestor.
- Focused installation tests cover the shared adapter contract across all five supported hosts,
  scope isolation, protected settings, native registration schemas, receipt recovery, ownership,
  structured repair selection and shared-package lifetime.
- Ruff, Markdown, repository integrity and version-source checks passed before commit.

Mandatory CI and published-archive verification remain delivery gates. Full workflow parity,
Desktop controls, reasoning-effort observation and external-write/recovery acceptance retain
[their existing qualification status](../codex-adapter/trial.md).
