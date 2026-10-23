---
title: Codex adapter contract evidence
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-23
---

# Codex adapter contract evidence

Captured 2026-10-23. The initial probes below are historical feasibility evidence,
not completed candidate acceptance. Current implementation and trial outcomes are
recorded in [trial.md](trial.md).
The governing design and plan are
[design](../../../superpowers/specs/2026-10-23-codex-adapter-design.md) and
[plan](../../../superpowers/plans/2026-10-23-codex-adapter-release.md).

## Feasibility decision

**GO for child identity feasibility on CLI 0.162.1.** Real native child
`PreToolUse` captures contain `agent_id` and `agent_type` in addition to the shared
parent `session_id`. The child identity matches real `SubagentStart` and
`SubagentStop` events. This removes the suspected parent-only identity limitation
for the observed `apply_patch` and shell paths.

**GO for required domain-review transport feasibility through the observed
Default async route.** A real `request_user_input_async` delivery carried
Approve/Revise choices; an actual later operator `turn/steer` produced a native
`userMessage` containing Approve and the model acknowledged that choice.
This is protocol qualification with authorized operator automation. End-to-end
harness decision authority, artifact binding, hook recovery, external writes and
Desktop rendering remain pending.

Default's synchronous `request_user_input` contract permits optional input and
expressly prohibits permission requests. The separate async handler emits
structured questions and returns immediate delivery acknowledgement; it does not
return an answer. This observed fixture decision was an application-domain
review, not a host permission request. It does not establish a general exception
for every question class or runtime. Plan planning-preference protocol also
completed independently; Plan continues to prohibit executing mutations.

The initial and clean-environment child executions failed with an inherited socket-directory sandbox
configuration error. Captured pre-tool lineage remains valid; successful writes,
policy denial and full workflow parity remain unqualified. A source-supported
capability does not establish that an installed release enforces harness laws.

## Frozen boundaries

| Boundary | Observation | Classification |
| --- | --- | --- |
| Repository | `ce8f1e7ad824ec2d178cb1e39ec0cdacb73e22d4`; manifests `0.7.0-rc.3` | Verified read |
| Existing work | `.root-architect/` and `docs/superpowers/` untracked at discovery | Preserved |
| Local/remote candidates | Both list `v0.7.0-rc.1`, `rc.2`, `rc.3`; remote `rc.3` peels to repository HEAD | Verified read; may change |
| Upstream | `git ls-remote https://github.com/openai/codex.git HEAD` returned `398500106707f0a3217c7cf83edc2bf226cc342f` | Verified source pin |
| PATH CLI | `codex --version`: `codex-cli 0.162.1` | Verified CLI binary |
| Desktop package | `/usr/lib/chatgpt/resources/linux-package-metadata.json`: `26.1013.40934`, brand `chatgpt`, production flavor | Verified package metadata |
| Current agent executable | `/proc/1/exe`: `/usr/lib/chatgpt/resources/codex`; that binary reports `0.163.0-alpha.10.2` | Verified executable, separate from CLI |
| Cached daemon | `app-server-daemon/current` points to package `0.163.0` | Verified cache; not proof of running daemon |
| Installed harness | Both marketplace plugin copies read `0.7.0-rc.3` | Verified manifests; live process version unknown |
| User hook trust | Config has trusted hashes for harness Codex pre/post/question/prompt/stop handlers | Verified configuration; matching active code still needs trial |
| Disposable CLI proof | Native spawn, child pre-tool, stop and wait events | Verified actual events |
| Desktop proof | No corresponding Desktop child-effect capture | Unknown |

## Immutable official contract

