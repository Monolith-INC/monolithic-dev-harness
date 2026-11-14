---
id: "3-mechanics/stack"
tier: 3
type: "mechanics"
area: "stack"
title: "Runtime and dependencies"
read_when: "Checking runtime support and direct dependencies before adding code."
provenance: "derived"
sources:
  - "pyproject.toml"
  - "requirements-dev.txt"
  - "plugins/monolithic-dev-harness/requirements-runtime.txt"
  - ".github/workflows/ci.yml"
derived_from_commit: "a2f686a38a25825d70e6b4a80c71f17c16315953"
updated: "2026-11-14"
version: 1
status: "current"
supersedes: []
links:
  - "[[4-rules/coding-standards]]"
---

## Summary

The authored runtime is primarily Python and shell. Ruff targets Python 3.12, and the CI test matrix covers Python 3.12 and 3.13.

## Commands

Read requirements-dev.txt and plugins/monolithic-dev-harness/requirements-runtime.txt before installing dependencies.

## Detail

The runtime requirements declare Jinja2>=3.1,<4. Development requirements include pytest>=8.3,<10, ruff==0.16.4 and shellcheck-py. No primary TypeScript application or tsconfig was found; the four tracked TypeScript files are vendored workflow rules. Review setup therefore records the TypeScript default as off, while changed TypeScript files can still invoke that lens.

## Open questions

- Direct dependency ranges are visible, but this store does not assert exact transitive versions or licence approval.
