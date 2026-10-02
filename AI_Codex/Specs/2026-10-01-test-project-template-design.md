---
type: design-doc
area: acceptance-testing
stack: [flutter, dart, python, markdown]
tags: [design, acceptance-testing, fixture]
created: 2026-10-01
status: approved
source: [conversation-2026-10-01]
---

# Reusable live-trial project template — design

## Problem

The harness develops and validates work inside a project, so the harness repository cannot by
itself demonstrate the full product workflow from a project's first idea through implementation.
A repeatable, realistic project is needed for human-run acceptance trials.

## Goal

Keep a committed Flutter project template in `test-project-template/`. Each trial starts from a
fresh copy in a temporary directory with its own Git repository and baseline commit. Trial work is
performed only in that copy; maintainers can inspect it and then discard it through a guarded
helper. `AI_Codex/` keeps the design, trial findings, and defects, not the temporary project.

## Fixture content

The template must be a grounded application with a clear purpose and several working features, representing a product already in motion. Its documentation describes its users, current behavior, product direction, code shape, architecture, and validation approach. It includes a realistic product-owner request for a feature addition, specific enough to investigate while leaving meaningful implementation decisions open. The current proposal is a support-ticket desk with a request to merge duplicate tickets while preserving conversation history.

The default trial exercises technical discovery: inspect the actual project, identify affected code and constraints, compare feasible approaches, and prepare the documentation and full implementation strategy before backlog work. Product ideation may remain an optional route; it is not the main flow.

## Trial lifecycle

1. `scripts/acceptance_trial.py prepare` copies the canonical template to a unique temporary
   directory, initializes Git in the copy, and records one local baseline commit.
2. The maintainer points the selected coding host at that copy. The source template remains
   unchanged.
3. Host installation, bootstrap choices, tracker isolation, and the full live run are selected for
   each trial. This helper does not change host configuration, install the harness, or write to a
   tracker.
4. The maintainer records findings and defects in `AI_Codex/Artifacts/live-trials/`, inspects the
   temporary project, and discards it with `scripts/acceptance_trial.py discard <project-path>`.

Discard only accepts a project created by the helper directly under the system temporary folder and
bearing its ownership marker. It removes that trial directory alone. The source template is never a
valid discard target.

## Success criteria

- Every prepared copy contains the same app and documentation as the committed template.
- Each copy has an independent Git repository with a clean baseline commit.
- Preparing and discarding a trial never changes the source template.
- A user can start with a realistic product-owner feature request and take it through technical discovery, a reviewed feature strategy, backlog and implementation planning, implementation, validation, and delivery.
- Findings compare observed behavior against outcomes, not prescribed artifact wording.
- Temporary copies and host/tracker setup are not committed as trial evidence.

## Boundaries

- Existing deterministic unit and integration suites remain the continuous automated checks.
- A real host, model run, tracker workspace, credentials, approvals, and live evidence are outside
  this implementation. Their setup will be designed with the user before a live trial.
- The helper does not install or uninstall the harness and does not create tracker items.
- The fixture does not include a detailed specification for its unresolved opportunity.

## Source guidance

- [Dart functions](https://dart.dev/language/functions)
- [Dart patterns](https://dart.dev/language/patterns)
- [Flutter learning pathway](https://docs.flutter.dev/learn/pathway)
