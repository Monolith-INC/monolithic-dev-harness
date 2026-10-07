---
title: ADR-0011 Standard questions catalog
status: active
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-07
---

# ADR-0011: Standard questions live in one catalog, in every language

## Status

Accepted

## Context

The harness asks the same questions at the same points of every run: the project language, setup
confirmation, the next step, the plan checkpoint, and each kind of write approval. Each skill used
to word these itself, and agents translated them on the fly. Wording drifted between skills,
Portuguese questions were improvised, and an approval's wording said nothing the write check could
hold it to.

## Decision

Every standard question is an entry in `config/gates.toml`: its question, up to three options with
what each means, the default recommendation, whether it takes free text, whether it approves
writes, and what such an approval is tied to (`artifacts`, `item:{ref}`, `branch:{branch}`,
`pr:{pr}`, or nothing). Each entry carries the text for every supported language (English and
Brazilian Portuguese). The agent asks it with `harness decision present --gate <id>`, fills the
entry's slots with `--value`, and the harness shows the version for the project's language.

Approvals can only be asked through a gate. One-off questions specific to a piece of work stay
free-form through the same command and render the same way.

## Options Considered

- **Wording in each skill:** no catalog to maintain, but the same question drifts between skills,
  translations are improvised, and nothing can check that an approval was asked properly.
- **One catalog (chosen):** one source per question, translations written once and reviewed,
  approvals tied to a declared context. Starting now is cheaper than moving every skill later.

## Consequences

### Positive

- The same question reads the same everywhere, in either language, on every host and fallback.
- A test checks that every entry has every language, the same slots and options in each, and passes
  the plain-question rules; approval entries must offer `Approve`.
- An approval's context comes from its gate, so the write check can enforce it (ADR-0003).

### Trade-offs

- A question's wording lives in the catalog while the skill that asks it says what each option
  does; changing one may need the other.
- Adding a language means translating every entry before it can ship.

## Validation

`tests/harness/test_gates.py`, `tests/harness/test_bound_approvals.py`, and
`tests/harness/test_decision_reuse.py`.

## References

- [ADR-0003](ADR-0003-human-only-approval-windows.md)
- `plugins/monolithic-dev-harness/references/human-decisions.md`