All source links below pin the same upstream revision. Files fetched to
`/tmp/codex-adapter-evidence-3985001` are source evidence, not installed binary
provenance. The load-bearing downloaded file hashes are preserved in
[`source-contract.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/source-contract.json).

| Claim | Immutable source | Result |
| --- | --- | --- |
| Pre-tool stdin has optional `agent_id`/`agent_type` alongside session/turn IDs | [schema.rs lines 276–298](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/hooks/src/schema.rs#L276-L298) | Documented; installed CLI capture confirms |
| Child context derives `agent_id` from the real `sess.thread_id()` for `ThreadSpawn` | [hook_runtime.rs lines 1065–1085](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/core/src/hook_runtime.rs#L1065-L1085) | Documented; separate from shared `sess.session_id()` |
| Pre-tool serialization propagates child fields and canonical tool name | [pre_tool_use.rs lines 169–191](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/hooks/src/events/pre_tool_use.rs#L169-L191) | Documented; matcher aliases need observed normalization |
| Subagent start is context injection; `continue:false` does not deny spawn | [session_start.rs lines 218–224](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/hooks/src/events/session_start.rs#L218-L224) | Documented limitation |
| Native question is root-only; only Plan sets `is_blocking` true | [request_user_input.rs lines 67–85](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/core/src/tools/handlers/request_user_input.rs#L67-L85) | Documented; installed CLI Plan protocol confirms blocking |
| Async native handler emits `AgentMessage` with async delivery/questions and returns `accepted:true` | [request_user_input_async.rs lines 131–147](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/core/src/tools/handlers/request_user_input_async.rs#L131-L147) | Documented delivery semantics; actual async delivery and later operator input observed |
| Default allows optional questions and excludes permission/escalation requests | [default.md](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/collaboration-mode-templates/templates/default.md) | Documented; matches current mode instructions |
| Plan picker is for planning decisions, important assumptions and undiscoverable information | [plan.md](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/collaboration-mode-templates/templates/plan.md#L59-L77) | Documented planning use; required external-effect approval not established |

Context7 was asked the exact unresolved question: whether Plan explicitly permits
required application-domain approvals such as approving an implementation plan
or external tracker write, separately from sandbox escalation. It returned the
Default prohibition, mode feature gating, host permission controls and the TUI
plan implementation popup. It did not provide an explicit required external
write picker exception. The TUI popup is a separate UI control and cannot be
treated as a generic `request_user_input` transport.

## Authentic capture and sanitization

The root ran one disposable CLI fixture in `/tmp/mdh-codex-proof`; this worker
read its actual hook stdin files. Repository fixtures are in
[`tests/delivery/fixtures/codex`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/).
Each is a real event, not an inferred reconstruction. The path prefix becomes
`/fixture/codex-proof`; native disposable IDs remain unchanged. The encrypted
native spawn brief is replaced with a fixed redaction string. Formatting changed
to indented JSON. See [`profile.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/profile.json)
and [`capture-provenance.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/capture-provenance.json).

| Fixture | Actual observation |
| --- | --- |
| `subagent-start.json` | Native child ID `01a1699b-f275-78b3-b7a4-6df0669a1a2f`, role `default` |
| `pre-tool.json` | Child `apply_patch`; same child ID, shared root session `01a1699b-cf45-7ef1-9285-2ff031a16c13` |
| `pre-tool-shell.json` | Child shell `pwd`; canonical hook name `Bash`, same child ID |
| `post-tool-shell-failure.json` | Actual error: socket directory must be user owned with mode `0700` |
| `pre-tool-spawn.json`, `post-tool-spawn.json` | Native canonical hook name `collaborationspawn_agent`; actual return names `/root/child_proof` |
| `pre-tool-wait.json`, `post-tool-wait.json` | Native canonical hook name `collaborationwait_agent`; actual non-timeout return |
| `subagent-stop.json` | Same child identity, root transcript plus separate child transcript, failure report |

No synchronous `ask.json` or `answer.json`, nor `prompt.json` or `interrupt.json`,
is present because no corresponding authentic event was supplied. The actual
async pre/post-hook captures are recorded separately below. No human answer was synthesized.
The installed harness matcher currently lacks the observed concatenated spawn
and wait aliases; broad lifecycle governance therefore remains an implementation
and acceptance task. The source supports enforceable pre-tool denial; this
capture used observation handlers and does not prove harness denial.

## Authorized operator protocol probe

The user's later direction authorized the root to run the trial autonomously on
the user's authority. Operator automation therefore supersedes the earlier need
to await a human selection for this protocol probe. It does not establish human
UI rendering or human answer capture.

The root started the installed CLI app-server with a native Plan collaboration
mode and a read-only sandbox, asking one planning preference: the color of the
test artifact. The actual server request is preserved in
[`protocol-question-request.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/protocol-question-request.json):
method `item/tool/requestUserInput`, real request ID `0`, `isBlocking: true`,
question ID `color`, and options Blue/Green. The authorized client driver sent
Blue against that actual request. The observed server resolution and final
`Selected color: Blue.` are retained in separate fixtures.

