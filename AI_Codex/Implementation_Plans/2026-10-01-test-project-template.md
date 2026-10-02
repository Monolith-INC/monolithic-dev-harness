---
type: implementation-plan
status: implementation-and-live-trial
created: 2026-10-01
spec: [[2026-10-01-test-project-template-design]]
---

# Reusable live-trial project template — implementation plan

## Delivery order

1. Create a Flutter support-ticket app with working ticket intake, assignment, status, reply/note, queue search/filter, persistence, and tests. Document its architecture and operation, then seed a realistic product-owner request to merge duplicate tickets while preserving history. Leave the implementation approach open for the live technical-discovery trial.
2. Add a standard-library helper that creates an isolated copy with a Git baseline and safely
   discards only copies it created.
3. Document how the template and helper fit the existing automated checks and future live trials.
4. Verify the app where the installed Flutter SDK permits, check copy/discard behavior, run the full
   harness suite, and run repository quality checks.
5. Bootstrap the installed Codex harness in a disposable project copy and run the approved
   discovery-to-delivery live trial with a deliberately isolated tracker workspace.

## Acceptance checks

- The sample app has no dependency on network services or an external tracker.
- Pure task transformations have focused tests; the Flutter project includes its own test.
- A prepared copy is outside the source tree, starts with a clean Git baseline, and has the
  expected files.
- Discard rejects an arbitrary directory and removes only a marked temporary trial.
- The canonical template is byte-for-byte unchanged by prepare/discard.
- The live run uses a disposable project copy and an isolated tracker workspace.
- The host and tracker records, generated work, local harness setup, and working copy are discarded
  or removed after evidence is captured; the canonical template stays unchanged.

## Follow-up boundary

The user approved continuing into a real host and tracker run after fixture implementation. Keep the
live trial isolated, follow the harness's required review gates for external writes, and record
evidence without committing the disposable project.
