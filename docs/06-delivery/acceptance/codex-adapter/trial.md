---
title: Codex adapter development trial
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-23
---

# Codex adapter development trial

Date: 2026-10-23. Status: RC6 published, installed and its corrected native question trial passed.
Final qualification is blocked by the unresolved requirements below.

Latest candidate: [v0.7.0-rc.6](https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.7.0-rc.6),
tagged commit `bcab959744f7b9bc8126d39894200a5a2e122b82`.
Archive SHA-256: `3034c56cc60dfdfaf12995a0185f2f5272ec3d079cbfcc5cb3564ff3b103bf1f`.
All four CI jobs and the release workflow passed on that source. Downloaded assets passed
`SHA256SUMS`; loaded adapter modules matched the archive byte for byte. The actual installer
registered the candidate in a fresh private CLI profile. Active Desktop configuration was not
upgraded by these isolated installations.

Published candidate: [v0.7.0-rc.4](https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.7.0-rc.4),
tagged commit `0ed24a2018463125ea56109df7731d90c44bd12d`.
The downloaded archive and installer both passed the published `SHA256SUMS` checks.
Archive SHA-256: `71d9123ff7a21599d016b814f741703fc22100c3ff99940249355cb468ac0e36`.
The release is explicitly a prerelease; no final `0.7.0` tag was created.

The subsequent RC5 archive, tagged at `2d59406b38f47867fefc03d111be59da8ab4f90e`, also
passed its published checksum, installer, all four CI jobs and release workflow.
Archive SHA-256: `44467e3e50c616a8c86d869df7563e6e82c0f750d7d0ddaeee87418b7b7504ff`.

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
| RC5 worker and follow-up | PASS: native `pwd` exited zero; two actual file-change events completed; file contains `text proof` and `followup`; same child UUID, two completed turns | [Actual worker evidence](rc5-installed-worker.json); `gpt-5.6-luna` / low observed in native activity; planning artifact only |
| RC5 worker hooks | PASS: no failed hook callbacks across worker/follow-up; post-tool context accepted | Actual installed archive, fresh profile, reviewed trust hashes; no general Desktop qualification |
| RC5 cancellation | Native activity reported interrupted, but adapter revocation FAILS qualification: saved binding remained active and no Interrupt callback appeared | No OS-process cancellation claim; mismatching fresh turns still fail lineage checks |
| RC5 native answer | Answer persisted in correct conversation/work session, but UserPromptSubmit callback FAIL: diagnostic text looked like invalid JSON | [Actual decision and failed callback](rc5-installed-decision.json); corrected with explicit Codex prompt JSON for RC6 |
| RC6 installed question and answer | PASS: real async question, later operator `Yes`, answered record in the same native conversation/work session; both prompt callbacks completed; no failed hook callbacks; driver exited zero | [Actual events and decision](rc6-installed-decision.json); native protocol, not rendered Desktop buttons or external-effect approval |
| RC6 package discovery | PASS: nine actual hooks; reviewed hashes trusted in the private profile; all three harness MCP servers initialized | Installed hook, bridge, runtime and child-binding modules match the verified release archive |

The socket failure was traced with official source to a host daemon directory that the enclosing
agent sandbox deliberately masks as mode `000`. An approved read outside that sandbox confirmed
the host directory has the required owner and mode `0700`. No directory permissions were changed.
The RC5 trial used the approved host execution facility while preserving the trial Codex
process's workspace sandbox and the harness hooks. The temporary RPC driver's recursion and
64 KiB response-buffer limitations were also corrected; these are trial tooling defects.

The source documentation and sanitized protocol/hook fixtures are linked from [evidence.md](evidence.md). Each probe answers a different unresolved boundary; no broad model-driven trial loop is authorized by this report.

## Shared process messaging development trial (2026-10-24)

The owner corrected the integration boundary: one standard protocol/interface and a central
message catalog, with vendor translation only in adapters. The implementation uses JSON-RPC 2.0
and one local message bus. Main-agent cancellation withdraws permission without waiting for a
vendor interruption hook; agent-reported status and host-observed status are recorded separately.

A fresh private profile installed a development source snapshot, retaining the RC6 manifest
version; this was not a published release. Loaded module bytes matched the trial source and nine
reviewed hook hashes were trusted only in that profile. A real native trial used a `gpt-6-sol`
main agent at medium effort and one `gpt-5.6-luna` subagent at low effort.

| Check | Result |
| --- | --- |
| Legitimate initial effect | Native file-change event completed; fixture contains `before cancellation`. |
| Standard cancellation | `harness process cancel` returned success; generic record persisted `revoked: true`. |
| Native interruption/report | Native activity reported interruption; standard `process report` saved `reported_status: interrupted`. |
| Subsequent effect | The same subagent's actual patch attempt was denied; file content remained unchanged. |
| State meaning | Last host observation remained `running`; the main-agent report and permission withdrawal were separate. |
| Hook/driver health | No failed hook callback; driver exited zero. |

[Authentic sanitized events and record](process-bus-native-trial.json) include source-module,
driver and raw-log hashes. The parent work session was operator-seeded; this does not qualify
onboarding, human UI or external writes. An already-running `sleep 30` command completed normally;
no OS-process termination guarantee is inferred from native agent interruption.

This closes the development implementation gap for permission withdrawal through the standard
message channel. The published RC6 archive is unchanged. Packaging this correction and the other
release requirements remain separate gates.

