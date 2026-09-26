---
title: monolithic-dev-harness Documentation
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# monolithic-dev-harness Documentation

This directory is the documentation interface for `monolithic-dev-harness`, a Claude Code and
Cursor plugin that runs a team's delivery process on Azure DevOps, Linear, a repository-local
tracker, or an onboarded one: backlog refinement, technical planning, spec-driven implementation,
and requirements-first review. Model-driven skills do the
work; a deterministic hook runtime, fed by evidence keyed to git ids, decides which tool calls are
allowed.

## Documentation map

```text
docs/
|-- README.md
|-- 00-product/
|   |-- vision.md
|   |-- requirements.md
|   `-- glossary.md
|-- 01-architecture/
|   |-- system-context.md
|   |-- architecture.md
|   |-- data-model.md
|   `-- decisions/
|       |-- ADR-0001-deterministic-enforcement-in-hooks.md
|       |-- ADR-0002-per-repository-opt-in.md
|       |-- ADR-0003-human-only-approval-windows.md
|       |-- ADR-0004-protected-items-are-never-linked.md
|       |-- ADR-0005-claude-code-and-cursor-only.md
|       |-- ADR-0006-install-from-release-archives.md
|       |-- ADR-0007-backlog-owns-what-spec-owns-how.md
|       |-- ADR-0008-the-harness-owns-its-files.md
|       `-- ADR-0009-trackers-are-adapters.md
|-- 02-design/
|   |-- api.md
|   |-- components.md
|   `-- workflows.md
|-- 03-engineering/
|   |-- development.md
|   |-- testing.md
|   |-- coding-standards.md
|   `-- dependencies.md
|-- 04-operations/
|   |-- deployment.md
|   |-- environments.md
|   |-- observability.md
|   `-- runbook.md
|-- 05-security/
|   |-- security.md
|   |-- threat-model.md
|   `-- data-privacy.md
|-- 06-delivery/
|   |-- roadmap.md
|   |-- release-process.md
|   |-- changelog.md
|   `-- checkpoints/
|       `-- pr-16-rework.md
`-- 07-guides/
    |-- onboarding.md
    |-- user-guide.md
    `-- troubleshooting.md
```

## Canonical source hierarchy

When documentation and behavior disagree, the authority order is: the code and its tests
(`plugins/monolithic-dev-harness/scripts/`, `runtime/`, `trackers/`, `tests/`), then the schemas
(`config/settings.schema.json`, `config/tracker.schema.json`), then each skill's `SKILL.md`,
then the ADRs, then these documents. Installed copies (the Claude plugin cache, Cursor's local
plugin directory, `~/.local/share/monolithic-dev-harness`) and release archives are derived
artifacts and must not be hand-edited.

## Source basis

These documents were written from the repository's code, skills, hook configuration, tests, and
installer. Behavior the test suites or CI prove is stated as fact. Behavior that has not been
observed end to end, notably loading in Cursor and full runs against live Azure DevOps and Linear projects,
is marked as pending rather than presented as verified.
