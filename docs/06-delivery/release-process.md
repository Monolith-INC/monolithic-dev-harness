---
title: Release Process
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-16
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
- all test suites on Python 3.12 and 3.13;
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

## Pre-release (version candidates)

Every version candidate is cut as a pre-release, `X.Y.Z-rc.N`, and tried in a live trial before
the final `X.Y.Z`:

1. Bump every version source to `X.Y.Z-rc.N` (the README badge writes the hyphen as `--`:
   `version-X.Y.Z--rc.N-orange`) and head the candidate's `CHANGELOG.md` section with it.
2. `python3 scripts/check_versions.py` must pass; tag the commit `vX.Y.Z-rc.N` and push the tag.
   The release workflow publishes it as a GitHub pre-release.
3. The owner copies the test project, installs the pre-release into it with
   `install.sh --version X.Y.Z-rc.N`, and runs the trial as a user would. The agent then reads the
   run's transcript and its folder, confirming first that the installed version is the candidate.
4. Fixes from the trial go into the next candidate (`rc.N+1`); the final release renames the
   section to `X.Y.Z`.

## Post-release Validation

Run the manual gates above. Users upgrade by re-running the installer.

## Rollback

Delete the GitHub release (keep the tag for history) and tell users to install the previous version
with `--version`. Fix forward with a new patch release.
