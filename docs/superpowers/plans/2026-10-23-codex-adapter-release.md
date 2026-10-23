---
title: Codex Adapter Release Implementation Plan
status: draft
owner: monolithic-dev-harness maintainers
last_reviewed: 2026-10-23
---

# Codex Adapter Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release a proven Codex Desktop adapter for structured human decisions and real governed subagent workflows, qualifying CLI separately.

**Architecture:** Existing deterministic policy, human-owned records and work-session gates remain authoritative. A small Codex runtime profile and model-facing workflow bridge select actual native tools; hook-originated lifecycle evidence binds real children to existing scope. Unsupported Python subprocess operations stay explicit, and every advertised capability needs surface-specific evidence.

**Tech Stack:** Python 3.12/3.13, existing functional `core.result` helpers and frozen records, Bash installer, JSON schemas, Codex plugin/hooks/custom-agent TOML, existing pytest and shell contracts.

**Spec:** [Codex adapter design](../specs/2026-10-23-codex-adapter-design.md).

## Global Constraints

- The primary qualification target is the user's installed Codex Desktop. Qualify CLI independently before advertising the same outcomes there.
- A native model tool, a Python subprocess, the CLI, Desktop, and an account-provided Canvas surface are distinct integration boundaries.
- Never use the question tool for host permission or sandbox escalation.
- Required domain approvals may use a native picker only when current host instructions and actual observed behavior permit that use.
- If that compatibility cannot be proved, keep the decision pending and report the release blocker.
- The existing typed human-answer path remains a safe recovery path when applicable. It does not count as satisfying the user's structured-control requirement.
- No delivery, timer, dismissal, optional default or unrelated reply is an approval.
- Binding records are human-owned state and cannot be written by an agent-facing receipt command.
- Use at most the user-approved `gpt-6.1-sol` with high effort for top-tier agents.
- Do not replace native subagents with separate `codex exec` sessions.
- Do not equate a visualization or file preview with editable Canvas.
- Mandatory CI remains: lint/schema/docs/version/install gates, Python 3.12/3.13 full suites, and release workflow checks.
- The absent human cannot be simulated: record a pending trial checkpoint until the actual answer and authorization are captured.
- No product code, suites, installation changes, tag, publication or commit is performed by this planning deliverable.
- Implementation uses expression-oriented transformations, pattern matching, immutable records and returned `Result` values. Isolate I/O at existing boundaries; no unrelated style refactor.

## Review Focus

- Default mode exposes a question tool but forbids or does not await the proposed required approval: remain pending and fail qualification (Task 2).
- A child or another chat presents a valid-looking answer/approval from another scope: reject authority reuse and preserve the pending question (Tasks 2 and 3).
- A mutating wrapper/lifecycle tool is absent from registered hooks or child lineage is missing: deny guarded effects and report the exact unsupported path (Task 3).
- Interrupted/restarted execution replays a delivered question or revoked approval: recover real evidence once without resubmitting the external effect (Tasks 2 and 5).
- Installing or rolling back over existing user configuration or a same-name custom agent: preserve user content and report conflicts without destructive partial replacement (Task 4).

---

## Execution shape and file ownership

Execute serially in the current shared checkout or a worktree selected at execution time. Root owns
Git, decisions and release state. A worker owns only its assigned task files and must preserve other
agents' changes. Batch independent reads; avoid broad repeated source scans. Tasks are reviewable
boundaries, not reasons to create another orchestration layer.

| Boundary | Files |
| --- | --- |
| Frozen evidence | New `docs/06-delivery/acceptance/codex-adapter/evidence.md`; new sanitized `plugins/monolithic-dev-harness/tests/delivery/fixtures/codex/` files |
| Runtime/decisions | New `scripts/host_adapters/codex_runtime.py`; existing `interactions.py`, `answer_recovery.py`, `harness/decisions.py`, `harness/hook.py`, `harness/cli.py`; new Codex tests |
| Child governance | New `scripts/host_adapters/codex_bindings.py`; existing adapter, hook bridge, hook registration, rules, host declaration/schema and workflow references |
| Installation | Existing `install.sh`, Codex custom agents/manifest/MCP config, archive builder and CI installer checks; new focused shell contract |
| Qualification/release | Acceptance report/runbook, ADR-0010, README/CHANGELOG/release process, version sources and existing checks |