[`protocol-question-provenance.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/protocol-question-provenance.json)
records server-log and driver hashes, the sending expression, and the limits.
The driver did not log outgoing bytes. Its source plus native server resolution
and result substantiate the operator response; no reconstructed outgoing
message is labeled as a captured event. No ask/answer hook event executed in this
probe. This is **GO for the installed CLI Plan planning-preference protocol**,
with operator automation. This Plan preference proof does not qualify required
external-effect approval, Desktop rendering or hook answer recovery. The
independent Default async proof below qualifies only its stated protocol scope.

## Default async domain-review protocol probe

The root subsequently tested `request_user_input_async` on the actual installed
CLI app-server in Default mode. The real completed `AgentMessage` has
`delivery: "async"`, title `Approve the fixture document?`, and options Approve
and Revise. The operator driver responded through `turn/steer` using the actual
observed thread and turn IDs. The server then emitted a completed `userMessage`
whose text was `Approve`, followed by `Operator choice: Approve.`

Those three real events are preserved as
[`protocol-async-question.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/protocol-async-question.json),
[`protocol-async-operator-answer.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/protocol-async-operator-answer.json),
and [`protocol-async-result.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/protocol-async-result.json).
[`protocol-async-provenance.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/protocol-async-provenance.json)
records source hashes, driver/log identity, transport and limits. Actual native
IDs are preserved; unrelated account/settings events were excluded.

This is **GO for the required fixture domain-review transport protocol** with
authorized operator automation. The pinned async handler independently confirms
that immediate `accepted:true` acknowledges delivery. The later actual input is
the response; delivery itself grants no authority. The probe performed no
external effect, produced no harness approval record, and did not exercise human
rendering or answer hooks. Its success does not qualify those boundaries.

## Trusted async hook capture

A subsequent bounded run used the exact reviewed disposable capture command
and the `currentHash` values returned by native `hooks/list`. Those hashes were
recorded for the temporary configuration's corresponding trust keys. Native
`hook/completed` callbacks show both pre-tool and post-tool handlers completed.
This establishes execution of these temporary capture handlers; it does not
qualify the user's installed harness plugin trust or policy enforcement.

[`ask-async.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/ask-async.json)
is actual `PreToolUse` stdin for `request_user_input_async`, carrying the
Approve/Revise question. [`answer-async-delivery.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/answer-async-delivery.json)
is the matching actual `PostToolUse` stdin. Its serialized `tool_response` is
`{"accepted":true}`. The shared native `tool_use_id` binds the two events;
this response is delivery acknowledgement and cannot be recorded as approval.

[`async-hook-provenance.json`](../../../../plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/async-hook-provenance.json)
retains raw/sanitized hashes, reviewed capture script hash, initial hook-list
trust statuses, matching configured trust hashes, and actual completed callbacks
from `/tmp/mdh-codex-proof/async-trusted-events.jsonl`. Only the disposable path
prefix was replaced. This is **GO for the observed async pre/post-hook wire
contract**, with later answer ingestion and harness authority still unqualified.

## Resumable checkpoint

Use the observed async transport only within its qualified domain-review scope;
bind the later actual response through harness policy before granting authority.
Resolve the disposable child sandbox configuration to distinguish
successful effect execution from observed pre-tool identity, then qualify denial,
bindings, wrapper coverage and Desktop behavior. Keep absent evidence explicitly
unknown. No broad suites, product changes, installation or release was performed
by this evidence worker.

## Follow-up turn contract and correction

Context7 was queried specifically for follow-up lifecycle semantics. Its returned
`followup_task` specification confirms reuse of an idle existing child. The pinned
[hook runtime](https://github.com/openai/codex/blob/398500106707f0a3217c7cf83edc2bf226cc342f/codex-rs/core/src/hook_runtime.rs#L129-L150)
dispatches `SubagentStart` on Startup/Fork; stop hooks close individual turns.
Context7 also returned a generalized summary claiming that start hooks can block:
that summary conflicts with the quoted parser implementation and is not used.

The first archive-installed worker probe correctly denied an unlinked code edit
under the existing Story/Bug prerequisite, then exposed an adapter defect: its
follow-up turn was also denied because the previous turn had stopped. The adapter
now records completed turn IDs and renews only authentic fresh turns in the same
frozen scope. Interrupted/conflicted records stay terminal; same/missing/replayed
turns and stale stop events cannot reactivate them. Focused hook integration
checks exercise the normal governed path and preserve the suspension bypass.
This correction still requires the updated archive's installed-host trial.
