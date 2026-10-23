---
title: Codex adapter development trial
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-23
---

# Codex adapter development trial

Date: 2026-10-23. Status: RC4 published and installed; final qualification remains pending.

Published candidate: [v0.7.0-rc.4](https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.7.0-rc.4),
tagged commit `0ed24a2018463125ea56109df7731d90c44bd12d`.
The downloaded archive and installer both passed the published `SHA256SUMS` checks.
Archive SHA-256: `71d9123ff7a21599d016b814f741703fc22100c3ff99940249355cb468ac0e36`.
The release is explicitly a prerelease; no final `0.7.0` tag was created.

The user explicitly authorized the root to operate the trial on their behalf. Responses submitted by the operator through the actual Codex client protocol are operator actions; they are not represented as human button clicks. Temporary configuration, credentials symlinks and captures live under `/tmp/mdh-codex-proof`; credentials are never copied into evidence.

| Probe | Observed result | Limit |
| --- | --- | --- |
| Native CLI delegation | Real root/child identities, spawn/wait and child pre/post hooks captured on CLI 0.162.1 | Initial and clean-environment child execution encountered sandbox socket ownership failure; no successful child write claimed |
| Plan synchronous question | Native `item/tool/requestUserInput`, blocking=true, Blue/Green options; actual operator response recognized | Planning preference, protocol only; not rendered Desktop UI or external-write approval |
| Default async domain review | Native async AgentMessage with Approve/Revise; later actual operator input recognized | No sandbox permission requested; delivery acknowledgement itself was never an answer |
| Harness decision round trip | PASS: CLI staged a session-bound decision; actual async ask adopted it; later native operator input recorded `answer=Yes` in the same work session | Source trial, not rendered Desktop UI or an external-write approval |
| Trusted async hooks | Exact disposable handler definitions reviewed and trust hashes persisted; native pre/post callbacks completed | Own test handlers, not qualification of installed plugin trust |
| Integrated child governance | PASS: authentic native child patch denied by current harness hook with `[harness human-owned]`; real lifecycle binding persisted then revoked on Stop | Operator-seeded parent scope; current source, not installed archive/full Feature/Story trial; driver stopped on child completion with a cleanup warning |
| Published archive installation | PASS: actual installer registered RC4 in an isolated Codex profile; installed hook, binding and runtime modules match the downloaded archive byte for byte | CLI 0.162.1; not the user's active Desktop process |
| Native plugin discovery | PASS: nine actual plugin hooks discovered; reviewed hashes trusted only in the isolated profile; backlog/workflow/integrations MCP servers each returned initialized capabilities and 22/22/21 tools | Discovery/initialization, not an external tracker operation |
| RC4 installed decision | PASS: actual native async presentation and later operator input recorded `Yes`, transport `async`, native conversation and work-session IDs | [Persisted decision](rc4-installed-decision.json); operator response, not Desktop click or external-effect approval |
| RC4 installed follow-up | PASS for turn renewal: same child recorded two distinct completed turns; FAIL for successful mutation | [Actual events and binding](rc4-installed-worker.json); nested sandbox blocked host socket access, then missing file prevented append; driver recursion failed at root completion |
| RC4 child post-tool wire | FAIL: child startup guard emitted PreToolUse output and Codex rejected it | Fixed for RC5; RC4 does not pass acceptance |

The socket failure was traced with official source to a host daemon directory that the enclosing
agent sandbox deliberately masks as mode `000`. An approved read outside that sandbox confirmed
the host directory has the required owner and mode `0700`. No directory permissions were changed.
The RC5 trial will use the approved host execution facility while preserving the trial Codex
process's workspace sandbox and the harness hooks. The temporary RPC driver's recursion and
64 KiB response-buffer limitations were also corrected; these are trial tooling defects.

The source documentation and sanitized protocol/hook fixtures are linked from [evidence.md](evidence.md). Each probe answers a different unresolved boundary; no broad model-driven trial loop is authorized by this report.

## Release requirements still to prove

- Current Desktop surface and visible structured controls.
- Successful legitimate worker effects, independent read-only reviewer enforcement, exact owned-file scope, same-child follow-up and cancellation.
- Existing laws across every advertised Claude workflow family.
- Genuine harness decision capture, reviewed content/scope binding, interruption/recovery and exactly-once scoped external write on a dedicated authorized fixture.

A protocol pass or a green unit test does not clear these requirements. Preserve pending gates and report concrete blockers rather than describing a partial adapter as fully functional.

## Verification to date

One combined core/integration/delivery/harness run produced 1,582 passes, one skip and six
failures caused by outdated presentation assumptions. Those affected assertions and native
bootstrap discovery were corrected; the focused resulting slice passed 96 tests. The installer
configuration regression passed its shell contract, and the changed bootstrap slice passed eight
tests. The follow-up-turn correction passed 92 focused binding/runtime tests, Ruff, metadata,
version and Markdown checks. All four mandatory CI jobs passed on the tagged commit, including
the full Python 3.12 and 3.13 suites and archive installation. The release workflow independently
passed its required tests and published the three verified assets. No final full-parity release
is claimed.