All `scripts/`, `tests/`, `hosts/`, `hooks/`, `config/`, and `references/` paths below are relative to
`plugins/monolithic-dev-harness/` unless they begin with `docs/`, `codex-marketplace/`, `.github/`,
`.claude-plugin/`, `install.sh`, `README.md`, `CHANGELOG.md`, or repository `scripts/` explicitly.

### Task 1: Freeze the actual Codex contract and the qualification boundary

**Files:**

- Create: `docs/06-delivery/acceptance/codex-adapter/evidence.md`.
- Create: `tests/delivery/fixtures/codex/profile.json` and sanitized `pre-tool.json`, `ask.json`, `answer.json`, `prompt.json`, `subagent-start.json`, `subagent-stop.json`, `interrupt.json` only for real observed payloads.
- Create: `tests/delivery/contract/test_codex_runtime_contract.py`.
- Modify: `docs/01-architecture/decisions/ADR-0010-codex-host-adapter.md` only after evidence settles claims.

**Interfaces:**

- Consumes: design evidence anchors and existing actual hook paths; no synthetic data labeled as captured.
- Produces: versioned profile fixture with `surface`, `host_version`, `upstream_revision`, `mode`, `advertised_tools`, `observed_events`, `trust_status`, `evidence_paths`; per-claim status `verified`, `documented`, or `unknown`.

- [ ] **Step 1: Record repository state, installed CLI and Desktop versions, local/remote candidate tags, current plugin path/version and long-lived process versions.** Do not infer Desktop from `codex --version`; do not change user configuration during discovery. Preserve existing untracked `.root-architect/` and other unrelated state.
- [ ] **Step 2: Resolve the checked official sources to an immutable upstream commit and pin each load-bearing excerpt/link.** Compare installed version behavior using the smallest available runtime inspection. Document mismatches; upstream `main` is not installed-version proof. Reuse the saved Context7 research; query again only for an unresolved exact contract.
- [ ] **Step 3: Perform one bounded native proof in an isolated fixture before broad implementation.** Capture actual spawn and child mutation events and prove an authenticated child identifier on each guarded effect; parent-only `session_id` is insufficient. Capture actual question mode/transport restrictions. Sanitize payloads while preserving shape and relationships. Label manufactured malformed fixtures separately; never fake a human answer or forge a live hook.
- [ ] **Step 4: Write failing contract tests for tool naming, mode-dependent question semantics, real child lineage and hook output wire format.** Include wrapper aliases observed in the capture, absent lineage, missing hooks, and unknown surface behavior.
- [ ] **Step 5: Resolve the release feasibility gate before product changes.** No authenticated child ID on a guarded effect means deny that effect and block release. Required decisions are prohibited under Default's optional input contract; qualify an explicitly permitted mode, preferring Plan only when its instructions permit the specific domain decision. Async needs independent permission/evidence. If either proof fails, record the blocker and stop dependent implementation; do not build a new server workaround or redefine success.
- [ ] **Step 6: Run only this focused contract file and review the evidence classification.** At this stage fixture-shape checks pass; planned missing runtime functions may fail deliberately and must be identified as such. Commit only if execution authority includes commits, with message `docs: freeze Codex adapter runtime contracts`.

Run from plugin root: `PYTHONPATH=.:scripts bin/harness-python -m pytest tests/delivery/contract/test_codex_runtime_contract.py -q -p no:cacheprovider`.

### Task 2: Make native decisions mode-aware and recover genuine answers once

**Files:**

- Create: `scripts/host_adapters/codex_runtime.py`.
- Modify: `scripts/host_adapters/interactions.py`, `scripts/host_adapters/answer_recovery.py`.
- Modify: `scripts/harness/decisions.py`, `scripts/harness/hook.py`, `scripts/harness/cli.py` only at existing presentation/capture/doctor boundaries.
- Modify: `references/human-decisions.md`, `references/workflow-storyboard.md`.
- Modify: `tests/harness/test_codex_answer_capture.py`, `tests/harness/test_question_fallback.py`.
- Create: `tests/harness/test_codex_runtime.py`.

**Interfaces:**

- Consumes: Task 1 profile and captured question/event fixtures; existing `Pending`, `Result`, `present`, and `recorded_answer` contracts.
- Produces: frozen `CodexRuntimeProfile` and `DecisionContext` records; `select_question_transport(profile: CodexRuntimeProfile, decision: DecisionContext) -> Result[str]`, returning existing `blocking`, `async`, or `chat` transport only when allowed by current contracts. An incompatible structured requirement returns `unsupported_decision_transport`.
- `DecisionContext` records required/optional, domain approval versus host permission/escalation, root/child, structured requirement and artifact/scope identity. These are validated facts from the workflow/profile, not arbitrary caller flags that can downgrade approval.
- Preserve existing `present` consumers through a narrow Codex-specific selection adapter. Do not change Claude's question contract.

