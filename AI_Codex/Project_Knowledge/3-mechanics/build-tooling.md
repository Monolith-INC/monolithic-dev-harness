---
id: "3-mechanics/build-tooling"
tier: 3
type: "mechanics"
area: "build"
title: "Build and quality commands"
read_when: "Selecting the repository checks appropriate to a change."
provenance: "derived"
sources:
  - ".github/workflows/ci.yml"
  - "pyproject.toml"
  - "scripts/build_release.sh"
  - "scripts/check_repo.py"
  - "scripts/check_versions.py"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[3-mechanics/testing]]"
---

## Summary

The repository uses Ruff, ShellCheck, repository validation, version checks and a release archive build.

## Commands

From repository root:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/check_repo.py
.venv/bin/python scripts/check_versions.py
scripts/build_release.sh
```

Use the workflow and development guide for the exact ShellCheck file list and plugin validation commands.

## Detail

The release workflow packages the plugin and installer and verifies archive installation. Do not edit release output to change authored behavior.

## Open questions

- CLI registration and hook trust must also be checked in the actual target host.
