---
title: Codex adapter development trial
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-23
---

# Codex adapter development trial

Date: 2026-10-23. Status: development qualification in progress; no candidate or final release has been published.

The user explicitly authorized the root to operate the trial on their behalf. Responses submitted by the operator through the actual Codex client protocol are operator actions; they are not represented as human button clicks. Temporary configuration, credentials symlinks and captures live under `/tmp/mdh-codex-proof`; credentials are never copied into evidence.

| Probe | Observed result | Limit |
| --- | --- | --- |
| Native CLI delegation | Real root/child identities, spawn/wait and child pre/post hooks captured on CLI 0.162.1 | Initial and clean-environment child execution encountered sandbox socket ownership failure; no successful child write claimed |
| Plan synchronous question | Native `item/tool/requestUserInput`, blocking=true, Blue/Green options; actual operator response recognized | Planning preference, protocol only; not rendered Desktop UI or external-write approval |
| Default async domain review | Native async AgentMessage with Approve/Revise; later actual operator input recognized | No sandbox permission requested; delivery acknowledgement itself was never an answer |
| Harness decision round trip | PASS: CLI staged a session-bound decision; actual async ask adopted it; later native operator input recorded `answer=Yes` in the same work session | Source trial, not rendered Desktop UI or an external-write approval |
| Trusted async hooks | Exact disposable handler definitions reviewed and trust hashes persisted; native pre/post callbacks completed | Own test handlers, not qualification of installed plugin trust |
| Integrated child governance | PASS: authentic native child patch denied by current harness hook with `[harness human-owned]`; real lifecycle binding persisted then revoked on Stop | Operator-seeded parent scope; current source, not installed archive/full Feature/Story trial; driver stopped on child completion with a cleanup warning |

The source documentation and sanitized protocol/hook fixtures are linked from [evidence.md](evidence.md). Each probe answers a different unresolved boundary; no broad model-driven trial loop is authorized by this report.

## Release requirements still to prove

- Packaged installer, current Desktop surface and visible structured controls.
- Successful legitimate worker effects, independent read-only reviewer enforcement, exact owned-file scope, same-child follow-up and cancellation.
- Existing laws across every advertised Claude workflow family.
- Genuine harness decision capture, reviewed content/scope binding, interruption/recovery and exactly-once scoped external write on a dedicated authorized fixture.
- Required CI and release checks on the actual candidate commit.

A protocol pass or a green unit test does not clear these requirements. Preserve pending gates and report concrete blockers rather than describing a partial adapter as fully functional.

## Verification to date

One combined core/integration/delivery/harness run produced 1,582 passes, one skip and six
failures caused by outdated presentation assumptions. Those affected assertions and native
bootstrap discovery were corrected; the focused resulting slice passed 96 tests. The installer
configuration regression passed its shell contract, and the changed bootstrap slice passed eight
tests. Repository metadata, version consistency, Ruff and Markdown checks passed. CI on the
candidate commit remains required. No final full-parity release is claimed.