- [ ] **Step 1: Add failing cases for permitted Plan domain decisions, Default optional unanswered, Default required approval rejection, unavailable Default feature, root-only tools, absent/impermissible async, required structured decision incompatibility, and forbidden sandbox escalation.** Assert that no transport selection opens approval and optional input cannot relabel an approval. Actual host-mode switching, when needed, requires a supported host operation and fresh profile, never a fabricated mode flag.
- [ ] **Step 2: Add failing capture/recovery cases for exact matching authentic answer, serialized result, duplicate replay, revoked approval, wrong project/session/call/question/options/artifact/scope, malformed private output, and interrupt/restart.** Assert a missed post-hook may recover from the genuine transcript once; synthetic model text cannot.
- [ ] **Step 3: Run the affected test functions and confirm failures express the missing behavior.** Use captured schema rather than guessed current tool fields.
- [ ] **Step 4: Implement pure profile/transport selection and narrow existing presentation/capture changes.** Keep the pending decision across fallback; never produce unconditional `isBlocking: true` for Default. Async delivery acknowledgement remains distinct from the later real human response. Preserve the typed recovery route without classifying it as structured qualification success.
- [ ] **Step 5: Extend doctor to report installation, hook trust/coverage and live decision evidence separately.** Missing evidence yields an explicit `unknown`/not-qualified finding, never a healthy live adapter assertion.
- [ ] **Step 6: Update the two workflow references to describe mode/decision restrictions, safe fallback and release blocking behavior.** Preserve exact gate meanings and digest binding.
- [ ] **Step 7: Run the focused files once, inspect diff for unchanged Claude behavior and commit if authorized.** Suggested message: `fix: respect Codex decision modes and authentic answer capture`.

Focused command from plugin root:

```bash
PYTHONPATH=.:scripts bin/harness-python -m pytest tests/harness/test_codex_runtime.py tests/harness/test_codex_answer_capture.py tests/harness/test_question_fallback.py -q -p no:cacheprovider
```

### Task 3: Bind native children to governed parent work and prove law parity

**Files:**

- Create: `scripts/host_adapters/codex_bindings.py`, `references/codex-runtime.md`.
- Modify: `scripts/host_adapters/codex_adapter.py`, `scripts/host_adapters/hook_bridge.py`, `scripts/harness/hook.py` at normalization/dispatch boundaries.
- Modify: `scripts/harness/rules.py` only to protect new binding records and classify evidenced native mutating tools.
- Modify: `hooks/codex.hooks.json`, `hosts/codex.json`, `config/host.schema.json` only where an explicit surface/evidence extension is necessary.
- Modify: `references/harness-stage-guide.md`, `skills/thermos/SKILL.md`, `skills/architect/SKILL.md` to reference the narrow Codex runtime instructions.
- Modify: `tests/harness/test_subagents.py`, `tests/harness/test_hook_security.py`, `tests/harness/test_work_session_context.py`.
- Create: `tests/harness/test_codex_bindings.py`, `tests/delivery/contract/test_codex_hook_subprocess.py`.

**Interfaces:**

- Consumes: real native lifecycle/event/result profile, existing `CanonicalToolEvent`, `Brief`, `Handle`, `Result`, and work-session authorization checks.
- Produces: frozen `CodexChildBinding` with parent native session, child native session, resolved project, work-session ID, role/effect class, owned paths, operation ID and lifecycle status.
- `binding_from_host_event(payload: Mapping[str, object], profile: CodexRuntimeProfile) -> Result[CodexChildBinding]` validates captured native provenance/shape; it does not trust an agent-supplied parent ID.
- `resolve_child_scope(repo: Path, native_session_id: str) -> Result[str]` returns the already-authorized parent work-session scope or a precise binding error.
- `observe_lifecycle(repo: Path, payload: Mapping[str, object], profile: CodexRuntimeProfile) -> Result[CodexChildBinding]` is isolated hook-only persistence. There is no public CLI/MCP operation that registers authority or writes binding state.
- Python `codex_adapter.subagents()` remains unsupported unless a real callable subprocess transport independently meets the existing contract; native instruction workflows are declared separately.

