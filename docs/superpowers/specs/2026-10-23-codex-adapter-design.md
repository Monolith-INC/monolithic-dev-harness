---
title: Codex adapter release design
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-23
---

# Codex adapter release design

Date: 2026-10-23. Status: design approved by the root agent acting as the user's delegated
representative; implementation and release remain unperformed. The root selected approach A below.

## Intent and scope

Deliver a Codex adapter that can run the harness's governed workflows, communicate decisions with
native structured controls when the host permits them, coordinate real subagents, recover genuine
answers, and show reviewable artifacts. Preserve the operational laws and existing Claude behavior.
Reduce repeated investigation and verification without removing release gates.

The primary qualification target is the user's installed Codex Desktop. Qualify CLI independently
before advertising the same outcomes there. A native model tool, a Python subprocess, the CLI,
Desktop, and an account-provided Canvas surface are distinct integration boundaries. A capability
on one boundary proves nothing about another.

This is an adapter release, not a rewrite of the harness, workflow engine, tracker gateway, or
other hosts. Do not replace native subagents with separate `codex exec` sessions. Do not equate a
visualization or file preview with editable Canvas. Do not bypass a gate to make a trial pass.

## Current evidence and limitations

Repository inspected at `ce8f1e7ad824ec2d178cb1e39ec0cdacb73e22d4`; version manifests read
`0.7.0-rc.3`. The locally invoked CLI reports `codex-cli 0.162.1`; this does not establish the
Desktop build. No implementation tests or live acceptance were run during this planning work.

| Evidence | Confirmed observation | Boundary or outstanding proof |
| --- | --- | --- |
| `scripts/host_adapters/codex_adapter.py` | Parses policy events/session ID and formats deny/allow output; `subagents()` returns `unsupported_ops` | This describes the current Python contract, not native Codex capabilities |
| `hosts/codex.json`, `config/host.schema.json` | Five subprocess operations are declared unsupported with unsourced caveats; supported claims require empirical provenance | Replace broad wording with precise surface evidence; never flip flags for an instruction-only bridge |
| `scripts/host_adapters/claude_adapter.py` | Claude's Python subagent operations are also unsupported | Claude's actual skill workflows, rather than this stub, define parity |
| `hooks/codex.hooks.json` | Registers pre-tool, question ask/answer, prompt, startup, and Stop handlers | Actual installed event names, wrapper tools, trust, child inheritance and interruptions need capture |
| `scripts/host_adapters/interactions.py` | Codex presentation currently assumes native blocking by availability flag; async uses a separate tool and bounded wait instructions | Host mode, root-only access, advertised tools, and permission restrictions must govern transport |
| `scripts/host_adapters/answer_recovery.py` | Blocking recovery checks session/cwd, call ID, question and options against a supplied transcript | Validate current payload fixtures, wrong-session rejection, duplicates and restart recovery |
| `install.sh` | Creates a separate Codex marketplace copy, expands MCP paths, installs two read-only custom agents, enables a question feature when unset and refuses explicit false | Installed feature availability and preserving user configuration require focused installer contracts |
| `scripts/harness/cli.py` | Doctor explicitly states it does not check live question capture | Installation success must remain separate from operational readiness |
| Official Codex sources retrieved through Context7, 2026-10-23 | Native hook schema/runtime includes PreToolUse, PostToolUse, UserPromptSubmit, SubagentStart/Stop and Interrupt; hooks have trust state | Mutable upstream sources must be pinned to a revision before implementation decisions are locked |
| Official Codex question/runtime sources retrieved through Context7 | Default question availability is feature gated; async depends on root and model-advertised tools; Plan and Default have different blocking semantics | A callable tool is not proof that a required approval may use it |
| Official default instructions retrieved through Context7 | `request_user_input` must not be used for permission or escalation requests; Default optional input may continue unanswered | Distinguish domain decisions from host sandbox escalation; unresolved required structured approval compatibility blocks release |
| Official app-server sources retrieved through Context7 | Multi-agent V2 child threads reject direct `turn/start` and `turn/steer`; native control handles child input | Do not design an external child-control service around those endpoints |
| Official hook event source retrieved through Context7 | `SubagentStart` supplies context and ignores `continue: false`; common hook `session_id` may identify the parent | Start notification cannot be advertised as a denied spawn; authentic per-effect child identity remains a feasibility gate |
| Official visualization documentation retrieved through Context7 | Rendering differs across Desktop, CLI and IDE | Canvas edit access is a separate unknown capability until actually demonstrated |

