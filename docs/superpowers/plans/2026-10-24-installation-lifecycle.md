---
title: Installation lifecycle rework
status: approved
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-25
---

# Installation lifecycle implementation plan

> Execute with Superpowers executing-plans, focused regression checks and one final independent review. Owner approved the scope choices and subsequently added purge, all-scope removal and cross-host doctor repair.

**Goal:** Make installation scope explicit and give the harness one ownership-aware install, update, remove, purge and diagnostic lifecycle.

**Architecture:** Keep the published curl/bash entry point and release archive. Reuse existing package preparation and host assets. A shared installation contract defines scope, component inventory, ownership and repair operations; host adapters translate their configuration layouts. Defer the separate product-wide unified adapter/Pydantic proposal.

**Stack:** Bash entry point, Python 3.12+, immutable dataclasses and Result, existing JSON/TOML formats and pytest.

## Approved behavior

- Initial scopes: `user` (available across projects) and `local` (private to a selected project). Reserve `project` for a future shared/versioned mode; do not silently reinterpret it.
- Prompt for missing scope in an interactive installation. Automation supplies `--scope`; `--yes` does not choose scope.
- `--project <path>` selects a private project. Preserve unrelated configuration and project work; do not activate user-wide/Desktop host registrations for local scope. Package storage stays at the original shared location.
- `--uninstall --scope all` covers user and discoverable/explicit project installations across supported hosts, reporting the inspected roots. Do not claim discovery of every unknown checkout.
- `--purge` resets harness-owned settings/configuration/state as well as removing the installation. Combined with installation it performs a scoped fresh installation. Ordinary removal retains project settings and state.
- Never delete host-wide credentials, source code, Tickets, planning documents or unrelated host settings. Unknown ownership is a finding requiring a specific repair, not permission to delete.
- Retain release checksums, explicit version selection, local source installation, curl and authenticated GitHub download entry points.
- Doctor searches all supported adapters and scopes for old packages, registration leftovers, hooks, MCP servers, skills, agents, settings, caches, backups and receipts. Static presence does not prove live activation.
- Offer concrete scope-specific repairs; require deliberate selection before destructive repair. Applying a stale plan must fail on changed content or symlink escape.

## Storage correction approved by the owner

Package storage and registration scope are independent. Keep the original installer storage
logic; do not add a release-version store or per-project package/executable copies.

| Item | Removed uncommitted relocation | Restored location for both scopes |
| --- | --- | --- |
| Main package | `PROJECT/.harness/install/marketplace` | `~/.local/share/monolithic-dev-harness/marketplace` |
| CLI | `PROJECT/.harness/bin/harness` | `~/.local/bin/harness` |
| Kimi command wrapper | `PROJECT/.harness/bin/harness-kimi` | No new wrapper; use native `--config-file` |
| Project settings/registration | No relocation required | Native project configuration and `.harness/installation.json` |

Existing directory overrides remain supported. Host-managed plugin copies/caches retain the
original host installation behavior. The installer maintains one current package. A project
reference index is registration metadata, not user-wide host activation. Project removal keeps
the shared package; user removal retains it while projects reference it; all-scope removal clears
known registrations before removing the shared package.

## Task 1: Map existing artifacts and freeze shared contracts

Files: `install.sh`, `scripts/harness/preferences.py`, `scripts/harness/bootstrap.py`, `host_adapters/installation_contract.py`, adapter implementations and `tests/harness/test_installation_contract.py`.

- [x] Map package roots, profiles, native caches, CLI links, custom agents, shared skills/agents, Zed/Kimi managed entries and backups, historical question marker, preferences and repository state.
- [x] Introduce immutable Component/Inventory/Finding/Repair and versioned InstallationAdapter contract; begin with all-adapter failing conformance tests.
- [x] Implement adapter locations and contract tests for every supported host; unsupported operations must be explicit.

## Task 2: Inventory and pure removal/repair plans

Files: `harness/installation_inventory.py`, `harness/installation_cleanup.py`, and focused tests.

- [x] Test exact ownership, malformed/unreadable configuration, absent optional paths, links, stale versions, duplicate effect identities, unrelated names, JSONC strings and quoted TOML keys.
- [x] Implement read-only discovery and pure selector-based repairs. Shared configuration is never deleted wholesale because it mentions the harness.
- [x] Test scope/host/project isolation, purge versus ordinary removal, stale digests, protected artifacts and deterministic repair plans.

## Task 3: Scoped entry point and ownership receipts

Files: `install.sh`, new shared lifecycle module(s), host adapter installation helpers, installer shell tests and `tests/run.sh`.

- [x] Test interactive/noninteractive scope selection, all-scope uninstall, explicit purge, conflicting flags and curl-compatible execution.
- [x] Reuse package staging and existing host support with explicit destinations; add private-project integration through the adapter contract.
- [x] Record version, scope, source root, destinations, hashes, links, native registrations and owned configuration edits. Preserve non-owned content and exclude private artifacts locally without untracking existing files.
- [x] Implement scoped removal and purge using inventory and receipts, including legacy exact ownership checks and repairable conflicts.

## Task 4: Doctor integration and repair UX

Files: `harness/cli.py`, installation inventory/cleanup executor and tests.

- [x] Add installation inventory to doctor, machine-readable output, explicit scope/project selection and repair previews.
- [x] Show detected source/version/scope, conflicts, uninspected locations and concrete repair commands. Do not equate installed files with a healthy live runtime.
- [x] Revalidate ownership and fingerprints before applying selected repairs; rerun the affected checks.

## Task 5: Delivery

- [x] Update installer/API/runbook documentation and ownership/removal semantics, distinguishing package installation from project bootstrap.
- [x] Run focused checks for changed boundaries, independent inventory reviews, mandatory CI and release workflow. Do not repeat broad suites locally. Both reported inventory findings are closed; see the RC8 installation acceptance report.
- [x] Publish the next candidate only after required CI; prove curl/source installation, repeat installation, scoped removal/purge and duplicate repair in disposable projects. RC8 is published; source lifecycle trials, repair contract tests and the published curl install/doctor/purge trial provide the recorded evidence.
- [x] Preserve RC7 evidence and remaining native/Desktop/workflow/approval qualification gates. Do not call incomplete parity a final release.