- [ ] **Step 1: Add failing lineage tests for real child/root mapping, cross-project child, conflicting parent, missing binding, stale ended parent, interrupted/cancelled child, duplicate lifecycle event and direct binding-file edits.** Unknown state does not imply successful stop/cancel.
- [ ] **Step 2: Add a parametrized root/child law matrix against real wire shapes.** Cover human-owned records, untrusted tracker, missing scoped approval, protected item even after approval, generated file, guarded-path requirement, draft/review/check requirements, history rewrite, Feature branch target, code prerequisites and completion requirements. Reuse existing rule fixtures; do not create a new policy engine.
- [ ] **Step 3: Add alias coverage tests for captured shell/file/MCP/wrapper tools and lifecycle tools.** Confirm native start, follow-up, status/wait and cancel evidence target the same child. `SubagentStart` is context notification and ignores `continue: false`; test spawn denial only through a proven enforceable pre-tool path. Otherwise deny effects and report that narrower guarantee. Instructions never prove completion.
- [ ] **Step 4: Run only failing new cases, then implement hook normalization and binding persistence using immutable transformations and `Result`.** Route normalized child effects through existing policy. Refuse guarded effects where lineage/coverage is unproven; when root and child events are indistinguishable, never assume root authority. Do not introduce app-server child `turn/start`/`turn/steer` control.
- [ ] **Step 5: Write the model-facing Codex workflow reference.** Root invokes observed native tools, records actual returned identity, supplies governing scope and limits, checks real status, routes follow-up to the same child, and waits for real cancellation/completion. Reviewer instructions keep independent context and no forbidden nested spawn/skill calls. Children return decision needs to root.
- [ ] **Step 6: Update capability provenance and stage/reviewer guidance.** Separate model runtime capability from Python subprocess support and Desktop from CLI; mark unobserved Canvas and child behavior unknown. Do not use Claude's unsupported subprocess stub as the parity ceiling.
- [ ] **Step 7: Run the focused files plus the existing scope/security slice once and review the complete law matrix.** Commit if authorized: `feat: govern Codex native subagents in parent work sessions`.

Focused command from plugin root:

```bash
PYTHONPATH=.:scripts bin/harness-python -m pytest tests/harness/test_codex_bindings.py tests/harness/test_subagents.py tests/harness/test_hook_security.py tests/harness/test_work_session_context.py tests/delivery/contract/test_codex_hook_subprocess.py -q -p no:cacheprovider
```

### Task 4: Make the distributable Codex installation match the verified runtime

**Files:**

- Modify: repository `install.sh`, `scripts/build_release.sh`, `.github/workflows/ci.yml`.
- Modify: `codex-marketplace/agents/mdh_thermo_review.toml`, `codex-marketplace/agents/mdh_thermo_quality.toml`.
- Modify: plugin `.codex-plugin/plugin.json`, `codex.mcp.json` only if evidence requires a corrected supported format.
- Modify: `tests/integrations/test_host_mcp_config.py`, `tests/delivery/test_manifests.py`, `tests/run.sh`.
- Create: `tests/test_installer_codex.sh`.

**Interfaces:**

- Consumes: supported minimum/profile from Task 1, runtime reference and child governance from Task 3.
- Produces: idempotent supported Codex install, correct hooks/MCP/custom agents/runtime reference in the archive, explicit readiness limits, uninstall/rollback preserving unrelated configuration.

- [ ] **Step 1: Add failing sandboxed shell contracts for missing supported feature, explicit false, unset/true setting, pre-existing unrelated config/comments, custom-agent name collision, stale cached package, paths with spaces, failed partial registration, repeat install, and uninstall.** Use a minimal fake CLI for deterministic installer contracts; label it as fake evidence.
- [ ] **Step 2: Add failing archive/MCP contracts that verify the native runtime reference, actual profile assets, hook config, absolute installed MCP paths and both custom agents.** Agent instructions retain read-only review and forbid unnecessary nested delegation; model settings respect the approved ceiling rather than an invented universal model ID.
- [ ] **Step 3: Implement the minimum installation correction based on observed feature and plugin contracts.** Preserve explicit user choices and unrelated config. Fail clearly on a required unsupported setting instead of silently turning it into a passing installation. Record only installer-owned additions for restoration. Do not change global user configuration through an undocumented workaround.
- [ ] **Step 4: Wire the focused shell contract into `tests/run.sh` and strengthen existing CI install assertions for packaged assets.** Preserve Python 3.12/3.13 and other host checks. Keep operational live qualification separate from sandboxed registration checks.
- [ ] **Step 5: Run new shell and affected JSON/MCP contracts once; inspect installer ownership and failure cleanup paths.** Commit if authorized: `fix: package and preserve verified Codex integration`.