A second bounded probe checked the remaining enforcement distinction on the final source: the
main agent withdrew permission while the original subagent execution was still running, then
waited for its next patch attempt before requesting native interruption. The patch was denied
specifically because the process had no permission, with the same native turn ID as the initial
successful write. The generic record subsequently observed execution completion while retaining
`revoked: true`. The main agent correctly omitted an interruption report when native status
showed the task had already completed. No hook callback failed; driver exited zero.
The [same-execution evidence](process-bus-same-execution-trial.json) records the matching turn IDs,
ordering, final state and exact loaded-module hashes.

Focused protocol/adapter/hook/session/question checks passed 271 tests. A scoped review found
one report from an old execution could carry over to a new execution. Its regression failed,
then passed after resetting the report when a new execution starts. Queries, updates and their
success/error envelopes use the same central JSON-RPC catalog and bus interface.

## RC7 installed assignment acceptance (2026-10-24)

Published [v0.7.0-rc.7](https://github.com/Monolith-INC/monolithic-dev-harness/releases/tag/v0.7.0-rc.7)
comes from `276f8f2cdcb4f0cedc36359a553f09f00ee5ecce`. All four CI jobs and the
release workflow passed. Downloaded archive SHA-256 is
`7e44101de9dc6c962a2c0656553bd150819286f5e2a8f6b25ec6e32f1fb43fe3`.
The archive and installer checksums matched. The actual installer ran in a private profile;
all 12 inspected loaded modules matched the archive. Eight actual hooks were reviewed and
trusted only in that profile. The active Desktop installation was unchanged.

A bounded actual CLI trial used a `gpt-6.1-sol` main agent at medium effort, a
`gpt-5.6-luna` worker at low effort and an independent-context `gpt-6-sol` reviewer at
medium effort. Native activity confirmed both subagent selections. Each returned tool-free
READY, received its immutable assignment through the authenticated standard command, then
received its task on a fresh native follow-up execution.

- The worker successfully created its exact owned planning file.
- The worker had two calls blocked by the actual assignment-policy hook. The outside-scope
  fixture file was absent at readback. The prompt requested one negative attempt; preserve
  this deviation and do not infer exactly-once behavior from the agent's summary.
- The reviewer read the proof successfully, then its actual edit attempt was blocked by the
  assignment-policy hook. Final proof bytes matched the original successful native file change.
- Both generic process records retained their assignments and reached completed status.
- No hook callback failed; the protocol driver exited zero.

[Sanitized authentic events, records and hashes](rc7-installed-assignments.json) preserve the
observations and limits. This qualifies this candidate's CLI assignment boundary. The parent
work session was operator-seeded; this does not qualify full onboarding, human Desktop controls,
all workflow families or external-write recovery. Requested effort and this trial's observed
effort are distinct from a general runtime effort-enforcement guarantee.

## RC8 Desktop structured-answer checkpoint

RC8 is published from `e883695c69b2d8be97d3d5c18b41584ec2db6963`. Its public installer,
archive checksums and installation lifecycle passed the
[installation acceptance checks](../installation/rc8-source-trial.md).

The operator opened a fresh Desktop chat in the disposable project
`/tmp/mdh-rc8-desktop-9QUjpH/project`. All three project-configured MCP services returned
actual responses. The integrations tracker-description operation correctly reported that the
project was not bootstrapped. Cross-host doctor inventory also found pre-existing Claude
registration overlap in another project and an unrelated legacy backup; no repair was applied.

The native async question `Accept this acceptance outline?` offered `Accept` and `Revise`.
The actual operator selected `Accept`; public decision status retained that exact answer,
native session/call IDs, presentation `HD-a8d5817d7e140f55` and the `REVIEW.md` digest.
[Authentic sanitized question, operator response and decision](rc8-installed-desktop.json)
qualify Desktop structured domain-feedback capture. The decision had `approval: false` and
no work-session scope. It does not qualify an external-effect approval or recovery. The file
preview was queued, so visible artifact review remains separately unqualified.

Ordinary setup next encountered the host's read-only `.git/info/exclude` boundary while
preparing its setup proposal. No setup was applied or internal record changed to bypass it.
Continuation must use the supported host permission mechanism for that narrowly scoped
bootstrap operation and preserve genuine setup decisions.

## Remaining final release gates

- Work-session-scoped Desktop approval and verified visible artifact review. RC8's native
  structured domain-feedback selection and answer capture passed the checkpoint above.
- General reasoning-effort policy enforcement and any assignment operations outside the qualified tool paths.
- Existing laws across every advertised Claude workflow family.
- Genuine harness decision capture, reviewed content/scope binding, interruption/recovery and exactly-once scoped external write on a dedicated authorized fixture.

A protocol pass or a green unit test does not clear these requirements. Preserve pending gates and report concrete blockers rather than describing a partial adapter as fully functional.

Model-facing status text or a model-written lifecycle receipt cannot supply human authority.
The shared message channel now
withdraws permission independently of native interruption callbacks, as the same-execution
trial demonstrates. Termination of already-running operating-system processes remains unqualified.
The remaining workflow families and a dedicated external-write/recovery fixture also need their
stated evidence. These are release blockers, not permission to bypass existing harness laws.

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

The final prompt correction reproduced four failed output-contract regressions, then passed the
117-test Codex slice. RC6 CI and release checks passed, and the changed boundary passed its real
archive-installed question trial. The unchanged worker/follow-up boundary retains RC5's authentic
successful effect evidence; it was not rerun for the prompt-only correction.