Official source anchors presently checked are
[hook schema](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/schema.rs),
[hook runtime](https://github.com/openai/codex/blob/main/codex-rs/core/src/hook_runtime.rs),
[app-server hook protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server-protocol/src/protocol/v2/hook.rs),
[turn completion](https://github.com/openai/codex/blob/main/codex-rs/core/src/session/turn.rs), and
[tool result handling](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/registry.rs).
Additional checked anchors are
[tool configuration](https://github.com/openai/codex/blob/main/codex-rs/tools/src/tool_config.rs),
[tool planning](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/spec_plan.rs),
[question handler](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/handlers/request_user_input.rs),
[Default instructions](https://github.com/openai/codex/blob/main/codex-rs/collaboration-mode-templates/templates/default.md),
[app-server input processing](https://github.com/openai/codex/blob/main/codex-rs/app-server/src/request_processors/thread_input.rs),
[subagent startup context](https://github.com/openai/codex/blob/main/codex-rs/hooks/src/events/session_start.rs),
[app-server documentation](https://learn.chatgpt.com/docs/app-server), and
[visualization documentation](https://learn.chatgpt.com/docs/visualizations).
These links describe upstream source, not a guarantee about the installed binary. Task 1 of the
plan records immutable links, relevant excerpts and installed runtime fixtures for every claim.

## Approaches

1. **A: native workflow integration, selected.** Let the current model invoke its native subagent
   and question tools, while the adapter normalizes observed host events, checks authority, and
   records receipts. Retain deterministic policy and state. This fits existing skills and limits
   transport work. It requires real evidence that child operations receive governance.
2. **B: app-server orchestration service.** Own long-lived external sessions and control transport.
   This introduces another lifecycle and authority boundary; direct child input is constrained in
   current official sources. It exceeds the release's time and quota scope.
3. **C: stabilize the existing compatibility package.** Improve installation and documentation only.
   This leaves requested native subagent workflows and structured decision reliability unproven and
   cannot satisfy the release outcome.

## Architecture and authority

Keep policy evaluation, decision records, artifact digests and work-session checks in the existing
runtime. Add a small Codex runtime profile and workflow reference describing model-callable tools
observed on the supported surface. The profile records evidence, mode and source, not universal
product capability. The existing `SubagentOps` API continues to describe callable subprocess
operations; an unsupported operation remains an explicit error.

The model-facing bridge prepares an operation from a scoped brief, calls the actual native tool,
and accepts only the real host result as its receipt. Preparing instructions is not a successful
start. A receipt is not authorization. Lifecycle state comes from native event/result evidence;
unobserved state is `unknown`. Never accept model-written JSON as a host event or fabricate a
handle, answer, approval, child identity, completion or cancellation.

The root owns human communication and the governing work session. Child briefs carry their real
parent identity, project, work-session reference, owned files, permitted effect class, model/effort
ceiling and governing plan. Reviewers read the stated artifact in independent contexts and return
findings; workers return changes/evidence within their assignment. Neither may grant authority to
itself or another child. A child needing a decision returns the need to the root.

Hook-originated child bindings associate a real native child with its root work session. Binding
records are human-owned state and cannot be written by an agent-facing receipt command. Missing,
ambiguous or contradictory lineage blocks guarded child effects. Native lifecycle tools are
normalized only after current payload evidence establishes their identity and effect. Follow-up
must target the original child, cancellation must be observed, and retried starts must not silently
create a second worker. Ended or interrupted work cannot spend a parent's stale approval.

Before broad implementation, perform one bounded native proof in an isolated fixture: capture the
actual spawn and child mutation events and establish an authenticated child identifier on each
guarded effect. A parent-only `session_id` is insufficient. No matching authenticated child ID means
no guarded effects; the release remains blocked until a host-supported lineage mechanism is
proved. `SubagentStart` is context notification, so deny spawn in an actual enforceable pre-tool
path only when supported; otherwise deny effects and describe that narrower guarantee honestly.
If a mutating event cannot distinguish root from child, never assume it came from the root to
grant authority; that runtime profile cannot qualify the guarded path.

## Decisions and answer recovery

Use one native question with at most three choices and the existing localized gate text. Show the
complete reviewed artifact before asking; bind authorization to unchanged content and scope.

Transport selection consumes the actual surface, mode, advertised tools and decision class.
Plan-mode native blocking, permitted Default optional input, and advertised asynchronous delivery
are separate cases. Never label Default input blocking simply because the tool exists. Never use
the question tool for host permission or sandbox escalation. Required domain approvals may use a
native picker only when current host instructions and actual observed behavior permit that use.
If that compatibility cannot be proved, keep the decision pending and report the release blocker.
Default mode's optional question contract does not authorize required domain approvals there.
Qualify the mandatory workflow in an explicitly permitted mode, preferring Plan only when its
operational instructions permit the specific domain decision. Async required decisions need their
own independent permission and actual surface proof.

The existing typed human-answer path remains a safe recovery path when applicable. It does not
count as satisfying the user's structured-control requirement. Do not silently downgrade that
requirement. No delivery, timer, dismissal, optional default or unrelated reply is an approval.
Async support must be observed on the root surface; wait interruptibly in bounded intervals only
when that tool exists, and preserve the pending question across interruption/restart.

Capture real hook answers first. Recover a missed answer only from the host-supplied authentic
transcript with matching native session, project, call ID, question ID/text/options, decision scope
and artifact digests. Replayed output must not reopen revoked approval. Fallback changes delivery
for the same decision, not its meaning or answer. Malformed/private responses produce a useful
failure reason without leaking response contents.

## Artifact review and Canvas

Follow `references/workflow-storyboard.md`: show the actual material using a verified interactive
document/editor, native rendered preview, opened file plus structured summary, or faithful inline
review. Preserve file identity and content digest through the decision. Record which surface was
used. A link alone is insufficient.

Discover Canvas/session tools on the actual account and inspect their supported operations before
claiming Canvas edit capability. If Canvas is unavailable or unknown, use the strongest verified
review surface and state that limitation in the supported-surface matrix. CLI qualification uses
its proven file/inline review route; it does not inherit Desktop rendering claims. Editable Canvas
is not mandatory for this release unless the required workflow specifically needs Canvas editing;
capability discovery and a truthful surface matrix are mandatory.

## Claude workflow parity and operational laws

| Existing workflow or law | Codex required outcome | Primary implementation boundary |
| --- | --- | --- |
| `skills/architect/SKILL.md` | Independent design candidates, real contexts, shared governing input | Native model-facing delegation |
| `skills/bmad-build/customize.toml` | Independent reviewer reads scoped material; no nested skill/spawn when forbidden | Child brief and installed instructions |
| `skills/bmad-prd/SKILL.md`, `skills/bmad-review/SKILL.md` | Extract instead of ingest, independent ready lenses, evidence-backed synthesis | Native fanout with bounded concurrency |
| `skills/bmad-party-mode/references/mode-subagent.md` | Real independent persona agents when selected and supported | Observed tool profile and mode |
| `skills/thermos/SKILL.md`, `codex-marketplace/agents/mdh_thermo_*.toml` | Both custom read-only reviewers load correct rubrics and return findings | Installer, discovery and sandbox evidence |
| Feature/Story work-session and implementation flow | Root assigns work from unchanged approved plan; worker effects stay in parent scope | Child binding plus existing workflow requirements |
| `human-owned` | Root and child cannot edit settings, approval/session/question/trust/evidence records directly | Every file/shell/wrapper mutation path |
| `tracker-invalid`, `approval-required`, `protected-items` | Real scoped approval required; protected records remain protected after approval | Gateway, hook normalization and common policy |
| `plain-questions` | Real human answer to one clear decision; no prefilled/forged answer | Native ask/answer and prompt capture |
| `generated-files`, guarded paths | Generated and guarded code requires existing approved path and evidence | Existing rules and workflow requirements |
| `draft-reviewed-prs`, `history-preserved`, `feature-branch` | Preserve draft/review/check, branch target and no-history-rewrite rules | Existing Git/SCM policy |
| Workflow code/completion requirements | Child edits and completion see same work-session, task, plan, checks and review gates | No separate child bypass |
| Pause/stop/cancel/resume/suspend | Stop authority promptly; retain evidence; only authentic human suspension/resume changes law | Native lifecycle and existing controls |

No advertised workflow is approved solely by matching prose. The evidence matrix must distinguish
static contracts, subprocess tests and observed installed-host execution. Inspect other direct
tool wrappers discovered in the live runtime; an uncovered mutating tool is a release blocker for
the advertised governed operation. Hooks are not claimed to be a universal security sandbox.

## Release and verification decisions

Use the next unused candidate in the current `0.7.0` release line after inspecting local and remote
tags; do not assume `rc.4` is free. Release `0.7.0` only after the candidate passes acceptance.
Preserve the installed previous version and user settings for rollback.
Prepare version sources and mandatory candidate CI first, obtain the existing maintainer
publication approval, and publish the candidate archive through the release workflow. Install
that checksum-verified candidate for the live trial; only the final release waits on its outcome.

Budget: one frozen evidence pass, one focused deterministic check per touched boundary, one fresh
builder check of this design/plan, one bounded final review, and one real Codex candidate trial.
Use at most the user-approved `gpt-6.1-sol` with high effort for top-tier agents. Run independent
reviews at the smallest useful scope; no repeated broad recon or model-driven soak loops. Mandatory
CI remains: lint/schema/docs/version/install gates, Python 3.12/3.13 full suites, and release
workflow checks. Repeat a failed slice only after its fix.

The real candidate trial starts from the installed release archive after restarting Desktop and
its gateway processes. It records version/profile, hook trust, MCP readiness, real child identity,
root/child denied effects, a governing Feature/Story worker, a `bmad-build` independent reviewer,
native lifecycle/follow-up/cancel, artifact presentation and a genuine human structured answer.
Compose minimal actual delegations for the remaining architect, PRD extraction, review fanout,
persona and thermos families in this same fixture. A broad parity claim requires evidence for
every included family; an omitted required Claude outcome blocks full parity release. Do not run
these complete workflows against a real product merely to collect evidence.
Exercise interruption and missed-answer recovery in this same bounded fixture. Use one disposable
local fixture and a dedicated remote fixture for one authentic denied/approved external write.
The absent human cannot be simulated: record a pending trial checkpoint until the actual answer
and authorization are captured. Synthetic fixtures remain deterministic test evidence only.

Release blocks on incompatible required structured decisions, unknown child law enforcement,
missing native lifecycle coverage needed by an advertised operation, unresolved critical findings,
failed CI/install/uninstall, absent real trial, or a host version outside the tested profile.
Maintainer PR approval and tag publication retain the existing release-process ownership.

Rollback uses the prior known-good archive via `--version`, restarts affected processes, restores
only installer-owned configuration, and preserves work sessions/decision evidence. Never rewrite
history or delete user state to make rollback appear healthy.

## Builder decisions and remaining proof

The root proxy approved approach A, Desktop-first qualification, independent CLI proof, strict laws,
the structured-decision blocker and the requirement for a genuine human trial answer. The author
chose a small runtime profile/reference plus normalized host receipts instead of expanding the
subprocess contract into an external orchestration service. Exact current native tool aliases,
hook lineage payloads, supported modes, Desktop build and source commit are evidence tasks, not
assumed answers. The implementation plan must freeze them before coding against those contracts.
The fresh builder check was completed; the root proxy approved the refinements on mode-specific
required decisions, Canvas scope, every parity family, authenticated child identity and notification
versus enforceable spawn denial. Proxy approval covers this design only; future runtime human
decisions and release ownership require the real authorized human.

## Updated execution model limits

The user subsequently required subagents one model tier below the root with medium reasoning
by default, and builder/coder subagents on `gpt-5.6-luna` with low (light) reasoning. Higher effort
requires a specific justification and cannot exceed high. These execution limits supersede the
earlier blanket top-tier subagent allowance.