Run from plugin root: `bash tests/test_installer_codex.sh`, then `PYTHONPATH=.:scripts bin/harness-python -m pytest tests/integrations/test_host_mcp_config.py tests/delivery/test_manifests.py -q -p no:cacheprovider`.

### Task 5: Run one real installed candidate acceptance trial

**Files:**

- Create: `docs/06-delivery/acceptance/codex-adapter/trial.md` and sanitized evidence under the same directory.
- Modify: `docs/06-delivery/acceptance/codex-adapter/evidence.md` with actual outcome links.
- Modify: `docs/06-delivery/release-process.md` to distinguish installed-host qualification from static checks.

**Interfaces:**

- Consumes: candidate archive, exact tested commit/checksum/version, focused test results and fresh builder/review findings.
- Produces: actual acceptance report with each required outcome `passed`, `failed`, or `pending`, authentic session/tool/decision IDs and evidence paths; no fabricated answer or summarized substitute for a live result.

- [ ] **Step 1: Prepare and publish the next unused candidate before its trial.** Refresh tag inventory; atomically bump all version sources listed in Task 6 to the selected RC, run metadata checks and mandatory candidate CI, obtain existing maintainer PR/tag publication approval, then publish through the existing release workflow and acquire its archive/checksum. The same candidate's live trial follows publication, as the current release process requires. Prepare one disposable project and dedicated remote fixture, preserving existing work/data; record prior version and restoration path. Stop at a pending maintainer publication checkpoint when approval is absent.
- [ ] **Step 2: Install the candidate archive using the actual installer, restart Desktop/gateways, confirm loaded version/path/checksum, trust the actual hooks, and verify all three MCP servers.** If a required surface/tool is absent, stop with exact evidence rather than adding another transport project.
- [ ] **Step 3: Compose minimal actual delegations for each parity family in the same fixture.** Cover the governing Feature/Story worker, `bmad-build` reviewer, architect candidates, PRD extraction, review fanout, persona agents and both thermos custom reviewers with tiny scoped artifacts. Confirm independent contexts, actual child identities, parent scope, forbidden nested delegation, denied root/child effects and no cross-session approval reuse. Follow up to the same worker, inspect status, cancel a disposable child. Omitted required families block full parity; never run all full workflows on a real product for this check.
- [ ] **Step 4: Present the actual review artifact and execute the mandatory workflow in the explicitly permitted decision mode.** Default cannot host its required approval under an optional-only tool contract. Use Plan only when official instructions allow this domain decision; independently qualify any async route. Record the real human structured selection through host capture. Proxy design approval cannot authorize future runtime decisions. If absent, preserve the pending checkpoint; typed fallback alone does not pass.
- [ ] **Step 5: In the same fixture exercise missed-answer recovery, interrupt/restart and duplicate delivery.** Use a supported interruption/capture diagnostic mechanism, never forge a production hook event or write decision records. Verify the genuine answer is recovered once and revoked approval stays revoked.
- [ ] **Step 6: Demonstrate one authentic denied external write before approval and one scoped approved external write after the real human approval.** Read back the effect. Resume does not repeat the write. Local fake gateway success is insufficient for this criterion.
- [ ] **Step 7: Record Desktop artifact review and separately discover actual connected Canvas capability.** A verified opened preview plus summary satisfies existing artifact review; editable Canvas is not mandatory unless the workflow specifically requires editing it. Use advertised Canvas operations only if present and leave unknown/unavailable explicit. Qualify CLI separately only if its required outcomes are observed; otherwise claim Desktop only.
- [ ] **Step 8: Write a compact outcome matrix and retain all failed/pending evidence.** Fix a defect in its owning task, bump a new candidate when required, and rerun only affected steps plus the required release checks. No silent law relaxation or whole-trial loop.

### Task 6: Close review findings and cut the gated release

**Files:**

