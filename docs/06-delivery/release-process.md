---
title: Release Process
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-30
---

# Release Process

## Objective

Every release is built by CI from a tagged commit on `main`, carries a checksum, and installs with
one command.

## Scope

The release archive, `install.sh`, `SHA256SUMS`, and the GitHub release notes.

## Milestones

See [roadmap.md](roadmap.md).

## Build

```bash
scripts/build_release.sh            # dist/monolithic-dev-harness-<v>.tar.gz, install.sh, SHA256SUMS
```

The archive is `git archive` of the tagged commit: the marketplace catalogs, the plugin (without its
tests), `README.md`, `CHANGELOG.md`, and `THIRD_PARTY_NOTICES.md`.

## Release Gates

Automated (CI, required before tagging):

- lint, format, shellcheck, JSON and schema validation;
- all test suites on Python 3.10 and 3.12;
- `claude plugin validate` for the plugin and the marketplace;
- the built archive installs into sandboxed Claude Code and Codex profiles and a Cursor directory;
  both plugin registrations, the Codex custom agents, and `harness doctor` are checked;
- `scripts/check_versions.py --tag vX.Y.Z` (the release workflow refuses a mismatched tag).

Manual (after publishing, before announcing):

- install on a real machine with the one-line installer;
- restart Claude Code, open a governed repository, and confirm one denied write
  (`approval-required`) and one approved write;
- restart Codex, review and trust the plugin hooks through `/hooks`, and confirm one denied write
  and one approved write in a governed repository; untrusted hooks are skipped;
- make one read-only Azure DevOps call through `workflow-integrations` in a governed repository.

## Owner Approval Requirements

A maintainer approves the release pull request and pushes the tag.

## Release

1. On a branch, bump the version in:
   `plugins/monolithic-dev-harness/.claude-plugin/plugin.json`,
   `plugins/monolithic-dev-harness/.cursor-plugin/plugin.json`,
   `plugins/monolithic-dev-harness/.codex-plugin/plugin.json`,
   `.claude-plugin/marketplace.json`, and the README version badge.
2. Add a `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md` and its link at the bottom.
3. `python3 scripts/check_versions.py` must pass. Open a pull request; merge when CI is green.
4. Tag the merge commit and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "vX.Y.Z" <merge commit> && git push origin vX.Y.Z
   ```

5. The release workflow re-runs the tests, builds the archive, and publishes the GitHub release with
   the CHANGELOG section as notes and the three assets attached.

## Post-release Validation

Run the manual gates above. Users upgrade by re-running the installer.

## Rollback

Delete the GitHub release (keep the tag for history) and tell users to install the previous version
with `--version`. Fix forward with a new patch release.
