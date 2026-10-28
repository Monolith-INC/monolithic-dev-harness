---
title: RC8 installation acceptance
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-25
---

# RC8 installation acceptance

Source, packaged and published-installer trials used disposable homes and projects. These
results do not supersede the Codex adapter's remaining native/Desktop qualification gates.

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

## Published candidate verification

- Candidate: [v0.7.0-rc.8](https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.7.0-rc.8).
- Tagged commit: `e883695c69b2d8be97d3d5c18b41584ec2db6963`.
- [Required CI](https://github.com/Monolith-INC/monolithic-dev-harness/actions/runs/40179552807)
  and [release workflow](https://github.com/Monolith-INC/monolithic-dev-harness/actions/runs/40180307346)
  completed successfully. This includes Python 3.12/3.13 suites, formatting/lint and
  packaged installation/removal. The initial CI failure was corrected in the tagged commit:
  five adapter factories needed formatting and the Claude CLI fixture needed its native profile
  directory, which the real CLI creates but the stub did not.
- The downloaded archive and installer passed their published `SHA256SUMS` checks.
  Archive SHA-256: `3882d8cc11b1d25f62f79aba389f5b969a204c40d213dec966af412843daa0ad`.
  Installer SHA-256: `23b5c2d5caf80cacc0bf4c999ec5f36548d70f904b32600616d7aa04c28b273f`.
  The downloaded archive matches the locally tested build byte for byte.
- Archive installation, doctor and all-scope purge passed in `/tmp/mdh-rc8-archive-H7ns5Y`.
- The public GitHub release installer was fetched with curl and piped into Bash with
  `--version 0.7.0-rc.8 --scope local --project <fixture> --host codex --yes`.
  Download/checksum verification, installation, doctor and all-scope purge passed in
  `/tmp/mdh-rc8-curl-v5BAB1`. This used the release download route, not `--source`.
- No project package/command copy or user-wide Codex registration was created. Purge removed
  the fixture's registration, shared package and CLI link.
- The installed published doctor detected a deliberately seeded user/project MCP duplicate
  in `/tmp/mdh-rc8-doctor-ohcgbvgj`. Selecting its user entry, previewing the selection digest
  and applying that exact selection removed only the selected entry. The project registration
  and unrelated settings were preserved. This is a controlled repair trial, not a claim that
  the actual user's pre-existing configuration was repaired.

Installation delivery is complete for this candidate. Full workflow parity, Desktop controls,
reasoning-effort observation and external-write/recovery acceptance retain
[their existing qualification status](../../../epic-0008-codex-host-adapter/acceptance/codex-adapter/trial.md). RC8 is a prerelease, not a
final fully functional Codex parity release.
