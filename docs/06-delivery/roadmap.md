---
title: Roadmap
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-09-26
---

# Roadmap

## Objective

Move from a verified build to a process the team runs on real work, then automate the parts that
do not need a person.

## Scope

The plugin, its installer, and its documentation. Board and repository configuration stay with
each team.

## Milestones

| Milestone | Status | Exit evidence |
| --- | --- | --- |
| 0.1.0: first release, four stages, seven rules, one-shot install | done | CI green; sandboxed Claude Code install |
| 0.2.0: trackers are adapters (Azure DevOps, Linear, local), one settings file, sessions, onboarding | done | CI green |
| Live check of the Linear adapter | next | a read, a create, a transition, and a comment against a real workspace |
| Live observation in Claude Code | next | a Story taken from idea to draft PR in a governed repository, every gate recorded |
| Live observation in Cursor | next | the plugin loads; a denied write and an approved write observed |
| Cost per stage measured | next | token usage recorded per stage on at least three real Stories |
| Triggers from Azure DevOps (service hooks / pipelines) | later | a validation comment posted when a card moves to Ready |
| Public installer | later | the repository or its releases are public, so plain `curl` works |

## Build

See [release-process.md](release-process.md#build).

## Release Gates

See [release-process.md](release-process.md#release-gates).

## Owner Approval Requirements

Milestone changes are decided by the maintainers.

## Release

See [release-process.md](release-process.md).

## Post-release Validation

See [release-process.md](release-process.md#post-release-validation).

## Rollback

See [../04-operations/deployment.md](../04-operations/deployment.md#rollback).