- Modify: `README.md`, `CHANGELOG.md`, `docs/06-delivery/release-process.md`, `docs/01-architecture/decisions/ADR-0010-codex-host-adapter.md`.
- Modify version sources: `plugins/monolithic-dev-harness/.claude-plugin/plugin.json`, `plugins/monolithic-dev-harness/.cursor-plugin/plugin.json`, `plugins/monolithic-dev-harness/.codex-plugin/plugin.json`, repository `.claude-plugin/marketplace.json`, README badge and newest CHANGELOG heading/link.
- Modify: `scripts/check_versions.py` only if an actual new version source was added; otherwise use existing checker unchanged.
- Final evidence: `docs/06-delivery/acceptance/codex-adapter/trial.md`.

**Interfaces:**

- Consumes: completed Task 5 outcome matrix, focused results, builder findings and required green CI.
- Produces: accurately scoped candidate/final release notes and reviewable PR; maintainer-approved release/tag and archive/checksum only when all gates are met.

- [ ] **Step 1: Request one fresh scoped final review of correctness/security and law compatibility.** Provide changed files and evidence matrix, not all repository history. Resolve concrete defects; preserve unresolved findings. Review does not replace the real trial.
- [ ] **Step 2: Update ADR and user-facing support claims to the exact qualified surface/version/outcomes.** Record typed-only or unknown modes as limitations/blockers. Explain restart/trust, structured decisions, native worker governance, artifact review, installation and rollback using verified behavior.
- [ ] **Step 3: After the published candidate passes Task 5, update all existing version sources atomically to final `0.7.0`.** Candidate preparation already occurred in Task 5 Step 1; a failed trial instead requires the next unused RC there, with doubled hyphen in the README candidate badge. Do not claim final release from a plan or static checks.
- [ ] **Step 4: Run repository metadata checks once: `python3 scripts/check_repo.py`, `python3 scripts/check_versions.py`, and `git diff --check`.** Let CI own the full Python 3.12/3.13 suites, lint/format/shellcheck/schema/docs/Markdown and sandboxed install/uninstall. Repeat a slice only after a relevant fix. Existing release workflow's full test/build run remains mandatory.
- [ ] **Step 5: Open the release PR if authorized, attach it to this chat, and obtain maintainer approval/merge.** Tag/publication follows the existing `docs/06-delivery/release-process.md` ownership; no release action is implied by approval of this planning document. Confirm required CI on the actual release commit.
- [ ] **Step 6: Publish the candidate/final archive only through the existing release workflow, verify checksum/assets and perform the required post-release checks.** Record versions and outcomes. A pending human trial, missing child governance or prohibited required picker use prevents the final fully-functional release claim.
- [ ] **Step 7: If rollback is needed, install the previous known-good `--version`, restore only installer-owned config, restart host/gateways and preserve all work-session/approval evidence.** Follow the existing release rollback policy without deleting tags/history or user state.

## Verification budget and stop conditions

Local verification is Task 1's frozen-contract check, one focused run per changed boundary in Tasks
2–4, one builder check, one scoped final review and the single real trial in Task 5. Full suites
remain CI/release gates and are not repeated locally for reassurance. No benchmarks, repeated
model round trips, broad unrelated cleanup or open-ended trial loops.

Stop dependent work on an unresolved supported-mode conflict, missing genuine human answer,
unproven child authority, unknown mutating tool coverage, failed gate or missing required surface.
Continue independent authorized documentation/evidence work and record a concrete resumable
checkpoint. A stopped release is an honest outcome; never alter the acceptance definition or
manufacture state to turn it green.

## Planning completion versus release completion

The planning assignment is complete when this design and plan have passed the fresh builder
check and the root proxy has resolved findings. Implementation completion additionally needs the
focused contracts and required CI. Release completion additionally needs authentic installed-host
acceptance, genuine human capture, required maintainer approvals and published verified assets.

## Builder check and coverage map

The fresh builder check is complete; the root proxy approved its refinements. Required decision
mode and real human authority map to Tasks 1, 2 and 5; child identity and notification-only spawn
events to Tasks 1 and 3; every Claude parity family to Tasks 3 and 5; Canvas discovery and supported
artifact fallback to Task 5; installer ownership and mandatory release checks to Tasks 4 and 6.
These are plan coverage statements, not evidence that implementation or acceptance has passed.

## Updated execution model limits

The user subsequently required subagents one model tier below the root with medium reasoning
by default, and builder/coder subagents on `gpt-5.6-luna` with low (light) reasoning. Higher effort
requires a specific justification and cannot exceed high. These execution limits supersede the
earlier blanket top-tier subagent allowance.
